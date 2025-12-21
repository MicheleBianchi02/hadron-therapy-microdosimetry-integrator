import csv
import os
import time

import numpy as np
import pyqtgraph as pg
from constants import NUM_BINS, UPDATE_INTERVAL_MS
from model import current_session
from numpy._typing import NDArray
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from serial_comm import serial_port
from utils import utils


class RunningWindow(QWidget):
    restart_signal = pyqtSignal()

    def __init__(self, simulate: bool) -> None:
        super().__init__()

        self.simulate = simulate
        self.rate = None
        self.init_variables()
        self.time_chart_type = "moving"

        # Create a QTimer to periodically check for new data
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_ui)
        self.init_ui()

    def init_variables(self):
        self.chart_type = "mc"

        self.BUFFER_SIZE = 2**17
        self.BUFFER_SIZE_DEBUG = 2**17

        self.already_saved = False

        self.bar_data_ch1 = np.zeros(NUM_BINS, dtype=int)
        self.bar_data_ch2 = np.zeros(NUM_BINS, dtype=int)
        self.data = np.zeros((self.BUFFER_SIZE, 2), dtype=float)
        self.start_data = np.zeros((self.BUFFER_SIZE_DEBUG, 2), dtype=float)
        self.stop_data = np.zeros((self.BUFFER_SIZE_DEBUG, 2), dtype=float)

        self.is_running = False
        self.already_runned = False

        self.ptr = 0

        self.timestamp = 0

        self.mean_value_ch1 = 0
        self.mean_value_ch2 = 0
        self.temp_values = []
        self.variance_ch1 = 0
        self.variance_ch2 = 0
        self.n_overflow_ch1 = 0
        self.n_overflow_ch2 = 0
        self.count = 0

        self.n_point_moving_win = 10_000
        self.starting_time = 0

    def init_ui(self):
        # --- Common Styles & Icons ---
        self.icon_start = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self.icon_stop = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        self.icon_restart = self.style().standardIcon(
            QStyle.StandardPixmap.SP_BrowserReload
        )
        self.icon_save = self.style().standardIcon(
            QStyle.StandardPixmap.SP_DialogSaveButton
        )
        self.icon_load = self.style().standardIcon(
            QStyle.StandardPixmap.SP_DialogOpenButton
        )

        self.setting_tab = RunSettingTab()
        self.setting_tab.update_signal.connect(self.on_update_setting)

        # --- MenuBar ---
        self.menu_bar = QMenuBar()
        self.options_menu = self.menu_bar.addMenu("File")

        self.save_file_action = QAction(self.icon_save, "Save Data", self)
        self.options_menu.addAction(self.save_file_action)
        self.save_file_action.triggered.connect(self.on_save_press)

        self.load_action = QAction(self.icon_load, "Load Data", self)
        self.options_menu.addAction(self.load_action)
        self.load_action.triggered.connect(self.on_load_press)

        self.view_menu = self.menu_bar.addMenu("View")
        self.show_setting = QAction("Show Settings Panel", self)
        self.show_setting.setCheckable(True)
        self.show_setting.setChecked(True)
        self.show_setting.toggled.connect(self.toggle_settings_panel)
        self.view_menu.addAction(self.show_setting)

        self.show_result = QAction("Show Results Panel")
        self.show_result.setCheckable(True)
        self.show_result.setChecked(True)
        self.show_result.toggled.connect(
            lambda state: self.result_table.setVisible(state)
        )
        self.view_menu.addAction(self.show_result)

        # --- Top Toolbar ---
        self.toolbar = QFrame()
        self.toolbar.setStyleSheet("""
            QFrame { 
                /* background-color: #f5f5f5; border-bottom: 1px solid #d0d0d0; */
                background-color: palette(Base);
                border-bottom: 1px solid palette(Mid);
                max-height: 60px;
            }
        """)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)

        # Controls
        self.start_bnt = QPushButton("Start Measure")
        # Initial style setup (will be overwritten by change_start_bnt)
        self.start_bnt.setIcon(self.icon_start)
        self.start_bnt.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_bnt.clicked.connect(self.on_start_press)

        self.change_start_bnt("start", hide=False, enable=True)

        self.restart_bnt = QPushButton()
        self.restart_bnt.setIcon(self.icon_restart)
        self.restart_bnt.setToolTip("Restart")
        self.restart_bnt.clicked.connect(self.on_restart_press)
        self.restart_bnt.setStyleSheet("padding: 8px;")

        # Metrics Labels
        self.measuring_time_label = QLabel("0.0 s")
        self.measuring_time_label.setStyleSheet(
            "font-size: 16pt; font-weight: bold; color: palette(text); margin-left: 10px;"
        )

        # Info Badge Widget
        self.info_widget = QWidget()
        info_layout = QHBoxLayout(self.info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)

        def create_badge(label, value_widget):
            container = QFrame()
            # Removed vertical padding to make it smaller
            container.setStyleSheet(
                "background: #dfe3e8; border: none; border-radius: 4px;"
            )
            lay = QHBoxLayout(container)
            lay.setContentsMargins(8, 2, 8, 2)
            lay.setSpacing(5)
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #666; font-size: 12pt; font-weight: bold;")
            val = value_widget
            val.setStyleSheet("color: #2f3b45; font-size: 12pt;")
            lay.addWidget(lbl)
            lay.addWidget(val)
            return container

        self.int_time_label = QLabel("-")
        self.rst_time_label = QLabel("-")
        self.sample_freq_label = QLabel("-")

        info_layout.addWidget(create_badge("INTEGRATION:", self.int_time_label))
        info_layout.addWidget(create_badge("RESET:", self.rst_time_label))
        info_layout.addWidget(create_badge("FREQUENCY:", self.sample_freq_label))

        toolbar_layout.addWidget(self.start_bnt)
        toolbar_layout.addSpacing(10)
        toolbar_layout.addWidget(self.restart_bnt)
        toolbar_layout.addSpacing(20)
        toolbar_layout.addWidget(QLabel("Time:"))
        toolbar_layout.addWidget(self.measuring_time_label)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.info_widget)

        # --- Chart Control Strip ---
        self.chart_controls = QFrame()
        cc_layout = QHBoxLayout(self.chart_controls)
        cc_layout.setContentsMargins(0, 5, 0, 5)

        self.view_hist_btn = QPushButton("Histogram")
        self.view_hist_btn.setCheckable(True)
        self.view_hist_btn.setChecked(True)
        self.view_hist_btn.clicked.connect(self.on_left_press)

        self.view_time_btn = QPushButton("Time Series")
        self.view_time_btn.setCheckable(True)
        self.view_time_btn.clicked.connect(self.on_right_press)

        self.update_view_buttons()

        # Time Window Controls
        self.moving_widget = QWidget()
        mw_layout = QHBoxLayout(self.moving_widget)
        mw_layout.setContentsMargins(0, 0, 0, 0)
        mw_layout.addWidget(QLabel("Window [s]:"))

        self.n_point_moving_line = QDoubleSpinBox()
        self.n_point_moving_line.setDecimals(1)
        self.n_point_moving_line.setRange(0, 1_000_000)
        # self.n_point_moving_line.setValue(10)
        self.n_point_moving_line.valueChanged.connect(self.on_change_n_point_moving)
        self.n_point_moving_line.setFixedWidth(80)
        mw_layout.addWidget(self.n_point_moving_line)
        self.moving_widget.setVisible(False)

        self.chart_time_mode_box = QComboBox()
        self.chart_time_mode_box.addItems(["Moving Window", "Full History"])
        self.chart_time_mode_box.currentIndexChanged.connect(
            self.on_change_time_chart_type
        )
        self.chart_time_mode_box.setVisible(False)

        self.memory_usage_widget = QWidget()
        memory_layout = QHBoxLayout(self.memory_usage_widget)
        memory_layout.setContentsMargins(0, 0, 0, 0)
        info_btn = QToolButton()
        info_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        )
        info_btn.setAutoRaise(True)  # shows only on hover
        info_btn.setToolTip("Memory usage details")
        info_btn.clicked.connect(self.on_mem_info_press)
        memory_layout.addWidget(info_btn)

        memory_layout.addWidget(QLabel("Memory [MB]"), stretch=4)
        self.memory_label = QLabel(None)
        memory_layout.addWidget(self.memory_label, stretch=4)

        cc_layout.addWidget(self.view_hist_btn)
        cc_layout.addWidget(self.view_time_btn)
        cc_layout.addSpacing(20)
        cc_layout.addWidget(self.chart_time_mode_box)
        cc_layout.addWidget(self.moving_widget)
        cc_layout.addStretch(1)
        cc_layout.addWidget(self.memory_usage_widget)

        # --- Plot Widget ---
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.legend = self.plot_widget.addLegend()
        self.legend.anchor(itemPos=(0, 1), parentPos=(0, 1), offset=(10, -10))
        self.legend.setBrush(pg.mkBrush(255, 255, 255, 255))
        self.legend.setPen("k")
        self.legend.setLabelTextColor("k")

        self.init_plot_items()

        # --- Results Table ---
        self.result_table = QTableWidget()
        self.setup_result_table()

        # --- Layout Assembly ---
        self.setup_window()

    def update_view_buttons(self):
        active_style = """
            QPushButton { 
                background-color: #0078d7;
                color: white;
                border: 1px solid #005a9e;
                border-radius: 0px;
                padding: 5px 20px;
                font-weight: bold;
            }
        """
        inactive_style = """
            QPushButton { 
                background-color: #f8f9fa;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 0px;
                padding: 5px 20px;
            }
            QPushButton:hover { background-color: #e2e6ea; }
        """

        left_active = (
            active_style
            + "QPushButton { border-top-left-radius: 4px; border-bottom-left-radius: 4px; }"
        )
        left_inactive = (
            inactive_style
            + "QPushButton { border-top-left-radius: 4px; border-bottom-left-radius: 4px; }"
        )
        right_active = (
            active_style
            + "QPushButton { border-top-right-radius: 4px; border-bottom-right-radius: 4px; border-left: none; }"
        )
        right_inactive = (
            inactive_style
            + "QPushButton { border-top-right-radius: 4px; border-bottom-right-radius: 4px;}"
        )

        if self.chart_type == "mc":
            self.view_hist_btn.setStyleSheet(left_active)
            self.view_time_btn.setStyleSheet(right_inactive)
            self.view_hist_btn.setChecked(True)
            self.view_time_btn.setChecked(False)
        else:
            self.view_hist_btn.setStyleSheet(left_inactive)
            self.view_time_btn.setStyleSheet(right_active)
            self.view_hist_btn.setChecked(False)
            self.view_time_btn.setChecked(True)

    def init_plot_items(self):
        self.mca_x_axis = np.arange(NUM_BINS + 1)
        self.mca_item_ch1 = pg.PlotCurveItem(
            self.mca_x_axis,
            np.zeros(NUM_BINS),
            pen=pg.mkPen(color="#0078d7", width=2),
            brush=pg.mkBrush(color="#0078d7"),
            stepMode=True,
            fillLevel=0,
            name="CH 1",
        )
        self.mca_item_ch2 = pg.PlotCurveItem(
            self.mca_x_axis,
            np.zeros(NUM_BINS),
            pen=pg.mkPen(color="#d9534f", width=2),
            brush=pg.mkBrush(color="#d9534f"),
            stepMode=True,
            fillLevel=0,
            name="CH 2",
        )

        self.line_item_ch1 = pg.PlotDataItem(
            pen=pg.mkPen("#0078d7", width=1), name="CH 1"
        )
        self.line_item_ch2 = pg.PlotDataItem(
            pen=pg.mkPen("#d9534f", width=1), name="CH 2"
        )

        self.start_line_item_ch1 = pg.PlotDataItem(
            pen=pg.mkPen(color=(0, 0, 139), width=1), name="Start CH1"
        )  # darker blue
        self.stop_line_item_ch1 = pg.PlotDataItem(
            pen=pg.mkPen(color=(135, 206, 250), width=1), name="Stop CH1"
        )  # cyan
        self.start_line_item_ch2 = pg.PlotDataItem(
            pen=pg.mkPen(color="g", width=1), name="Start CH2"
        )
        self.stop_line_item_ch2 = pg.PlotDataItem(
            pen=pg.mkPen(color="m", width=1), name="Stop CH2"
        )

        self.nan_marker_item_ch1 = None
        self.nan_marker_item_ch2 = None

        self.init_mc_chart()

    def setup_result_table(self):
        columns = [
            "",
            "Mean [Ch]",
            "Mean [pC]",
            "Var [Ch²]",
            "Var [pC²]",
            "StdDev [Ch]",
            "StdDev [pC]",
            "Count",
            "Errors",
        ]
        self.result_table.setColumnCount(len(columns))
        self.result_table.setRowCount(2)
        self.result_table.setHorizontalHeaderLabels(columns)
        self.result_table.verticalHeader().hide()

        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.result_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.result_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.result_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        self.result_table.setShowGrid(True)
        self.result_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.result_table.setStyleSheet("""
            QTableWidget {
                    background-color: palette(Base);
                    alternate-background-color: palette(AlternateBase);
                    gridline-color: palette(Midlight);
                    border: 1px solid palette(Mid);
                    border-radius: 9px;
                    font-size: 12pt;
                }
            QTableWidget::item {
                border-color: palette(Dark);
                padding-left: 5px;
                padding-right: 5px;
                padding-top: 2px;
                padding-bottom: 2px;
                
                /* Removes the dotted focus line */
                outline: 0;
            }

            QTableWidget::item:selected {
                background-color: palette(Highlight);
                color: palette(HighlightedText);
            }

            QHeaderView::section {
                background-color: palette(Button);
                color: palette(ButtonText);
                padding: 5px;
                font-weight: bold;
                border: none;
                
            }

            QTableCornerButton::section {
                background-color: palette(Button);
                border: none;
            }
        """)

        self.result_table.setItem(0, 0, QTableWidgetItem("CH 1"))
        self.result_table.setItem(1, 0, QTableWidgetItem("CH 2"))
        for c in range(1, len(columns)):
            item1 = QTableWidgetItem("0")
            item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item2 = QTableWidgetItem("0")
            item2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.result_table.setItem(0, c, item1)
            self.result_table.setItem(1, c, item2)

        self.result_table.setFixedHeight(110)

    def setup_window(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setLayout(main_layout)

        main_layout.addWidget(self.menu_bar)
        main_layout.addWidget(self.toolbar)

        central_layout = QHBoxLayout()

        # --- left side (Controls + Plot + Table) ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 5, 10, 5)

        left_layout.addWidget(self.chart_controls)
        left_layout.addWidget(self.plot_widget, stretch=10)
        left_layout.addWidget(self.result_table, stretch=0)

        central_layout.addWidget(left_widget, stretch=10)

        # --- right side (Settings only) ---
        right_widget = QWidget()
        self.right_widget = right_widget
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 5, 5, 5)

        self.sidebar_tabs = QTabWidget()
        self.sidebar_tabs.addTab(self.setting_tab, "Settings")

        right_layout.addWidget(self.sidebar_tabs)

        central_layout.addWidget(right_widget)

        main_layout.addLayout(central_layout, stretch=10)

    # =======================================================
    # logic
    # =======================================================

    def on_start_press(self):
        if not self.is_running:
            if self.simulate:
                self.rate = 10**-3 / (
                    current_session.int_time + current_session.reset_time
                )
                # self.rate *= 1000
                print(f"Simulating a rate of {self.rate} measures/ms for each channel")
            else:
                response = serial_port.send_start()
                if not response:
                    QMessageBox.critical(self, "Error", "Start command failed.")
                    return

            utils.start_receiving(simulate=self.simulate, rate=self.rate)
            self.init_variables()
            self.starting_time = time.time()
            self.is_running = True
            self.already_runned = True

            self.change_start_bnt("stop", hide=False, enable=True)
            self.restart_bnt.setEnabled(False)

            if current_session.file_path is None:
                self.already_saved = False
            else:
                self.already_saved = True
                first_line = (
                    f"integration time [s]: {current_session.int_time}, "
                    f"reset time [s]: {current_session.reset_time}, "
                    f"sample frequency [Hz]: {current_session.sample_freq}"
                )
                self._write_to_file(current_session.file_path, first_line, "w")

            if self.chart_type == "mc":
                self.init_mc_chart(update=True)
            elif self.chart_type == "time":
                self.init_time_chart(update=True)

            self._update_ui(update_time=True)
            self.timer.start(UPDATE_INTERVAL_MS)
        else:
            self.on_stop_press()

    def on_stop_press(self):
        # this already wait that the thread stop to run. So this may block the
        # UI for a certain time (equal to the serial timeout ~100ms)
        response = utils.stop_receiving(not self.simulate)
        if not response:
            QMessageBox.critical(self, "Error", "Stop command failed.")
            return

        if self.already_runned:
            self._update_ui(update_time=True)
            self.is_running = False
            self.change_start_bnt(None, hide=True, enable=False)
            self.timer.stop()
            self.restart_bnt.setEnabled(True)

        self.change_start_bnt(None, hide=True, enable=False)

    def _update_ui(self, update_time: bool = True):
        try:
            new_data = utils.get_latest_data()
        except RuntimeError as e:
            print(f"Error: {str(e)}")
            self.is_running = False
            self.change_start_bnt(None, hide=True, enable=False)
            self.timer.stop()
            new_data = []

        measure_time = round((time.time() - self.starting_time), 1)
        if update_time:
            self.measuring_time_label.setText(f"{measure_time} s")

        if not new_data or new_data is None:
            return

        if current_session.debug_mode:
            start_value, stop_value, new_data = self.store_data(new_data)
        else:
            new_data = self.store_data(new_data)

        # e.g. new_data =
        # [ [ch1_1, ch2_1],
        #   [ch1_2, ch2_2],
        #   ...
        #   [ch1_n, ch2_n]
        # ]
        # it is an array of array (matrix)

        # from here new data is a matrix nx2 where the first columns represent ch1 and ch2

        self.fill_result_table(new_data)

        # float is 8 bytes. times 2 because we have two channels
        size = (self.BUFFER_SIZE * 8 + 2 * self.BUFFER_SIZE_DEBUG * 8) * 2
        self.memory_label.setText(str(int(size / 1e6)))

        # size2 = (
        #     sys.getsizeof(self.data)
        #     + sys.getsizeof(self.start_data)
        #     + sys.getsizeof(self.stop_data)
        # )

        if self.chart_type == "mc":
            self.show_mc()
        elif self.chart_type == "time":
            self.show_time()

        if current_session.file_path is not None:
            if current_session.debug_mode:
                self._write_to_file(
                    current_session.file_path, (start_value, stop_value), "a"
                )
            else:
                self._write_to_file(current_session.file_path, new_data, "a")

    # =======================================================
    # plot
    # =======================================================

    def init_mc_chart(self, update: bool = False):
        """Initialize/Update the multichannel chart. If update is True,
        the chart is simply updated, therefore hidden lines will remain hidden."""
        if not update:
            self.safeAdd(self.mca_item_ch1)
            self.safeAdd(self.mca_item_ch2)
            self.safeRemove(self.line_item_ch1)
            self.safeRemove(self.line_item_ch2)
            self.safeRemove(self.start_line_item_ch1)
            self.safeRemove(self.stop_line_item_ch1)
            self.safeRemove(self.start_line_item_ch2)
            self.safeRemove(self.stop_line_item_ch2)

        self.chart_time_mode_box.setVisible(False)
        self.moving_widget.setVisible(False)
        self.remove_overflow_marker()
        self.plot_widget.setLabel("left", "Counts")
        if self.setting_tab.show_type == self.setting_tab.CHANNEL:
            self.plot_widget.setXRange(0, NUM_BINS + 1)
            self.plot_widget.setLabel("bottom", "Channel")
        elif self.setting_tab.show_type == self.setting_tab.CHARGE:
            max_charge = (
                max(
                    [
                        self.setting_tab.capacitance_pf_ch1,
                        self.setting_tab.capacitance_pf_ch2,
                    ]
                )
                * self.setting_tab.adc_range
            )
            self.plot_widget.setXRange(0, max_charge)
            self.plot_widget.setLabel("bottom", "Charge [pC]")

        self.plot_widget.getAxis("bottom").setScale(1)
        self.plot_widget.setYRange(0, 10)
        self.plot_widget.enableAutoRange(pg.ViewBox.YAxis)

    def init_time_chart(self, update: bool = False):
        """Initialize/Update the time chart. If update is True, the chart is simply
        updated, therefore hidden lines will remain hidden."""
        self.chart_time_mode_box.setVisible(True)
        if not update:
            self.safeRemove(self.mca_item_ch1)
            self.safeRemove(self.mca_item_ch2)
            self.safeAdd(self.line_item_ch1)
            self.safeAdd(self.line_item_ch2)

            if current_session.debug_mode:
                self.safeAdd(self.start_line_item_ch1)
                self.safeAdd(self.stop_line_item_ch1)
                self.safeAdd(self.start_line_item_ch2)
                self.safeAdd(self.stop_line_item_ch2)

        if self.setting_tab.show_type == self.setting_tab.CHANNEL:
            self.plot_widget.setLabel("left", "Channel")
            self.plot_widget.setXRange(0, 1)
            self.plot_widget.setYRange(0, NUM_BINS)
        elif self.setting_tab.show_type == self.setting_tab.CHARGE:
            self.plot_widget.setLabel("left", "Charge [pC]")
            self.plot_widget.setXRange(0, 1)
            max_charge = max(
                [
                    self.setting_tab.capacitance_pf_ch1,
                    self.setting_tab.capacitance_pf_ch2,
                ]
            ) * (self.setting_tab.adc_range)
            self.plot_widget.setYRange(0, max_charge)

        self.plot_widget.getAxis("bottom").setScale(
            current_session.int_time + current_session.reset_time
        )
        self.plot_widget.setLabel("bottom", "Time [s]")

        is_moving = self.chart_time_mode_box.currentIndex() == 0
        self.moving_widget.setVisible(is_moving)

        if not is_moving:
            self.plot_widget.enableAutoRange(pg.ViewBox.XAxis)
        else:
            self.plot_widget.setXRange(0, self.n_point_moving_win)
            self.plot_widget.enableAutoRange(pg.ViewBox.XAxis)

        self.line_item_ch1.setDownsampling(auto=False, method="peak")
        self.line_item_ch2.setDownsampling(auto=False, method="peak")

    def safeAdd(self, item):
        if item not in self.plot_widget.items():
            self.plot_widget.addItem(item)
        item.setVisible(True)
        existing_items = [sample.item for sample, label in self.legend.items]
        if item not in existing_items:
            self.legend.addItem(item, item.name())

    def safeRemove(self, item):
        item.setVisible(False)
        if self.legend is not None:
            self.legend.removeItem(item)

    def show_mc(self):
        if self.setting_tab.show_type == self.setting_tab.CHANNEL:
            self.mca_item_ch1.setData(self.mca_x_axis, self.bar_data_ch1)
            self.mca_item_ch2.setData(self.mca_x_axis, self.bar_data_ch2)
        elif self.setting_tab.show_type == self.setting_tab.CHARGE:
            max_charge_ch1 = (
                self.setting_tab.capacitance_pf_ch1 * self.setting_tab.adc_range
            )
            max_charge_ch2 = (
                self.setting_tab.capacitance_pf_ch2 * self.setting_tab.adc_range
            )
            self.mca_item_ch1.setData(
                self.mca_x_axis / NUM_BINS * max_charge_ch1, self.bar_data_ch1
            )
            self.mca_item_ch2.setData(
                self.mca_x_axis / NUM_BINS * max_charge_ch2, self.bar_data_ch2
            )

    def show_time(self):
        if self.time_chart_type == "all":
            start = 0
        else:
            start = self.ptr - self.n_point_moving_win
            if start < 0:
                start = 0

        st_range, end = self.setting_tab.get_range_index(
            self.ptr, current_session.sample_freq
        )
        start = max(st_range, start)

        if self.setting_tab.show_type == self.setting_tab.CHANNEL:
            factor_ch1 = 1
            factor_ch2 = 1
        elif self.setting_tab.show_type == self.setting_tab.CHARGE:
            max_charge_ch1 = (
                self.setting_tab.capacitance_pf_ch1 * self.setting_tab.adc_range
            )
            max_charge_ch2 = (
                self.setting_tab.capacitance_pf_ch2 * self.setting_tab.adc_range
            )
            factor_ch1 = max_charge_ch1 / NUM_BINS
            factor_ch2 = max_charge_ch2 / NUM_BINS

        x = np.arange(start=start, stop=end)
        self.line_item_ch1.setData(x=x, y=self.data[start:end, 0] * factor_ch1)
        self.line_item_ch2.setData(x=x, y=self.data[start:end, 1] * factor_ch2)

        self.show_overflow_marker(start=start, stop=end)

        if current_session.debug_mode:
            self.start_line_item_ch1.setData(
                x=x, y=self.start_data[start:end, 0] * factor_ch1
            )
            self.stop_line_item_ch1.setData(
                x=x, y=self.stop_data[start:end, 0] * factor_ch1
            )
            self.start_line_item_ch2.setData(
                x=x, y=self.start_data[start:end, 1] * factor_ch2
            )
            self.stop_line_item_ch2.setData(
                x=x, y=self.stop_data[start:end, 1] * factor_ch2
            )

    def show_overflow_marker(self, y_marker=NUM_BINS, start: int = 0, stop: int = 0):
        if self.setting_tab.show_type == self.setting_tab.CHARGE:
            max_charge = (
                max(
                    [
                        self.setting_tab.capacitance_pf_ch1,
                        self.setting_tab.capacitance_pf_ch2,
                    ]
                )
                * self.setting_tab.adc_range
            )
            y_marker = y_marker / NUM_BINS * max_charge

        x_nan_ch1 = start + np.where(np.isnan(self.data[start:stop, 0]))[0]
        y_nan_ch1 = np.full(x_nan_ch1.shape, y_marker, dtype=float)
        x_nan_ch2 = start + np.where(np.isnan(self.data[start:stop, 1]))[0]
        y_nan_ch2 = np.full(x_nan_ch2.shape, y_marker, dtype=float)

        if x_nan_ch1.size == 0 and self.nan_marker_item_ch1 is not None:
            self.plot_widget.removeItem(self.nan_marker_item_ch1)
            self.nan_marker_item_ch1 = None

        elif x_nan_ch1.size > 0:
            if self.nan_marker_item_ch1 is None:
                self.nan_marker_item_ch1 = self.plot_widget.plot(
                    x_nan_ch1,
                    y_nan_ch1,
                    pen=None,
                    symbol="o",
                    symbolPen="k",
                    symbolBrush="c",
                    symbolSize=10,
                    name="Errors CH 1",
                )
            else:
                self.nan_marker_item_ch1.setData(x_nan_ch1, y_nan_ch1)

        if x_nan_ch2.size == 0 and self.nan_marker_item_ch2 is not None:
            self.plot_widget.removeItem(self.nan_marker_item_ch2)
            self.nan_marker_item_ch2 = None

        elif x_nan_ch2.size > 0:
            if self.nan_marker_item_ch2 is None:
                self.nan_marker_item_ch2 = self.plot_widget.plot(
                    x_nan_ch2,
                    y_nan_ch2,
                    pen=None,
                    symbol="x",
                    symbolPen="k",
                    symbolBrush="r",
                    symbolSize=10,
                    name="Errors CH 2",
                )
            else:
                self.nan_marker_item_ch2.setData(x_nan_ch2, y_nan_ch2)

    def remove_overflow_marker(self):
        if self.nan_marker_item_ch1 is not None:
            self.plot_widget.removeItem(self.nan_marker_item_ch1)
            self.nan_marker_item_ch1 = None
        if self.nan_marker_item_ch2 is not None:
            self.plot_widget.removeItem(self.nan_marker_item_ch2)
            self.nan_marker_item_ch2 = None

    # =======================================================
    # results
    # =======================================================

    def calculate_stat(self, new_data: NDArray):
        if new_data.size == 0:
            return

        # more than 2 numbers are required to calculate the sample variance
        if (self.count < 2 and new_data.shape[0] < 2) or len(self.temp_values) != 0:
            # Enter if the first time this function is called the new_data are not
            # enough to calculate the variance. If this is the case, the next time
            # we must enter here again to use the previously saved data.
            # e.g. new_data = [[ch1, ch2]]
            for data in new_data:
                self.temp_values.append(data)

            new_data = np.array(self.temp_values)

            if new_data.shape[0] < 2:
                return

            else:
                self.temp_values.clear()

        raw_ch1 = new_data[:, 0]
        raw_ch2 = new_data[:, 1]
        ch1 = np.nan_to_num(raw_ch1, nan=NUM_BINS)
        ch2 = np.nan_to_num(raw_ch2, nan=NUM_BINS)
        n_b = len(new_data)

        # --- Channel 1 Batch Stats ---
        mean_b_ch1 = np.mean(ch1)
        # M2 is the "Sum of Squared Differences"
        # M2 = variance * N
        m2_b_ch1 = np.var(ch1, ddof=0) * n_b

        # --- Channel 2 Batch Stats ---
        mean_b_ch2 = np.mean(ch2)
        m2_b_ch2 = np.var(ch2, ddof=0) * n_b

        # Combine Old Stats (Set A) with New Batch Stats (Set B)
        # We are merging two sets of data using Chan's parallel variance formula

        n_a = self.count
        n_total = n_a + n_b

        delta_ch1 = mean_b_ch1 - self.mean_value_ch1
        self.mean_value_ch1 += delta_ch1 * (n_b / n_total)

        # Recover existing M2 from saved variance (M2_a)
        m2_a_ch1 = self.variance_ch1 * (n_a - 1)
        m2_total_ch1 = m2_a_ch1 + m2_b_ch1 + (delta_ch1**2) * (n_a * n_b / n_total)

        self.variance_ch1 = m2_total_ch1 / (n_total - 1)

        delta_ch2 = mean_b_ch2 - self.mean_value_ch2
        self.mean_value_ch2 += delta_ch2 * (n_b / n_total)

        m2_a_ch2 = self.variance_ch2 * (n_a - 1)
        m2_total_ch2 = m2_a_ch2 + m2_b_ch2 + (delta_ch2**2) * (n_a * n_b / n_total)
        self.variance_ch2 = m2_total_ch2 / (n_total - 1)

        self.count = n_total

        # The welford online algorithm below takes too long to execute
        # with millions of lines
        # for new_value in new_data:
        #     ch1 = new_value[0]
        #     ch2 = new_value[1]
        #
        #     if np.isnan(ch1):
        #         ch1 = NUM_BINS
        #     if np.isnan(ch2):
        #         ch2 = NUM_BINS
        #
        #     self.count += 1
        #
        #     # --- ch1
        #     delta = ch1 - mean_ch1
        #     mean_ch1 += delta / self.count
        #     delta2 = ch1 - mean_ch1
        #     m2_ch1 += delta * delta2
        #
        #     # --- ch2
        #     delta = ch2 - mean_ch2
        #     mean_ch2 += delta / self.count
        #     delta2 = ch2 - mean_ch2
        #     m2_ch2 += delta * delta2

    def fill_result_table(self, new_data):
        start, end = self.setting_tab.get_range_index(
            self.ptr, current_session.sample_freq
        )
        if end - start == self.count:
            new_data = np.array([])

        elif end > self.count and end != self.ptr:
            remaining = end - self.count
            new_data = new_data[0:remaining, :]

        if new_data.size > 0 and start != end:
            self.calculate_stat(new_data)
            self.n_overflow_ch1 += np.count_nonzero(np.isnan(new_data[:, 0]))
            self.n_overflow_ch2 += np.count_nonzero(np.isnan(new_data[:, 1]))

        def set_item(row, col, val):
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.result_table.setItem(row, col, item)

        # Headers
        # "Integrator",
        # "Mean\n[Channel]",
        # "Mean\n[pC]",
        # "Variance\n[Channel]",
        # "Variance\n[pC]",
        # "Std. Dev.\n[Channel]",
        # "Std. Dev.\n[pC]",
        # "n. measures",
        # "Errors",

        max_charge = self.setting_tab.capacitance_pf_ch1 * self.setting_tab.adc_range
        set_item(0, 1, round(self.mean_value_ch1, 2))
        set_item(0, 2, round(self.mean_value_ch1 / NUM_BINS * max_charge, 2))
        set_item(0, 3, round(self.variance_ch1, 4))
        set_item(0, 4, round(self.variance_ch1 * (max_charge / NUM_BINS) ** 2, 4))
        set_item(0, 5, round(np.sqrt(self.variance_ch1), 4))
        set_item(
            0, 6, round(np.sqrt(self.variance_ch1 * (max_charge / NUM_BINS) ** 2), 4)
        )
        set_item(0, 7, self.count)
        set_item(0, 8, self.n_overflow_ch1)

        max_charge = self.setting_tab.capacitance_pf_ch2 * self.setting_tab.adc_range
        set_item(1, 1, round(self.mean_value_ch2, 2))
        set_item(1, 2, round(self.mean_value_ch2 / NUM_BINS * max_charge, 2))
        set_item(1, 3, round(self.variance_ch2, 4))
        set_item(1, 4, round(self.variance_ch2 * (max_charge / NUM_BINS) ** 2, 4))
        set_item(1, 5, round(np.sqrt(self.variance_ch2), 4))
        set_item(
            1, 6, round(np.sqrt(self.variance_ch2 * (max_charge / NUM_BINS) ** 2), 4)
        )
        set_item(1, 7, self.count)
        set_item(1, 8, self.n_overflow_ch2)

    # =======================================================
    # store data
    # =======================================================

    def store_data(self, new_data: NDArray):
        """Store the new incoming data. If in debug mode both the start and stop value
        is returned. For both cases, the real measured data (difference) is
        returned (for the debug mode, it will be the difference between the two). It
        is also returned the number of overflows."""

        if current_session.debug_mode:
            start_value, stop_value, new_data = utils.convert_data_debug(new_data)
        else:
            new_data = utils.convert_data(new_data)

        if current_session.debug_mode:
            self.fill_buffer_debug(start_value, stop_value)

        self.fill_buffer(new_data)
        self.fill_bar_buffer(new_data)

        if current_session.debug_mode:
            return start_value, stop_value, new_data
        else:
            return new_data

    def fill_bar_buffer(self, new_data: NDArray):
        n_sample = np.sum(self.bar_data_ch1)
        start, end = self.setting_tab.get_range_index(
            self.ptr, current_session.sample_freq
        )

        if end - start == n_sample:
            return

        elif end - start < n_sample:
            remaining = end - n_sample
            new_data = new_data[0:remaining, :]

        raw_ch1 = new_data[:, 0]
        raw_ch2 = new_data[:, 1]
        ch1_indices = raw_ch1[~np.isnan(raw_ch1)].astype(int)
        ch2_indices = raw_ch2[~np.isnan(raw_ch2)].astype(int)

        self.bar_data_ch1 += np.bincount(ch1_indices, minlength=NUM_BINS)[:NUM_BINS]
        self.bar_data_ch2 += np.bincount(ch2_indices, minlength=NUM_BINS)[:NUM_BINS]

    def fill_buffer(self, new_data: NDArray) -> None:
        if new_data.shape[0] <= 0:
            return

        if self.ptr + new_data.shape[0] > self.BUFFER_SIZE:
            while self.ptr + new_data.shape[0] > self.BUFFER_SIZE:
                self.BUFFER_SIZE *= 2

            new_y = np.zeros((self.BUFFER_SIZE, 2), dtype=float)
            new_y[: self.ptr, :] = self.data[: self.ptr, :]
            self.data = new_y.copy()

        self.data[self.ptr : self.ptr + new_data.shape[0], :] = new_data.copy()
        self.ptr += new_data.shape[0]

    def fill_buffer_debug(self, start_data: NDArray, stop_data: NDArray):
        new_l = start_data.shape[0]

        if new_l <= 0:
            return

        if self.ptr + new_l > self.BUFFER_SIZE_DEBUG:
            while self.ptr + new_l > self.BUFFER_SIZE_DEBUG:
                self.BUFFER_SIZE_DEBUG *= 2

            new_start = np.zeros((self.BUFFER_SIZE_DEBUG, 2), dtype=float)
            new_stop = np.zeros((self.BUFFER_SIZE_DEBUG, 2), dtype=float)

            new_start[: self.ptr, :] = self.start_data[: self.ptr, :]
            new_stop[: self.ptr, :] = self.stop_data[: self.ptr, :]

            self.start_data = new_start
            self.stop_data = new_stop

        self.start_data[self.ptr : self.ptr + new_l, :] = start_data.copy()
        self.stop_data[self.ptr : self.ptr + new_l, :] = stop_data.copy()

    # =======================================================
    # button logic mapping
    # =======================================================

    def on_left_press(self):
        self.chart_type = "mc"
        self.update_view_buttons()
        self.init_mc_chart()
        self.show_mc()

    def on_right_press(self):
        self.chart_type = "time"
        self.update_view_buttons()
        self.init_time_chart()
        self.show_time()

    def on_change_time_chart_type(self):
        idx = self.chart_time_mode_box.currentIndex()
        if idx == 0:
            self.time_chart_type = "moving"
            self.moving_widget.setVisible(True)
        else:
            self.time_chart_type = "all"
            self.moving_widget.setVisible(False)
        self.init_time_chart()
        self.show_time()

    def on_mem_info_press(self):
        text = (
            "This application stores measurements in memory for fast access.\n\n"
            "Buffers automatically expand by doubling their size when full.\n"
            "Over time, this can lead to high memory consumption.\n\n"
            "Memory usage reference:\n"
            "• Debug mode: ~1 GB per 17 million measurements\n"
            "• Operational mode: ~1 GB per 67 million measurements\n\n"
            "Please monitor system memory during long-running sessions."
        )
        QMessageBox.information(self, "Help — Memory", text)

    def on_restart_press(self):
        if not self.is_running:
            if not self.already_saved and self.already_runned:
                confirm = QMessageBox.question(
                    self,
                    "Restart",
                    "Restart without saving?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if confirm == QMessageBox.StandardButton.No:
                    return

            self.init_variables()

            self.change_start_bnt("start", hide=False, enable=True)
            self.measuring_time_label.setText("0 s")
            self.memory_label.setText(None)
            self.chart_type = "mc"
            self.update_view_buttons()
            self.init_time_chart()
            self.init_mc_chart()
            self.mca_item_ch1.clear()
            self.mca_item_ch2.clear()
            self.line_item_ch1.clear()
            self.line_item_ch2.clear()
            self.already_runned = False
            for r in range(2):
                for c in range(1, self.result_table.columnCount()):
                    self.result_table.setItem(r, c, QTableWidgetItem("0"))

            utils.empty_buffer()
            self.restart_signal.emit()
        else:
            QMessageBox.warning(
                self, "Warning", "Please stop the measurement before restarting."
            )

    def on_save_press(self):
        if not self.is_running:
            dialog = QFileDialog(self)
            dialog.setWindowTitle("Save Measurement Data")
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog.setNameFilters(
                ["CSV Files (*.csv)", "Text Files (*.txt)", "Data Files (*.dat)"]
            )
            dialog.setDefaultSuffix("csv")
            start_path = os.path.expanduser("~")
            dialog.setDirectory(start_path)
            dialog.selectFile("measurement.csv")
            if not dialog.exec():
                return
            file_path = dialog.selectedFiles()[0]
            if not file_path:
                return

            data = self.data[: self.ptr, :]
            start_data = self.start_data[: self.ptr, :]
            stop_data = self.stop_data[: self.ptr, :]

            first_line = (
                f"integration time [s]: {current_session.int_time}, "
                f"reset time [s]: {current_session.reset_time}, "
                f"sample frequency [Hz]: {current_session.sample_freq}"
            )

            if self._write_to_file(file_path, first_line, "w"):
                if current_session.debug_mode:
                    if self._write_to_file(file_path, (start_data, stop_data), "a"):
                        self.already_saved = True
                else:
                    if self._write_to_file(file_path, data, "a"):
                        self.already_saved = True
        else:
            QMessageBox.warning(
                self, "Warning", "Please stop the measurement before saving."
            )

    def on_load_press(self):
        if self.is_running:
            QMessageBox.warning(
                self, "Warning", "Please stop the measurement before loading."
            )
            return

        elif not self.already_saved and self.already_runned:
            confirm = QMessageBox.question(
                self,
                "Load",
                "Load new file without saving current data?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.No:
                return

        dialog = QFileDialog(self)
        dialog.setWindowTitle("Load Measurement Data")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilters(
            ["CSV Files (*.csv)", "Text Files (*.txt)", "Data Files (*.dat)"]
        )
        dialog.setDirectory(os.path.expanduser("~"))

        if dialog.exec():
            file_path = dialog.selectedFiles()[0]
            if file_path:
                try:
                    self.load_file(file_path)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to load: {str(e)}")
                    print(str(e))

    # =======================================================
    # misc
    # =======================================================

    def toggle_settings_panel(self, checked):
        self.right_widget.setVisible(checked)

    def change_start_bnt(
        self, name: str | None, hide: bool = False, enable: bool = True
    ):
        if hide:
            self.start_bnt.setVisible(False)
            if name is None:
                return
        else:
            self.start_bnt.setVisible(True)

        # Common big style
        base_style = """
            QPushButton {
                color: white; 
                font-weight: bold; 
                padding: 10px 30px; 
                border-radius: 5px; 
                font-size: 14pt;
                min-width: 150px;
            }
        """

        if name == "stop":
            self.start_bnt.setText("STOP")
            self.start_bnt.setIcon(self.icon_stop)
            self.start_bnt.setStyleSheet(
                base_style
                + """QPushButton { background-color: #dc3545; } 
                QPushButton:hover { background-color: #c82333; }"""
            )
        elif name == "start":
            self.start_bnt.setText("START")
            self.start_bnt.setIcon(self.icon_start)
            self.start_bnt.setStyleSheet(
                base_style
                + """QPushButton { background-color: #28a745; }
                QPushButton:hover { background-color: #218838; }"""
            )

        self.start_bnt.setEnabled(enable)

    def load_file(self, file_path: str):
        self.init_variables()  # need to restore the ptr and other variables

        with open(file_path, "r") as f:
            reader = csv.reader(f)

            # if the file is empty this will raise a StopIteration
            header = next(reader)

            if len(header) != 3:
                raise RuntimeError("Faulty header")

            int_time = header[0]
            y = int_time.split(":")
            if len(y) != 2:
                raise RuntimeError("Faulty header")

            current_session.int_time = float(y[1].strip())

            rst_time = header[1]
            y = rst_time.split(":")
            if len(y) != 2:
                raise RuntimeError("Faulty header")
            current_session.reset_time = float(y[1].strip())

            freq = header[2]
            y = freq.split(":")
            if len(y) != 2:
                raise RuntimeError("Faulty header")
            current_session.sample_freq = float(y[1].strip())

            first_data_row = next(reader)
            num_cols = len(first_data_row)

        if num_cols not in [3, 5]:
            raise RuntimeError("Column number")

        # TODO: This may take a lot of times to load millions of
        # measurement. Change to pandas if loading speed is required
        raw_data = np.genfromtxt(file_path, delimiter=",", skip_header=1)
        elapsed_time = raw_data[-1, 0]

        if num_cols == 3:
            current_session.debug_mode = False
            data = raw_data[:, 1:3]
        else:
            current_session.debug_mode = True
            start_data = raw_data[:, [1, 3]]
            stop_data = raw_data[:, [2, 4]]
            data = stop_data - start_data
            self.fill_buffer_debug(start_data, stop_data)

        self.fill_buffer(data)
        self.fill_bar_buffer(data)
        self.fill_result_table(data)
        self.on_frequency_change()
        self.change_start_bnt(None, hide=True, enable=False)
        self.restart_bnt.setEnabled(True)
        self.measuring_time_label.setText(f"{round(elapsed_time, 2)} s")

        if self.chart_type == "mc":
            self.init_mc_chart()
            self.show_mc()
        elif self.chart_type == "time":
            self.init_time_chart()
            self.show_time()

        self.setting_tab.disable_time_range()

    def _write_to_file(self, file_path: str, data, mode: str) -> bool:
        """Write the given data to the file at file_path. mode can be 'w' or 'a'.
        'w' will overwrite the file, 'a' will append the data to the existing file."""

        if mode not in ["w", "a"]:
            raise ValueError("Wrong mode")
        try:
            with open(file_path, mode) as f:
                to_write = ""
                if isinstance(data, (list, np.ndarray)):
                    # processing mode

                    for val in data:
                        self.timestamp += 1

                        ts = round(self.timestamp / current_session.sample_freq, 7)
                        ch1 = int(val[0]) if not np.isnan(val[0]) else val[0]
                        ch2 = int(val[1]) if not np.isnan(val[1]) else val[1]

                        to_write += f"{ts},{ch1},{ch2}\n"

                    f.write(to_write)

                elif isinstance(data, str):
                    # write first lines (like config data)
                    f.write(f"{data}\n")

                elif isinstance(data, tuple):
                    # debug_mode
                    start_val, stop_val = data
                    for i in range(len(start_val)):
                        self.timestamp += 1

                        ts = round(self.timestamp / current_session.sample_freq, 7)
                        s1, s2 = int(start_val[i][0]), int(start_val[i][1])
                        e1 = (
                            int(stop_val[i][0])
                            if not np.isnan(stop_val[i][0])
                            else stop_val[i][0]
                        )
                        e2 = (
                            int(stop_val[i][1])
                            if not np.isnan(stop_val[i][1])
                            else stop_val[i][1]
                        )
                        to_write += f"{ts},{s1},{e1},{s2},{e2}\n"

                    f.write(to_write)

                elif data is None:
                    # Create an empty file
                    pass
            return True

        except PermissionError:
            QMessageBox.critical(
                self, "Error", "Permission denied: Cannot write to this location."
            )
            return False
        except OSError:
            QMessageBox.critical(
                self, "Error", "System error: Please try a different path."
            )
            return False

    def on_frequency_change(self):
        """Called when the time window changes the sample frequency. Called each time
        this window is shown"""
        self.n_point_moving_line.setValue(
            self.n_point_moving_win / current_session.sample_freq
        )

        def fmt_time(t):
            if t > 1:
                return f"{round(t, 3)} s"
            elif t > 1e-3:
                return f"{round(t * 1e3, 3)} ms"
            else:
                return f"{round(t * 1e6, 3)} μs"

        def fmt_hz(h):
            if h > 1e3:
                return f"{round(h / 1e3, 2)} kHz"
            return f"{round(h, 6)} Hz"

        self.int_time_label.setText(fmt_time(current_session.int_time))
        self.rst_time_label.setText(fmt_time(current_session.reset_time))
        self.sample_freq_label.setText(fmt_hz(current_session.sample_freq))

    def on_change_n_point_moving(self):
        """Called when changing the number of points in the moving window"""

        # The inserted value is in second

        n_point_s = self.n_point_moving_line.value()
        n_point = round(n_point_s * current_session.sample_freq)
        if n_point > 0:
            self.n_point_moving_win = n_point
            if self.chart_type == "time":
                self.init_time_chart()
                self.show_time()

    def on_update_setting(self):
        if self.chart_type == "time":
            self.init_time_chart(update=True)
            self.show_time()
        elif self.chart_type == "mc":
            self.init_mc_chart(update=True)
            self.show_mc()

        self.variance_ch1 = 0
        self.variance_ch2 = 0
        self.n_overflow_ch1 = 0
        self.n_overflow_ch2 = 0
        self.count = 0
        self.bar_data_ch1 *= 0
        self.bar_data_ch2 *= 0
        self.temp_values = []

        start, end = self.setting_tab.get_range_index(
            self.ptr, current_session.sample_freq
        )
        self.fill_bar_buffer(self.data[start:end])
        self.fill_result_table(self.data[start:end])

    def close_event(self) -> bool:
        # closeEvent is called only on the main window, not the child widget

        # used when closing the app when the receiving is still working.
        if self.is_running and self.already_runned:
            confirm = QMessageBox.question(
                self,
                "Close",
                "Stop receiving?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.No:
                return False
            self.on_stop_press()

        if not self.already_saved and self.already_runned:
            confirm = QMessageBox.question(
                self,
                "Close",
                "Close without saving?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.No:
                return False
        return True


# =====================================================================================
# The class below can be used fot the moving window in case a memeory safe application
# is required.
# =====================================================================================

# class RingBuffer:
#     def __init__(self, size=500_000):
#         """A circular buffer with fixed memory usage.
#         size: Max number of rows (e.g., 500k points).
#         """
#         self.capacity = size
#         self.buffer = np.zeros((size, 2), dtype=float)
#         self.ptr = 0  # Points to the next write position
#         self.is_full = False
#
#     def clear(self):
#         self.ptr = 0
#         self.is_full = False
#         self.buffer.fill(0)
#
#     def add(self, new_data):
#         """new_data: np.array of shape (k, 2)"""
#         n = new_data.shape[0]
#         if n == 0:
#             return
#
#         # If new data is larger than entire buffer, just take the last chunk
#         # This should never happen
#         if n > self.capacity:
#             new_data = new_data[-self.capacity :]  # take last rows
#             n = self.capacity
#
#         # Check if we need to wrap around
#         if self.ptr + n <= self.capacity:
#             # Simple case: fits at the end
#             self.buffer[self.ptr : self.ptr + n] = new_data
#             self.ptr += n
#         else:
#             # Wrapping case
#             # Fill until the end of the array
#             space_at_end = self.capacity - self.ptr
#             self.buffer[self.ptr :] = new_data[:space_at_end]
#
#             # Wrap around to the beginning
#             remainder = n - space_at_end
#             self.buffer[:remainder] = new_data[space_at_end:]
#
#             self.ptr = remainder
#             self.is_full = True
#
#         if self.ptr == self.capacity:
#             self.ptr = 0
#             self.is_full = True
#
#     def get_recent(self, n_points):
#         """Returns the last 'n_points' in chronological order (oldest -> newest).
#         This involves a copy, but it's fast for plotting windows (e.g. 10k points).
#         """
#         if n_points <= 0:
#             return np.empty((0, self.buffer.shape[1]))
#
#         # We can't return more than we have
#         available = self.capacity if self.is_full else self.ptr
#         n_points = min(n_points, available)
#
#         # Calculate indices
#         # The 'end' is usually self.ptr
#         # The 'start' is self.ptr - n_points (handling wrap)
#
#         idx_end = self.ptr
#         idx_start = self.ptr - n_points
#
#         if idx_start >= 0:
#             # No wrapping needed for retrieval
#             return self.buffer[idx_start:idx_end]
#         else:
#             # Wrapping needed: We need Part A (end of buffer) + Part B (start of buffer)
#             # idx_start is negative, so self.buffer[idx_start:] gives the end chunk
#             part_a = self.buffer[idx_start:]
#             part_b = self.buffer[:idx_end]
#             return np.vstack((part_a, part_b))


class RangeSelector(QGroupBox):
    range_change = pyqtSignal()

    def __init__(self, title="Time Range Filter"):
        super().__init__(title)
        self.setCheckable(True)
        self.setChecked(False)
        self.init_ui()

    def init_ui(self):
        layout = QGridLayout()
        layout.setContentsMargins(5, 10, 5, 5)
        layout.setVerticalSpacing(10)
        self.setLayout(layout)

        opts = {
            "suffix": "s",
            "siPrefix": True,
            "dec": True,
            "step": 0.1,
            "minStep": 1e-6,
            "decimals": 3,
            "bounds": [0, None],  # Prevent negative time
        }

        self.chk_start = QCheckBox("From:")
        self.chk_start.setFixedHeight(35)
        self.spin_start = pg.SpinBox(value=0.0, **opts)
        self.spin_start.setEnabled(False)
        self.spin_start.setFixedHeight(35)

        self.chk_end = QCheckBox("To:")
        self.chk_end.setFixedHeight(35)
        self.spin_end = pg.SpinBox(value=60.0, **opts)
        self.spin_end.setEnabled(False)
        self.spin_end.setFixedHeight(35)

        layout.addWidget(self.chk_start, 0, 0)
        layout.addWidget(self.spin_start, 0, 1)
        layout.addWidget(self.chk_end, 1, 0)
        layout.addWidget(self.spin_end, 1, 1)

        self.toggled.connect(self._chk_change)
        self.chk_start.toggled.connect(self._chk_change)
        self.chk_end.toggled.connect(self._chk_change)
        self.spin_start.sigValueChanged.connect(self._validate_ranges)
        self.spin_end.sigValueChanged.connect(self._validate_ranges)

    def _chk_change(self):
        self.spin_start.setEnabled(self.chk_start.isChecked())
        self.spin_end.setEnabled(self.chk_end.isChecked())
        self._validate_ranges()

    def _validate_ranges(self):
        s = self.spin_start.value()
        e = self.spin_end.value()
        if self.chk_start.isChecked() and self.chk_end.isChecked() and s > e:
            if self.sender() == self.spin_start:
                self.spin_end.setValue(s)
            else:
                self.spin_start.setValue(e)
        self.range_change.emit()

    def get_time_range(self, current_max_time):
        """Returns (start_time, end_time).

        Parameters
        ----------
            current_max_time (float): The actual current duration of your experiment.
                Since the experiment runs for days, pass the value at the moment of
                analysis.
        """
        if not self.isChecked():
            return 0.0, current_max_time
        s = self.spin_start.value() if self.chk_start.isChecked() else 0.0
        e = self.spin_end.value() if self.chk_end.isChecked() else current_max_time
        return max(0.0, min(s, e)), max(s, min(e, current_max_time))


class RunSettingTab(QWidget):
    update_signal = pyqtSignal()
    CHARGE = "Charge"
    CHANNEL = "Channel"
    capacitance_pf_ch1 = 100
    capacitance_pf_ch2 = 200
    show_type = CHANNEL
    adc_range = 5

    def __init__(self) -> None:
        super().__init__()
        self.init_ui()

    def init_ui(self):
        style_sheet = """
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
             QGroupBox::indicator {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 3px;
                top: 0px;
                width: 13px;
                height: 13px;
            }
            QDoubleSpinBox {
                padding-top: 3px;
                padding-bottom: 3px;
                padding-left: 0px;
                /* Reserve space on right for buttons so text doesn't overlap them */
                padding-right: 10px; 
            }
            QComboBox {
                padding: 3px 0px 3px 0px;
            }
        """
        self.setStyleSheet(style_sheet)

        main_layout = QVBoxLayout()
        # main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)

        # --- Capacitance Section ---
        cap_group = QGroupBox("Capacitance Settings")
        cap_layout = QGridLayout()

        # cap_layout.setColumnStretch(0, 1)
        # cap_layout.setColumnStretch(1, 2)

        self.capacitance_line_ch1 = QDoubleSpinBox()
        self.capacitance_line_ch1.setRange(0, float("inf"))
        self.capacitance_line_ch1.setValue(self.capacitance_pf_ch1)
        self.capacitance_line_ch1.valueChanged.connect(self.on_cap_change)

        self.capacitance_line_ch2 = QDoubleSpinBox()
        self.capacitance_line_ch2.setRange(0, float("inf"))
        self.capacitance_line_ch2.setValue(self.capacitance_pf_ch2)
        self.capacitance_line_ch2.valueChanged.connect(self.on_cap_change)

        cap_layout.addWidget(QLabel("CH 1 [pF]:"), 0, 0)
        cap_layout.addWidget(self.capacitance_line_ch1, 0, 1)
        cap_layout.addWidget(QLabel("CH 2 [pF]:"), 1, 0)
        cap_layout.addWidget(self.capacitance_line_ch2, 1, 1)
        cap_group.setLayout(cap_layout)

        # --- ADC Section ---
        adc_group = QGroupBox("ADC Range [V]")
        adc_layout = QHBoxLayout()

        self.min_adc_line = QDoubleSpinBox()
        self.min_adc_line.setRange(float("-inf"), float("inf"))
        self.min_adc_line.setValue(0)
        self.min_adc_line.valueChanged.connect(self.on_adc_range_change)

        self.max_adc_line = QDoubleSpinBox()
        self.max_adc_line.setRange(float("-inf"), float("inf"))
        self.max_adc_line.setValue(5)
        self.max_adc_line.valueChanged.connect(self.on_adc_range_change)

        adc_layout.addWidget(self.min_adc_line)
        adc_layout.addStretch(1)
        adc_layout.addWidget(QLabel("to"))
        adc_layout.addStretch(1)
        adc_layout.addWidget(self.max_adc_line)
        adc_group.setLayout(adc_layout)

        # --- View Mode ---
        view_group = QGroupBox("Units")
        view_layout = QVBoxLayout()
        self.type_box = QComboBox()
        self.type_box.addItems([self.CHANNEL, self.CHARGE])
        self.type_box.currentIndexChanged.connect(self.on_type_change)
        view_layout.addWidget(self.type_box)
        view_group.setLayout(view_layout)

        # --- Time Filter ---
        self.time_range = RangeSelector()
        self.time_range.setStyleSheet(style_sheet)
        self.time_range.range_change.connect(self.update_signal.emit)

        # Add all to layout
        main_layout.addWidget(cap_group)
        main_layout.addWidget(adc_group)
        main_layout.addSpacing(20)
        main_layout.addWidget(view_group)
        main_layout.addWidget(self.time_range)
        main_layout.addStretch(1)

    def on_type_change(self):
        self.show_type = self.type_box.currentText()
        self.update_signal.emit()

    def on_cap_change(self):
        c1, c2 = self.capacitance_line_ch1.value(), self.capacitance_line_ch2.value()
        if c1 > 0:
            self.capacitance_pf_ch1 = c1
        if c2 > 0:
            self.capacitance_pf_ch2 = c2
        self.update_signal.emit()

    def on_adc_range_change(self):
        mn, mx = self.min_adc_line.value(), self.max_adc_line.value()
        if mn > mx:
            self.min_adc_line.setValue(mx)
        diff = mx - mn
        if diff > 0:
            self.adc_range = diff
            self.update_signal.emit()

    def get_range_index(self, max_index, sample_frequency):
        max_time = max_index / sample_frequency
        start, end = self.time_range.get_time_range(max_time)
        return int(start * sample_frequency), int(end * sample_frequency)

    def disable_time_range(self):
        self.time_range.setChecked(False)
