from dataclasses import dataclass

from constants import TX_DELAY_DEBUG, TX_DELAY_PRO


@dataclass
class Session:
    int_time: int = 1
    reset_time: int = 1
    sample_freq: int = 1
    file_path: str | None = None
    tx_delay: int = TX_DELAY_PRO
    _debug_mode: bool = False

    @property
    def debug_mode(self):
        return self._debug_mode

    @debug_mode.setter
    def debug_mode(self, value):
        if value:
            self.tx_delay = TX_DELAY_DEBUG
        else:
            self.tx_delay = TX_DELAY_PRO
        self._debug_mode = value


current_session = Session()
