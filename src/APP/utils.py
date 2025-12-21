import threading
import time

import numpy as np
from constants import OSC_FREQ, OVERFLOW_VALUE, TMREG, UREG
from model import current_session
from numpy._typing import NDArray
from serial_comm import serial_port


class Utils:
    _data_buffer: list[tuple[int, int]] = []

    _lock = threading.Lock()
    _stop = True
    _error = False

    _thread = None

    def get_int_time(self, value: float) -> tuple[float, bytes, bytes, bytes]:
        """Get integration time provided the ideal one in seconds.

        Returns
        -------
            tuple containing:
                - int_time (float) : actual integration time reachable by the clock
                - three bytes of the timer register. The first byte returned is timerU,
                    the second is timerH and the last is timerL
        """

        # value = tmr_bin * u_bin / OSC_FREQ
        # max(value) = 2^24
        # max(tmr_bin) = TMREG = 2^16 (16 bit)
        # max(u_bin) = UREG = 2^8 (8 bit)

        tmr_bin = 0
        u_bin = 0
        error = -1
        int_time = 0

        # start from UREG becasue we want to have the minimum number of interrupt (ie
        # u_bin as small as possible)
        for u_bin_tmp in range(UREG, 0, -1):  # 256 -> 1
            tmr_bin_tmp = value * OSC_FREQ / u_bin_tmp
            tmr_bin_tmp = round(tmr_bin_tmp)
            if tmr_bin_tmp == 0:
                # int_time can't be lower than 30us
                tmr_bin_tmp = 1

            int_time_tmp = tmr_bin_tmp * u_bin_tmp / OSC_FREQ
            error_tmp = (int_time_tmp - value) ** 2

            if (error_tmp <= error and tmr_bin_tmp <= TMREG) or error < 0:
                tmr_bin = tmr_bin_tmp
                u_bin = u_bin_tmp
                error = error_tmp
                int_time = int_time_tmp

        if tmr_bin > TMREG:
            tmr_bin = TMREG
            u_bin = UREG
            int_time = tmr_bin * u_bin / OSC_FREQ

        tmr_reg = TMREG - tmr_bin
        u_reg = UREG - u_bin

        # if u_reg is 256 (=2^8, 0001 0000 0000) timerU must be 0. Doing an AND with
        # 0xFF (1111 1111) will give 0
        timerU = bytes([u_reg & 0xFF])
        timerH = bytes([(tmr_reg >> 8) & 0xFF])
        timerL = bytes([tmr_reg & 0xFF])

        return int_time, timerU, timerH, timerL

    def get_reset_time(self, value: float) -> tuple[float, bytes, bytes]:
        """Get reset time provided the ideal one in seconds.

        Returns
        -------
            tuple containing:
                - reset (float) : actual reset time reachable by the clock
                - two bytes of the timer register. The first byte returned is timerH and
                    the second is timerL.
        """
        bin_raw = value * OSC_FREQ

        if bin_raw > TMREG:
            bin_value = TMREG + current_session.tx_delay
            reset_time = bin_value / OSC_FREQ

            timerH = bytes([0])  # bytes uses lists
            timerL = bytes([0])

        else:
            bin_value = round(bin_raw)
            bin_value = bin_value - current_session.tx_delay

            # minimum value of bin_value is 1 becuase we must always wait a ticks of the
            # clock before going into overflow

            if bin_value <= 0:
                bin_value = 1  # the TX_DELAY is not done with the timer

            reset_time = (current_session.tx_delay + bin_value) / OSC_FREQ

            bin_value = TMREG - bin_value
            timerH = bytes([(bin_value >> 8) & 0xFF])
            timerL = bytes([bin_value & 0xFF])

        return reset_time, timerH, timerL

    def start_receiving(self, simulate: bool = False, rate: int | None = None):
        """Start a thread that read the data from the serial port and save them
        inside utils_data. If simulate is True, these data are simulated at the
        given rate. If None, a default value of 5 measures/ms is used. If simulate
        is False, this value is ignored."""
        self._stop = False
        if not simulate:
            self._thread = threading.Thread(target=self._get_serial_data, daemon=False)

        else:
            self._thread = threading.Thread(
                target=self._simulate_data, args=(rate,), daemon=False
            )

        self._thread.start()

    def stop_receiving(self, send_stop: bool):
        """Waits for the reader thread to completely terminate. If send_stop
        is True, the end message is sent to the serial port"""
        self._stop = True

        if self._thread is not None:
            if self._thread.is_alive():
                self._thread.join()  # Wait until the thread is finished

        if send_stop:
            response = serial_port.send_stop()
        else:
            response = True

        return response

    def empty_buffer(self):
        """Empty the data list (utils._data_buffer)"""
        with self._lock:
            self._data_buffer.clear()

    def get_latest_data(self) -> list[tuple[int, int]]:
        """Return a list containing the data inserted in utils._data_buffer.

        Returns
        -------
            The list of data.

        Raise
        -----
            RuntimeError: Raised when an error occured during the reading
            (self._error = True), e.g. when the port is disconnected during the
            reading

        """

        if self._error:
            self._error = False
            raise RuntimeError("An error occured while receiving some data")

        with self._lock:
            if not self._data_buffer:
                return []

            # since only the pointer is copied in new_data, this operation is very
            # fast
            new_data = self._data_buffer
            self._data_buffer = []

        return new_data

    def convert_data(self, data: list[tuple[int, int]]) -> NDArray[float]:
        """Given the list of data (tuple[ch1, ch2]), convert them into a np array and substitute
        the wrong data with np.nan."""
        # new_data = [ (diff1_ch1, diff1_ch2), (diff2_ch1, diff2_ch2)]    in production
        arr = np.array(data, dtype=float)  # allows NaN
        arr[arr == OVERFLOW_VALUE] = np.nan
        return arr

    def convert_data_debug(
        self, data: list[tuple[tuple[int, int], tuple[int, int]]]
    ) -> tuple[NDArray, NDArray, NDArray]:
        # new_data = [ ( (a1,b1),(c1,d1) ), ( (a2,b2),(c2,d2) ), ...]     in debug
        # new_data = [ (diff1_ch1, diff1_ch2), (diff2_ch1, diff2_ch2)]    in production
        # In the production mode the output is already the difference between the two

        # start = [[a, c], ...]
        start_values = np.array([[a, c] for (a, b), (c, d) in data], dtype=float)
        # stop = [[b, d], ...]
        stop_values = np.array([[b, d] for (a, b), (c, d) in data], dtype=float)
        stop_values[stop_values == OVERFLOW_VALUE] = np.nan

        new_data = stop_values - start_values
        new_data[new_data < 0] = np.nan
        new_data[new_data == OVERFLOW_VALUE] = np.nan

        return start_values, stop_values, new_data

    def _get_serial_data(self):
        """Reads byte-by-byte from the serial port."""

        byte_buffer = bytearray()

        if current_session.debug_mode:
            while not self._stop:
                try:
                    read_byte = serial_port.get_data()

                    # If the read returned a byte (i.e., it didn't time out)
                    if read_byte:
                        byte_buffer.extend(read_byte)

                        if len(byte_buffer) == 8:
                            start_value_ch1 = int.from_bytes(
                                byte_buffer[0:2], byteorder="little"
                            )
                            stop_value_ch1 = int.from_bytes(
                                byte_buffer[2:4], byteorder="little"
                            )
                            start_value_ch2 = int.from_bytes(
                                byte_buffer[4:6], byteorder="little"
                            )
                            stop_value_ch2 = int.from_bytes(
                                byte_buffer[6:8], byteorder="little"
                            )
                            with self._lock:  # Lock to protect the shared _data list
                                self._data_buffer.append(
                                    (
                                        (start_value_ch1, stop_value_ch1),
                                        (start_value_ch2, stop_value_ch2),
                                    )
                                )

                            # Clear the buffer to be ready for the next 2 bytes
                            byte_buffer.clear()

                except Exception as e:
                    print(f"Error in reader thread: {e}")
                    self._error = True
                    break

        else:
            while not self._stop:
                try:
                    read_byte = serial_port.get_data()

                    # If the read returned a byte (i.e., it didn't time out)
                    if read_byte:
                        byte_buffer.extend(read_byte)

                        if len(byte_buffer) == 4:
                            value_ch1 = int.from_bytes(
                                byte_buffer[0:2], byteorder="little"
                            )
                            value_ch2 = int.from_bytes(
                                byte_buffer[2:4], byteorder="little"
                            )
                            with self._lock:  # Lock to protect the shared _data list
                                self._data_buffer.append((value_ch1, value_ch2))

                            # Clear the buffer to be ready for the next 2 bytes
                            byte_buffer.clear()

                except Exception as e:
                    print(f"Error in reader thread: {e}")
                    self._error = True
                    break

    def _simulate_data(self, rate: int | None = None):
        """Fill the data list with random numbers at intervals defined by the
        given rate parameter. It should be in measure/ms. So, for rate of 2, we would
        get 2 integers every millisecond.
        If rate is None, the default value of 5 is used (1 int every 200 us)
        The time.sleep() function may not be accurate under 1ms, so very high rate
        are very hard to reproduce accuratly.
        """

        if rate is None:
            rate = 5  # 5 int/ms = 1 every 200 us

        while True:
            if not self._stop:
                start = time.perf_counter()

                start_value, stop_value, diff_value = self._generate_random_val()

                if not current_session.debug_mode:
                    with self._lock:
                        self._data_buffer.append((diff_value[0], diff_value[1]))

                else:
                    with self._lock:
                        self._data_buffer.append(
                            (
                                (start_value[0], stop_value[0]),
                                (start_value[1], stop_value[1]),
                            )
                        )

                tm_sleep = 10**-3 / rate

                end = time.perf_counter()

                elapsed = end - start

                if tm_sleep - elapsed > 0:
                    time.sleep(tm_sleep - elapsed)

                # The sleep function is not reliable in the hundreds of microseconds
                # region

            else:
                break

    def _generate_random_val(self) -> tuple[float, float, float]:
        """Generate two random numbers. If they overflow, the stop_value and diff_value
        will have OVERFLOW_VALUE.

        Returns
        -------
            Tuple containing the start_value, stop_value and their difference
        """

        # return np.array([1, 1]), np.array([3500, 3500]), np.array([3499, 3499])
        start_value_ch1 = np.random.normal(loc=1000, scale=50, size=1)
        start_value_ch1 = int(start_value_ch1[0])

        stop_value_ch1 = np.random.normal(loc=3700, scale=150, size=1)
        stop_value_ch1 = int(stop_value_ch1[0])

        start_value_ch2 = np.random.normal(loc=300, scale=50, size=1)
        start_value_ch2 = int(start_value_ch2[0])

        stop_value_ch2 = np.random.normal(loc=3500, scale=150, size=1)
        stop_value_ch2 = int(stop_value_ch2[0])

        start_value = np.array([start_value_ch1, start_value_ch2])
        stop_value = np.array([stop_value_ch1, stop_value_ch2])
        diff_val = stop_value - start_value

        if stop_value_ch1 < start_value_ch1 or stop_value_ch1 >= 2**12 - 1:
            stop_value[0] = OVERFLOW_VALUE
            diff_val[0] = OVERFLOW_VALUE

        if stop_value_ch2 < start_value_ch2 or stop_value_ch2 >= 2**12 - 1:
            stop_value[1] = OVERFLOW_VALUE
            diff_val[1] = OVERFLOW_VALUE

        return start_value, stop_value, diff_val


utils = Utils()
