OVERFLOW_VALUE = 2**15

OSC_FREQ = 2**15  # 32768 Hz
TMREG = 2**16  # timerH * timerL
UREG = 2**8  # timerU

# From the start of the interrupt to the end of the transmission
# if 190 us => TX_DELAY = 6 ticks
# The value in s is TX_DELAY / OSC_FREQ . It is an approximation by defects
TX_DELAY_PRO = 13  # ticks
TX_DELAY_DEBUG = 25  # ticks


UPDATE_INTERVAL_MS = 50  # in ms
NUM_BINS = 2**12  # 4096 bars for the multichannel
