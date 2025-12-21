import os

from model import current_session
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)


class FilePathWindow(QWidget):
    enable_next = pyqtSignal()
    load_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)  # Enable Drag and Drop
        self.init_ui()

    def init_ui(self):

        icon_folder = self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        icon_file = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)


        # --- Browse Button ---
        self.browse_bnt = QPushButton("Browse...")
        self.browse_bnt.setIcon(icon_folder)
        self.browse_bnt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_bnt.clicked.connect(self.on_browse_press)
        self.browse_bnt.setStyleSheet("""
            QPushButton {
                padding: 6px 15px;
                font-size: 14pt;
                background-color: #0078d7;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #005a9e; }
        """)

        current_session.file_path = None

        # --- Error / Status Feedback ---
        self.error_message = QLabel("")
        self.error_message.setStyleSheet(
            "color: #d9534f; font-size: 11pt; margin-top: 5px;"
        )
        self.error_message.setVisible(False)

        # --- File Path Line ---
        self.file_path_line = QLineEdit(current_session.file_path)
        self.file_path_line.setPlaceholderText(
            "Select a location or Drag & Drop a file here..."
        )
        self.file_path_line.setReadOnly(True)
        self.file_path_line.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                font-size: 12pt;
                border: 1px solid #ccc;
                border-radius: 4px;
                /* background-color: #f9f9f9; */
            }
            QLineEdit:focus { border: 1px solid #0078d7; }
        """)
        self.file_path_line.setMinimumWidth(400)

        # --- Save Later Button ---
        self.no_save_bnt = QPushButton("Don't save to file (Live view only)")
        self.no_save_bnt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.no_save_bnt.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #555;
                font-size: 11pt;
                text-align: left;
                border: none;
            }
            QPushButton:hover { color: #000; text-decoration: underline; }
            QPushButton:disabled { color: #aaa; text-decoration: none; }
        """)
        self.no_save_bnt.clicked.connect(self.on_save_later_press)

        # --- Load Button ---
        self.load_bnt = QPushButton("Load Existing Data")
        self.load_bnt.setIcon(icon_file)
        self.load_bnt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.load_bnt.setStyleSheet("""
            QPushButton {
                padding: 10px;
                font-size: 14pt;
                border: 1px solid #aaa;
                border-radius: 4px;
                /* background-color: #f0f0f0; */
            }
            QPushButton:hover { background-color: #ccc; }
        """)
        self.load_bnt.clicked.connect(self.on_load_press)

        self.setup_ui()

    def setup_ui(self):
        master = QVBoxLayout()
        master.setSpacing(20)
        self.setLayout(master)

        # --- new measurement ---
        group_save = QGroupBox("New Measurement")
        group_save.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14pt;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        save_layout = QVBoxLayout()

        # Row for Input and Browse
        input_row = QHBoxLayout()
        input_row.addWidget(self.file_path_line)
        input_row.addWidget(self.browse_bnt)

        save_layout.addLayout(input_row)
        save_layout.addWidget(self.error_message)
        save_layout.addWidget(self.no_save_bnt)
        group_save.setLayout(save_layout)

        # --- or divider ---
        or_label = QLabel("- OR -")
        or_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        or_label.setStyleSheet("color: #888; font-weight: bold;")

        # --- load data ---
        group_load = QGroupBox("Analysis Mode")
        group_load.setStyleSheet("""
             QGroupBox {
                font-weight: bold;
                font-size: 12pt;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
             } 
             QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        load_layout = QVBoxLayout()
        load_layout.addWidget(self.load_bnt)
        group_load.setLayout(load_layout)

        master.addStretch(1)
        master.addWidget(group_save)
        master.addSpacing(10)
        master.addWidget(or_label)
        master.addSpacing(10)
        master.addWidget(group_load)
        master.addStretch(2)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            # If it exists, assume loading. If not (or user wants to overwrite), set as
            # save path.
            # For this context, we'll treat it as setting the save path if it ends in CSV
            path = files[0]
            current_session.file_path = path
            self.file_path_line.setText(path)
            self._validate_ui_state(success=True)
            self.enable_next.emit()

    def on_browse_press(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Save Measurement Data")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilters(
            ["CSV Files (*.csv)", "Text Files (*.txt)", "Data Files (*.dat)"]
        )
        dialog.setDefaultSuffix("csv")

        start_path = os.path.expanduser("~")
        dialog.setDirectory(start_path)

        if current_session.file_path is None:
            dialog.selectFile("measurement.csv")
        else:
            dialog.selectFile(current_session.file_path)

        if dialog.exec():
            current_session.file_path = dialog.selectedFiles()[0]
            self.file_path_line.setText(current_session.file_path)
            self._validate_ui_state(success=True)
            self.enable_next.emit()

    def _validate_ui_state(self, success: bool):
        """Helper to update UI visuals based on state"""
        if success:
            self.error_message.setVisible(False)
            self.file_path_line.setStyleSheet("""
                QLineEdit {
                    padding: 8px;
                    font-size: 12pt;
                    border-radius: 4px;
                    /* background-color: #f9f9f9; */
                    border: 1px solid #28a745; 
                }
            """)
            self.no_save_bnt.setEnabled(True)
        else:
            self.file_path_line.setStyleSheet("""
                QLineEdit {
                    padding: 8px;
                    font-size: 12pt;
                    border-radius: 4px;
                    /* background-color: #fff0f0; */
                    border: 1px solid #d9534f;
                }
            """)

    def restart_file_window(self):
        """Called when restarting the measurement"""
        current_session.file_path = None
        self.error_message.setVisible(False)
        # Reset Style
        self.file_path_line.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                font-size: 12pt;
                border-radius: 4px;
                /* background-color: #f9f9f9; */
                border: 1px solid #ccc;
            }
        """)
        self.file_path_line.clear()

    def create_file(self) -> bool:
        """Create an empty file at the file_path location.
        A bool value is returned wheter the operation was successful or not.
        Called when changing window (pressing next).
        """
        if current_session.file_path is None:
            return True

        try:
            if not current_session.file_path:
                self.error_message.setText("Please add a valid file name")
                self.error_message.setVisible(True)
                self._validate_ui_state(success=False)
                return False

            with open(current_session.file_path, "w"):
                pass

            self.error_message.setVisible(False)
            return True

        except PermissionError:
            self.error_message.setText(
                "Permission denied: Cannot write to this location."
            )
            self.error_message.setVisible(True)
            self._validate_ui_state(success=False)
            return False
        except OSError:
            self.error_message.setText("System error: Please try a different path.")
            self.error_message.setVisible(True)
            self._validate_ui_state(success=False)
            return False

    def on_save_later_press(self):
        self.file_path_line.setText("Session will not be saved (Live Only)")
        self.file_path_line.setStyleSheet(
            "QLineEdit { color: #888; font-style: italic; border: 1px #ccc; }"
        )
        current_session.file_path = None
        self.no_save_bnt.setEnabled(False)
        self.error_message.setVisible(False)
        self.enable_next.emit()

    def on_load_press(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Load Measurement Data")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilters(
            ["CSV Files (*.csv)", "Text Files (*.txt)", "Data Files (*.dat)"]
        )

        start_path = os.path.expanduser("~")
        dialog.setDirectory(start_path)

        if dialog.exec():
            file_path = dialog.selectedFiles()[0]
            if file_path:
                self.load_signal.emit(file_path)

    def restart_event(self):
        self.restart_file_window()
        self.no_save_bnt.setEnabled(True)
