import threading
import time

import serial
import serial.tools.list_ports

# Exception are managed elsewhere


SERIAL_TIMEOUT = 0.1  # in s
TOTAL_TIMEOUT = 1.5  # timeout after which stop waiting for the response


def get_port() -> list[dict[str, str]]:
    """Return a list of dictionaries formatted as follow:
    ```json
    [
        {"name": name_1, "description": desc_1, "manufacturer": manu_1, "device": device_1},
        {"name": name_2, "description": desc_2, "manufacturer": manu_2, "device": device_2},
        {"name": name_3, "description": desc_3, "manufacturer": manu_3, "device": device_3}
    ]
    ```
    """

    serial_port = serial.tools.list_ports.comports()

    port_list = []
    for port in serial_port:
        port_list.append(
            {
                "name": port.name,
                "description": port.description,
                "manufacturer": port.manufacturer,
                "device": port.device,
            }
        )

    return port_list


class SerialPort:
    timeout = TOTAL_TIMEOUT

    def __init__(self) -> None:
        self._port = None
        self._baud_rate = None
        self.serial = serial.Serial()

        self._lock = threading.Lock()

    def connect(self) -> bool:
        """Opens the serial port and verifies it's ready.
        If already open, close and open a new connection. Done to update the
        port, baud_rate and timeout."""

        # Do not change the parameters while serial.read() is executing (on a
        # different thread). Closing the connection and reopening is will cause
        # some problems
        to_open = False
        if (
            self.serial.port != self._port
            or self.serial.baudrate != self._baud_rate
            or self.serial.timeout != SERIAL_TIMEOUT
        ):
            if self.serial.is_open:
                self.serial.close()

            self.serial.port = self._port
            self.serial.baudrate = self._baud_rate
            self.serial.timeout = SERIAL_TIMEOUT

            to_open = True

        else:
            # paramter didn't change
            if not self.serial.is_open:
                to_open = True

        try:
            if to_open:
                self.serial.open()

            return True
        except serial.SerialException as e:
            print("Connection error:")
            print(str(e))

            return False

    def verify_conn(self):
        if not self.connect():
            return False

        response = bytes()
        operation_timeout = time.time() + self.timeout

        with self._lock:
            self.serial.reset_input_buffer()
            self.serial.write("V".encode("ascii"))

        while not response and time.time() < operation_timeout:
            with self._lock:
                response = self.serial.read(1)

        return self._check_response("V", response, "Connection verification")

    def send_timer(
        self,
        timerU_int: bytes,
        timerH_int: bytes,
        timerL_int: bytes,
        timerH_reset: bytes,
        timerL_reset: bytes,
    ) -> bool:
        """Send the 5 configuration bytes for the timer."""
        if not self.connect():
            return False

        # --- start of timer config ---
        response = bytes()
        operation_timeout = time.time() + self.timeout
        expected_response = "W".encode("ascii")

        with self._lock:
            self.serial.reset_input_buffer()
            self.serial.write("T".encode("ascii"))

        # Sometimes it can happen that some data arrives in between the
        # execution of reset_input_buffer and the occurance of the
        # interrupt on the microcontroller. It means that some data may
        # be present in the buffer even if different than W. So we need
        # to wait that this W arrive. If too much time has elapsed,
        # return False
        while response != expected_response and time.time() < operation_timeout:
            with self._lock:
                response = self.serial.read(1)

        if not self._check_response("W", response, "start of timer config"):
            return False

        # --- send timer config data ---
        with self._lock:
            self.serial.write(timerU_int)
            self.serial.write(timerH_int)
            time.sleep(0.0002)  # wait 200us just for safety
            self.serial.write(timerL_int)
            self.serial.write(timerH_reset)
            time.sleep(0.0002)  # wait 200us just for safety
            self.serial.write(timerL_reset)

        # --- end of timer config ---
        response = bytes()
        operation_timeout = time.time() + self.timeout

        while not response and time.time() < operation_timeout:
            with self._lock:
                response = self.serial.read(1)

        return self._check_response("D", response, "end of timer config")

    def send_start(self) -> bool:
        if not self.connect():
            return False

        response = bytes()
        operation_timeout = time.time() + self.timeout

        with self._lock:
            self.serial.reset_input_buffer()
            self.serial.write("S".encode("ascii"))

        while not response and time.time() < operation_timeout:
            with self._lock:
                response = self.serial.read(1)

        return self._check_response("D", response, "start operation")

    def send_stop(self) -> bool:
        if not self.connect():
            return False

        response = bytes()
        operation_timeout = time.time() + self.timeout
        expected_response = "D".encode("ascii")

        with self._lock:
            self.serial.reset_input_buffer()
            self.serial.write("E".encode("ascii"))

        # We need to wait the the D code is reached inside the buffer, because some
        # data may be received while the E code is sent
        while response != expected_response and time.time() < operation_timeout:
            with self._lock:
                response = self.serial.read(1)

        return self._check_response("D", response, "end operation")

    def send_debug_mode(self) -> bool:
        if not self.connect():
            return False

        response = bytes()
        operation_timeout = time.time() + self.timeout
        expected_response = "D".encode("ascii")

        with self._lock:
            self.serial.reset_input_buffer()
            self.serial.write("M".encode("ascii"))
            self.serial.write("D".encode("ascii"))

        # We need to wait the the D code is reached inside the buffer, because some
        # data may be received while the E code is sent
        while response != expected_response and time.time() < operation_timeout:
            with self._lock:
                response = self.serial.read(1)

        return self._check_response("D", response, "set debug mode")

    def send_production_mode(self) -> bool:
        if not self.connect():
            return False

        response = bytes()
        operation_timeout = time.time() + self.timeout
        expected_response = "D".encode("ascii")

        with self._lock:
            self.serial.reset_input_buffer()
            self.serial.write("M".encode("ascii"))
            self.serial.write("P".encode("ascii"))

        # We need to wait the the D code is reached inside the buffer, because some
        # data may be received while the E code is sent
        while response != expected_response and time.time() < operation_timeout:
            with self._lock:
                response = self.serial.read(1)

        return self._check_response("D", response, "set production mode")

    def get_data(self) -> bytes:
        """Read 1 bytes from the serial port. If the transmission rate is small, a
        null byte b'' may be returned. This happen because of the read timeout
        of the serial (0.1s)
        """
        with self._lock:
            value = self.serial.read(1)

        return value

        # DEBUG:

        # if ser.in_waiting > 0:
        #     data = ser.read(1)
        #     byte_val = data[0]
        #
        #     # Convert to different formats
        #     binary_str = format(byte_val, "08b")  # 8-bit binary with leading zeros
        #     hex_str = format(byte_val, "02X")  # 2-digit uppercase hex
        #     dec_val = byte_val
        #     ascii_char = chr(byte_val) if 32 <= byte_val <= 126 else "."  # printable ASCII
        #
        #     print(
        #         f"Byte: {data} | BIN: {binary_str} | HEX: {hex_str} | DEC: {dec_val} | ASCII: {ascii_char}"
        #     )

    def _check_response(
        self,
        expected_response_str: str,
        response: bytes | bytearray,
        operation: str,
    ):
        if not response:
            print(f"[{operation}] timed out.")
            return False

        if response == expected_response_str.encode("ascii"):
            print(f"Received text while doing [{operation}]: '{expected_response_str}'")
            return True
        else:
            try:
                text = response.decode("utf-8").strip()
            except UnicodeDecodeError:
                text = response

            print(
                f"[{operation}] failed. Expected '{expected_response_str}' but got '{text}'."
            )
            return False

    @property
    def port(self):
        """Port"""
        return self._port

    @port.setter
    def port(self, value: str):
        self._port = value

    @property
    def baud_rate(self):
        """Baud rate"""
        return self._baud_rate

    @baud_rate.setter
    def baud_rate(self, value: int):
        self._baud_rate = value


serial_port = SerialPort()
