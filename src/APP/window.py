from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from serial_comm import serial_port
from windows.file_path_window import FilePathWindow
from windows.running_window import RunningWindow
from windows.setting_window import SettingWindow
from windows.time_window import TimeWindow

# TODO: What happen when the serial cable is disconnected while measuring?
# Add a stop button even if start wasn't pressed

# TODO: Add the possibility to choose the starting time and end time for the
# analysis, separately. (the detector is turned on before starting the beam)


class MainWindow(QWidget):
    def __init__(self, simulate: bool, baud_rate: int, is_single_channel: bool):
        super().__init__()
        self.simulate = simulate
        self.is_single_channel = is_single_channel
        serial_port.baud_rate = baud_rate
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("MicroDosimeter")
        self.resize(1200, 800)

        master = QVBoxLayout()
        self.setLayout(master)

        self.windows_stack = QStackedWidget()
        master.addWidget(self.windows_stack)

        self.setup_window = SetupWindow(self.simulate)
        self.setup_window.change_to_running_window.connect(
            self.change_to_running_window
        )
        self.setup_window.file_window.load_signal.connect(self.load_data)
        self.running_window = RunningWindow(self.simulate)
        self.running_window.restart_signal.connect(self.restart_window)

        self.windows_stack.addWidget(self.setup_window)
        self.windows_stack.addWidget(self.running_window)

        self.windows_stack.setCurrentIndex(0)

    def change_to_running_window(self):
        self.windows_stack.setCurrentIndex(1)
        self.running_window.on_frequency_change()

    def restart_window(self):
        self.setup_window.restart_from_beginning()
        # serial_port.serial.close()
        self.windows_stack.setCurrentIndex(0)

    def load_data(self, file_path: str):
        try:
            self.running_window.load_file(file_path)
            self.windows_stack.setCurrentIndex(1)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load: {str(e)}")
            print(str(e))

    def closeEvent(self, a0) -> None:
        if self.windows_stack.currentIndex() == 1:  # running_window
            close = self.running_window.close_event()

            if close:
                return super().closeEvent(a0)

            return a0.ignore()

        else:
            return super().closeEvent(a0)


class SetupWindow(QWidget):
    change_to_running_window = pyqtSignal()

    def __init__(self, simulate: bool):
        super().__init__()
        self.simulate = simulate
        self.init_ui()

    def init_ui(self):
        # header section
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet(
            "/* background-color: white */ ; border-bottom: 1px solid #ddd;"
        )
        header_layout = QVBoxLayout(self.header_frame)

        self.header_title = QLabel("Step 1: Data Setup")
        self.header_title.setStyleSheet(
            "font-size: 22pt; font-weight: bold; color: palette(text); border: none;"
        )

        self.header_subtitle = QLabel("Choose where to save your measurement data.")
        self.header_subtitle.setStyleSheet("font-size: 15pt; color: #666; border: none")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 3)
        self.progress_bar.setValue(1)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: none; background: #eee; border-radius: 3px; }
            QProgressBar::chunk { background: #0078d7; border-radius: 3px; }
        """)

        header_layout.addWidget(self.header_title)
        header_layout.addWidget(self.header_subtitle)
        header_layout.addSpacing(10)
        header_layout.addWidget(self.progress_bar)
        header_layout.setContentsMargins(30, 20, 30, 20)

        # content section
        self.stack_view = QStackedWidget()
        self.stack_view = DynamicStackedWidget()

        # Windows
        self.file_window = FilePathWindow()
        self.file_window.enable_next.connect(lambda: self.next_bnt.setEnabled(True))

        self.setting_window = SettingWindow(self.simulate)
        self.setting_window.connection_successfull.connect(self.connection_successfull)

        self.time_window = TimeWindow(self.simulate)
        self.time_window.sent_successfull.connect(self.sent_successfull)
        self.time_window.editing_time.connect(self.disable_next)

        self.stack_view.addWidget(self.file_window)
        self.stack_view.addWidget(self.setting_window)
        self.stack_view.addWidget(self.time_window)

        # footer section
        self.footer_frame = QFrame()
        self.footer_frame.setStyleSheet(
            "/* background-color: #f5f5f5 */; border-top: 1px solid #ddd;"
        )
        footer_layout = QHBoxLayout(self.footer_frame)
        footer_layout.setContentsMargins(30, 15, 30, 15)

        self.back_bnt = QPushButton("Back")
        self.back_bnt.setEnabled(False)
        self.back_bnt.setStyleSheet("""
            QPushButton { 
                font-size: 14pt;
                font-weight: bold; 
                padding: 8px 30px; 
                color: palette(text);
                background-color: rgba(127, 127, 127, 0.3); 
                border: none; 
                border-radius: 4px; 
            }
            QPushButton:hover { background: #e0e0e0; color: #000; }
            QPushButton:disabled { 
                background-color: rgba(127, 127, 127, 0.3); 
                color: rgba(127, 127, 127, 0.8);
            }
        """)
        self.back_bnt.clicked.connect(self.on_back_press)

        self.next_bnt = QPushButton("Next Step")
        self.next_bnt.setEnabled(False)
        self.next_bnt.setStyleSheet("""
            QPushButton { 
                font-size: 14pt; 
                font-weight: bold; 
                padding: 8px 30px; 
                background-color: #0078d7; 
                color: white; 
                border-radius: 4px; 
                border: none;
            }
            QPushButton:hover { background-color: #0063b1; }
            QPushButton:disabled { 
                background-color: rgba(127, 127, 127, 0.3); 
                color: rgba(127, 127, 127, 0.8);
            }
        """)
        self.next_bnt.clicked.connect(self.on_next_press)

        footer_layout.addWidget(self.back_bnt)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.next_bnt)

        # main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        layout.addWidget(self.header_frame)

        # Wrapper for content to give it margin
        content_wrapper = QWidget()
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(30, 20, 30, 20)

        center_layout = QHBoxLayout()
        center_layout.addStretch(1)

        # self.stack_view.setMaximumWidth(700)
        center_layout.addWidget(self.stack_view)

        center_layout.addStretch(1)

        content_layout.addLayout(center_layout)

        layout.addWidget(content_wrapper, stretch=1)

        layout.addWidget(self.footer_frame)

        
        self.stack_view.currentChanged.connect(self.updateGeometry)
        self.stack_view.currentChanged.connect(self.adjustSize)

    def on_next_press(self):
        index = self.stack_view.currentIndex() + 1

        if index == 1:  # Moving to Settings
            if self.file_window.create_file():
                self.update_header(
                    2,
                    "Step 2: Connect Device",
                    "Select the serial port for the microcontroller.",
                )
                self.back_bnt.setEnabled(True)
                self.next_bnt.setEnabled(False)  # Wait for connection
            else:
                return

        elif index == 2:  # Moving to Time
            self.update_header(
                3,
                "Step 3: Timing Configuration",
                "Set integration time and reset parameters.",
            )

            if self.time_window.already_sent:
                self.next_bnt.setEnabled(True)
            else:
                self.next_bnt.setEnabled(False)

            self.time_window.update_label()
            self.next_bnt.setText("Start Measurement")

        else:  # Moving to Run
            self.change_to_running_window.emit()
            return

        self.stack_view.setCurrentIndex(index)

    def on_back_press(self):
        index = self.stack_view.currentIndex() - 1

        if index == 0:
            self.update_header(
                1, "Step 1: Data Setup", "Choose where to save your measurement data."
            )
            self.back_bnt.setEnabled(False)
            self.next_bnt.setEnabled(True)
        elif index == 1:
            self.update_header(
                2,
                "Step 2: Connect Device",
                "Select the serial port for the microcontroller.",
            )
            self.next_bnt.setText("Next Step")
            self.next_bnt.setEnabled(True)

        self.stack_view.setCurrentIndex(index)

    def update_header(self, step_num, title, subtitle):
        self.header_title.setText(title)
        self.header_subtitle.setText(subtitle)
        self.progress_bar.setValue(step_num)

    def connection_successfull(self):
        self.next_bnt.setEnabled(True)

    def sent_successfull(self):
        self.next_bnt.setEnabled(True)

    def disable_next(self):
        self.next_bnt.setEnabled(False)

    def restart_from_beginning(self):
        self.stack_view.setCurrentIndex(0)
        self.setting_window.restart_event()
        self.file_window.restart_event()

        # Reset Header
        self.update_header(
            1, "Step 1: Data Setup", "Choose where to save your measurement data."
        )
        self.back_bnt.setEnabled(False)
        self.next_bnt.setText("Next Step")
        self.disable_next()




# QStackedWidget set the width of all the widgets inside it to the 
# the width of the biggest widget
class DynamicStackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def sizeHint(self):
        # Only return the size hint of the current widget
        if self.currentWidget():
            return self.currentWidget().sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self):
        if self.currentWidget():
            return self.currentWidget().minimumSizeHint()
        return super().minimumSizeHint()