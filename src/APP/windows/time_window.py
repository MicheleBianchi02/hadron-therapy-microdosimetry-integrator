from model import current_session
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)
from serial_comm import serial_port
from utils import utils


class TimeWindow(QWidget):
    sent_successfull = pyqtSignal()
    editing_time = pyqtSignal()
    already_sent = False

    def __init__(self, simulate: bool) -> None:
        super().__init__()
        self.simulate = simulate
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QComboBox {
                background-color: palette(Base);
                color: palette(WindowText);
            }
            /* Abstract control the popup window */
            QComboBox QAbstractItemView {
                background-color: palette(Base);
                color: palette(WindowText);
                border: 1px solid palette(Mid);
                selection-background-color: palette(Highlight);
                selection-color: palette(HighlightedText);
                outline: 0;
            }
        """)
        self.icon_error = self.style().standardIcon(
            QStyle.StandardPixmap.SP_MessageBoxCritical
        )
        self.icon_success = self.style().standardIcon(
            QStyle.StandardPixmap.SP_DialogApplyButton
        )

        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet("""
            QFrame {
                background-color: #dfe3e8;   /* soft dark gray surface */
                border-radius: 8px;
            }
        """)
        self.final_int_time_label = QLabel("-")
        self.final_rst_time_label = QLabel("-")
        self.final_freq_label = QLabel("-")

        for lbl in [
            self.final_int_time_label,
            self.final_rst_time_label,
            self.final_freq_label,
        ]:
            lbl.setStyleSheet("font-size: 16pt; font-weight: bold; color: #2f3b45;")

        self.time_table = QTableWidget()
        self.time_table.setColumnCount(4)
        self.time_table.setHorizontalHeaderLabels(
            ["Preset Name [ms]", "Integration [ms]", "Reset [ms]", "Freq [Hz]"]
        )
        header = self.time_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.time_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.time_table.setMinimumWidth(500)


        self.time_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.time_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.time_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.time_table.setAlternatingRowColors(True)
        self.time_table.setShowGrid(False)
        self.time_table.verticalHeader().setVisible(False)
        self.time_table.setStyleSheet("""
            QTableWidget {
                font-size: 11pt;
                border: 1px solid #ccc;
                gridline-color: #ccc;
            }

            QHeaderView::section {
                font-size: 12pt;          /* slightly bigger header text */
                font-weight: bold;
                padding: 2px 5px;        /* vertical | horizontal padding */
                border: 1px solid #ccc;
                background-color: #f5f5f5;
            }

            QHeaderView::section:horizontal {
                padding-top: 8px;
                padding-bottom: 8px;
            }
        """)
        # self.time_table.setStyleSheet("""
        #     QTableWidget { font-size: 11pt; border: 1px solid #ccc; }
        # """)
        self.time_table.itemSelectionChanged.connect(self.on_table_selection)

        # --- manual inputs ---
        self.int_time = QLineEdit("1")
        self.rst_time = QLineEdit("1")
        self.magnitude_int = QComboBox()
        self.magnitude_int.setFixedWidth(60)
        self.magnitude_rst = QComboBox()
        self.magnitude_rst.setFixedWidth(60)
        self.mode_menu = QComboBox()

        for widget in [
            self.int_time,
            self.rst_time,
            self.magnitude_int,
            self.magnitude_rst,
            self.mode_menu,
        ]:
            widget.setStyleSheet("padding: 5px; font-size: 12pt;")

        self.magnitude_int.addItems(["s", "ms", "μs"])
        self.magnitude_int.setCurrentIndex(1)  # ms
        self.magnitude_rst.addItems(["s", "ms", "μs"])
        self.magnitude_rst.setCurrentIndex(2)  # us

        self.mode_menu.addItems(["Debug", "Operational"])
        self.mode_menu.setCurrentIndex(1)

        # Signals
        self.magnitude_int.currentIndexChanged.connect(self.on_manual_edit)
        self.int_time.textEdited.connect(self.on_manual_edit)
        self.magnitude_rst.currentIndexChanged.connect(self.on_manual_edit)
        self.rst_time.textEdited.connect(self.on_manual_edit)
        self.mode_menu.currentIndexChanged.connect(self.on_mode_change)

        # Toggle Button for Advanced
        self.advance_opt_bnt = QPushButton("Show Manual Configuration")
        self.advance_opt_bnt.setCheckable(True)
        self.advance_opt_bnt.setStyleSheet("""
            QPushButton { 
                text-align: left;
                padding: 8px;
                font-weight: bold;
                color: palette(text);
                border: none; 
            }
            QPushButton:checked { color: palette(text) }
            QPushButton:hover { background-color: #ccc; border-radius: 4px; }
        """)
        self.advance_opt_bnt.toggled.connect(self.on_toggle_advanced)

        self.advance_opt_widget = QWidget()
        self.advance_opt_widget.setVisible(False)

        # --- action buttons ---
        self.send_bnt = QPushButton(" Apply Configuration")
        self.send_bnt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_bnt.setStyleSheet("""
            QPushButton {
                background-color: #28a745; color: white; font-weight: bold; 
                padding: 12px 20px; font-size: 14pt; border-radius: 5px;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.send_bnt.clicked.connect(self.on_send_press)

        self.edit_bnt = QPushButton("Edit")
        self.edit_bnt.setVisible(False)
        self.edit_bnt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_bnt.setStyleSheet("""
            QPushButton {
                background-color: #ffc107; color: #333; font-weight: bold; 
                padding: 12px 20px; font-size: 14pt; border-radius: 5px;
            }
            QPushButton:hover { background-color: #e0a800; }
        """)
        self.edit_bnt.clicked.connect(self.on_edit_press)

        # --- status bar ---
        self.status_icon = QLabel()
        self.status_icon.setStyleSheet("border: none;")
        self.status_label = QLabel("Ready to configure")
        self.status_label.setStyleSheet(
            "color: #666; font-size: 11pt; font-style: italic; border: none;"
        )
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet(
            "background-color: #f8f9fa; border-radius: 4px; padding: 5px;"
        )
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_label, 1)
        self.status_frame.setVisible(False)

        self.setup_layout()
        self.fill_table()

        # Trigger initial calculation
        self.on_manual_edit()

    def setup_layout(self):
        master = QVBoxLayout()
        self.setLayout(master)

        # Summary Dashboard
        sum_layout = QHBoxLayout(self.summary_frame)

        def create_stat(title, widget):
            v = QVBoxLayout()
            t = QLabel(title)
            t.setStyleSheet(
                "color: #7f8c8d; font-size: 10pt; text-transform: uppercase; letter-spacing: 1px;"
            )
            v.addWidget(t)
            v.addWidget(widget)
            return v

        sum_layout.addLayout(create_stat("Integration", self.final_int_time_label))
        sum_layout.addLayout(create_stat("Reset Time", self.final_rst_time_label))
        sum_layout.addLayout(create_stat("Sample Frequency", self.final_freq_label))

        master.addWidget(self.summary_frame)
        master.addSpacing(15)

        # Main Content (Scrollable if screen is small)
        scroll = QScrollArea()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # Disable horizontal scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # -- Presets Group --
        preset_group = QGroupBox("Quick Presets")
        preset_group.setStyleSheet("QGroupBox { font-weight: bold; font-size: 12pt; }")
        pg_layout = QVBoxLayout()
        pg_layout.addWidget(self.time_table)
        preset_group.setLayout(pg_layout)
        content_layout.addWidget(preset_group)

        # -- Manual/Advanced Group --
        content_layout.addWidget(self.advance_opt_bnt)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        # Int Row
        r1 = QHBoxLayout()
        r1.addWidget(self.int_time)
        r1.addWidget(self.magnitude_int)
        form_layout.addRow("Integration Time:", r1)

        # Reset Row
        r2 = QHBoxLayout()
        r2.addWidget(self.rst_time)
        r2.addWidget(self.magnitude_rst)
        form_layout.addRow("Reset Time:", r2)

        # Mode Row
        form_layout.addRow("Operational Mode:", self.mode_menu)

        self.advance_opt_widget.setLayout(form_layout)
        content_layout.addWidget(self.advance_opt_widget)

        content_layout.addStretch(1)
        scroll.setWidget(content_widget)
        master.addWidget(scroll)

        # Footer (Action Buttons)
        footer = QHBoxLayout()
        footer.addWidget(self.status_frame, 1)
        footer.addWidget(self.edit_bnt)
        footer.addWidget(self.send_bnt)
        master.addLayout(footer)

    def fill_table(self):
        def int_time(value):
            value, _, _, _ = utils.get_int_time(value)
            return value * 1000

        def rst_time(value):
            value, _, _ = utils.get_reset_time(value)
            return value * 1000

        table_data = {
            "Long Integration": {"int": 100, "rst": 0, "freq": 0},
            "Standard": {"int": 10, "rst": 0, "freq": 0},
            "Fast": {"int": 1, "rst": 0, "freq": 0},
            "Ultra Fast": {"int": 0, "rst": 0, "freq": 0},  # 30us
        }

        self.time_table.setRowCount(len(table_data))

        row = 0
        for name, val in table_data.items():
            # Recalculate real values
            real_int = int_time(val["int"] / 1000)
            real_rst = rst_time(val["rst"] / 1000)
            real_freq = 1000 / (real_int + real_rst) if (real_int + real_rst) > 0 else 0

            self.time_table.setItem(row, 0, QTableWidgetItem(name))
            self.time_table.setItem(row, 1, QTableWidgetItem(f"{real_int:.4f}"))
            self.time_table.setItem(row, 2, QTableWidgetItem(f"{real_rst:.4f}"))
            self.time_table.setItem(row, 3, QTableWidgetItem(f"{real_freq:.4f}"))

            # Store raw data in the first item for easy retrieval
            self.time_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole, (real_int, real_rst)
            )
            row += 1

        # Resize
        header = self.time_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        # self.time_table.setFixedHeight(180)  # Fixed height for cleanliness

    def on_toggle_advanced(self, checked):
        self.advance_opt_widget.setVisible(checked)
        if checked:
            self.advance_opt_bnt.setText("Hide Manual Configuration")
            # Clear table selection to indicate manual mode
            self.time_table.clearSelection()
        else:
            self.advance_opt_bnt.setText("Show Manual Configuration")

    def on_table_selection(self):
        items = self.time_table.selectedItems()
        if not items:
            return

        # Get raw values stored in UserRole in ms
        val_int, val_rst = self.time_table.item(self.time_table.currentRow(), 0).data(
            Qt.ItemDataRole.UserRole
        )

        # Block signals to prevent recursion loops
        self.int_time.blockSignals(True)
        self.rst_time.blockSignals(True)
        self.magnitude_int.blockSignals(True)
        self.magnitude_rst.blockSignals(True)

        # Update Manual Fields to match selection (User feedback)
        self.int_time.setText(str(val_int))
        self.magnitude_int.setCurrentIndex(1)  # ms
        self.rst_time.setText(str(val_rst))
        self.magnitude_rst.setCurrentIndex(1)  # ms

        self.int_time.blockSignals(False)
        self.rst_time.blockSignals(False)
        self.magnitude_int.blockSignals(False)
        self.magnitude_rst.blockSignals(False)

        self.on_manual_edit()

    def on_manual_edit(self):
        # This handles input from Text boxes OR Table updates
        self.editing_time.emit()
        self.send_bnt.setEnabled(True)

        # If user is typing manually, clear table selection
        if self.sender() in [
            self.int_time,
            self.rst_time,
            self.magnitude_int,
            self.magnitude_rst,
        ]:
            self.time_table.blockSignals(True)
            self.time_table.clearSelection()
            self.time_table.blockSignals(False)

        try:
            # integration
            t_int = ""
            for c in self.int_time.text():
                if c.isdecimal() or (c == "." and "." not in t_int):
                    t_int += c

            self.int_time.setText(t_int)
            t_int = float(t_int)
            mag_i = self.magnitude_int.currentText()
            mult_i = 1 if mag_i == "s" else (1e-3 if mag_i == "ms" else 1e-6)
            final_int = t_int * mult_i

            (
                current_session.int_time,
                self.timerU_int,
                self.timerH_int,
                self.timerL_int,
            ) = utils.get_int_time(final_int)

            # reset
            t_rst = ""
            for c in self.rst_time.text():
                if c.isdecimal() or (c == "." and "." not in t_rst):
                    t_rst += c

            self.rst_time.setText(t_rst)
            t_rst = float(t_rst)
            mag_r = self.magnitude_rst.currentText()
            mult_r = 1 if mag_r == "s" else (1e-3 if mag_r == "ms" else 1e-6)
            final_rst = t_rst * mult_r

            current_session.reset_time, self.timerH_rst, self.timerL_rst = (
                utils.get_reset_time(final_rst)
            )

            # Frequency
            current_session.sample_freq = (
                1 / (current_session.int_time + current_session.reset_time)
                if (current_session.int_time + current_session.reset_time) > 0
                else 0
            )

            self.update_label()
        except ValueError:
            pass  # Handle empty strings or parse errors gracefully

    def on_mode_change(self):
        current_session.debug_mode = self.mode_menu.currentText() == "Debug"
        self.on_manual_edit()  # Re-trigger

    def update_label(self):
        i_ms = current_session.int_time * 1000
        r_ms = current_session.reset_time * 1000
        self.final_int_time_label.setText(f"{i_ms:.4f} ms")
        self.final_rst_time_label.setText(f"{r_ms:.4f} ms")
        self.final_freq_label.setText(f"{current_session.sample_freq:.4f} Hz")

    def on_send_press(self):
        self.status_frame.setVisible(True)
        # self.status_label.setText("Sending configuration...")
        # self.status_frame.setStyleSheet("background-color: #e6f7ff; color: #0050b3;")
        # QFrame.repaint(self)

        success = False
        if self.simulate:
            success = True
        else:
            # Send Timers
            if serial_port.send_timer(
                self.timerU_int,
                self.timerH_int,
                self.timerL_int,
                self.timerH_rst,
                self.timerL_rst,
            ):
                # Send Mode
                if current_session.debug_mode:
                    success = serial_port.send_debug_mode()
                else:
                    success = serial_port.send_production_mode()

        if success:
            self.status_frame.setStyleSheet(
                "background-color: #d4edda; border: 1px solid #c3e6cb; border-radius: 5px;"
            )
            self.status_label.setText("Configuration Applied Successfully")
            self.status_label.setStyleSheet(
                "color: #155724; font-weight: bold; font-size: 12pt; border: none;"
            )
            self.status_icon.setPixmap(self.icon_success.pixmap(24, 24))
            self.already_sent = True
            self.sent_successfull.emit()

            self.toggle_ui_lock(locked=True)

            print("Parameter sent to the PIC:")
            print(f"timerU_int: {self.timerU_int}")
            print(f"timerH_int: {self.timerH_int}")
            print(f"timerL_int: {self.timerL_int}")
            print(f"timerH_reset: {self.timerH_rst}")
            print(f"timerL_reset: {self.timerL_rst}")
        else:
            self.status_frame.setStyleSheet(
                "background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px;"
            )
            self.status_label.setText("Error: Failed to send data. Check connection.")
            self.status_label.setStyleSheet(
                "color: #721c24; font-weight: bold; font-size: 12pt; border: none;"
            )
            self.status_icon.setPixmap(self.icon_error.pixmap(24, 24))
            self.already_sent = False

    def toggle_ui_lock(self, locked: bool):
        self.send_bnt.setVisible(not locked)
        self.edit_bnt.setVisible(locked)
        self.time_table.setEnabled(not locked)
        self.advance_opt_widget.setEnabled(not locked)
        self.advance_opt_bnt.setEnabled(not locked)

    def on_edit_press(self):
        self.toggle_ui_lock(locked=False)
        self.status_frame.setVisible(False)
        self.editing_time.emit()
