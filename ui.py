"""PyQt6 dark-themed Settings/Dashboard UI and System Tray integration for YetiAmbush."""

import os
import time
from pathlib import Path
from typing import Any, Dict

from PyQt6.QtCore import QTime, QTimer, Qt
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSystemTrayIcon,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from config import (
    is_autostart_enabled,
    load_config,
    resolve_icon_path,
    resolve_sound_path,
    set_autostart_enabled,
)
from engine import HydrationEngine, STATE_ACTIVE, STATE_SNOOZED, STATE_STOPPED
from notifier import play_sound

DARK_STYLESHEET = """
QMainWindow, QWidget#MainContainer, QScrollArea {
    background-color: #11151d;
    color: #e2e8f0;
}
QGroupBox {
    background-color: #181e29;
    border: 1px solid #283244;
    border-radius: 10px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: bold;
    color: #93c5fd;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    background-color: #11151d;
    border-radius: 4px;
}
QFrame#StatusCard {
    background-color: #172030;
    border: 1px solid #263854;
    border-radius: 10px;
}
QFrame#ModeCard {
    background-color: #1d2432;
    border: 1px solid #2b364a;
    border-radius: 8px;
}
QLabel {
    color: #e2e8f0;
    background: transparent;
}
QSpinBox, QComboBox, QLineEdit, QTimeEdit {
    background-color: #0f131a;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 35px;
    selection-background-color: #2563eb;
}
QSpinBox:focus, QComboBox:focus, QLineEdit:focus, QTimeEdit:focus {
    border: 1px solid #38bdf8;
}
QSpinBox:disabled, QComboBox:disabled, QLineEdit:disabled, QSlider:disabled {
    color: #64748b;
    background-color: #151a23;
    border-color: #222b3a;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #181e29;
    color: #f1f5f9;
    selection-background-color: #2563eb;
    border: 1px solid #334155;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #273244;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #0ea5e9;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #38bdf8;
    border: 2px solid #0f172a;
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}
QSlider::handle:horizontal:disabled {
    background: #475569;
}
QRadioButton, QCheckBox {
    color: #e2e8f0;
    spacing: 8px;
    min-height: 30px;
}
QRadioButton::indicator, QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QProgressBar {
    background-color: #0f131a;
    border: 1px solid #2b384d;
    border-radius: 7px;
    text-align: center;
    color: #f8fafc;
    font-weight: bold;
    min-height: 24px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
    border-radius: 6px;
}
QPushButton {
    background-color: #232c3d;
    color: #f1f5f9;
    border: 1px solid #334155;
    border-radius: 7px;
    padding: 6px 14px;
    min-height: 36px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2d384d;
    border-color: #475569;
}
QPushButton:pressed {
    background-color: #1e293b;
}
QPushButton#PrimaryBtn {
    background-color: #0284c7;
    border: 1px solid #0ea5e9;
    color: #ffffff;
}
QPushButton#PrimaryBtn:hover {
    background-color: #0369a1;
}
QPushButton#LogDrinkBtn {
    background-color: #065f46;
    border: 1px solid #10b981;
    color: #ecfdf5;
}
QPushButton#LogDrinkBtn:hover {
    background-color: #047857;
}
QPushButton#StopEnoughBtn {
    background-color: #7f1d1d;
    border: 1px solid #ef4444;
    color: #fef2f2;
    font-size: 13px;
}
QPushButton#StopEnoughBtn:hover {
    background-color: #991b1b;
}
QPushButton#ResumeBtn {
    background-color: #065f46;
    border: 1px solid #10b981;
    color: #ecfdf5;
    font-size: 13px;
}
QPushButton#ResumeBtn:hover {
    background-color: #047857;
}
"""


def apply_dark_theme(app: QApplication) -> None:
    """Apply Fusion style, dark palette, and YetiAmbush QSS theme."""
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#11151d"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e2e8f0"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0f131a"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#181e29"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f8fafc"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#232c3d"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f1f5f9"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#0284c7"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(DARK_STYLESHEET)


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelTimeEdit(QTimeEdit):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()


def _create_synced_slider_spin(
    minimum: int,
    maximum: int,
    step: int,
    suffix: str,
) -> tuple[NoWheelSlider, NoWheelSpinBox]:
    """Create a bidirectionally synchronized slider and spinbox pair."""
    slider = NoWheelSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setSingleStep(step)
    slider.setPageStep(step * 2)
    slider.setMinimumHeight(35)

    spin = NoWheelSpinBox()
    spin.setRange(minimum, maximum)
    spin.setSingleStep(step)
    spin.setSuffix(suffix)
    spin.setMinimumHeight(35)
    spin.setMinimumWidth(115)

    slider.valueChanged.connect(spin.setValue)
    spin.valueChanged.connect(slider.setValue)
    return slider, spin


class SettingsWindow(QMainWindow):
    """Main dark-themed dashboard and settings window for YetiAmbush."""

    def __init__(self, engine: HydrationEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._allow_quit = False
        self._selected_sound_file = ""

        self._init_ui()
        self.load_from_config()
        self.refresh_live_status()

        self.engine.state_changed.connect(self.refresh_live_status)

        # Refresh displayed countdown every second only while visible
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(1000)
        self._ui_timer.timeout.connect(self._update_countdown_label)
        self._ui_timer.start()

    def allow_quit(self) -> None:
        self._allow_quit = True

    def closeEvent(self, event) -> None:
        if self._allow_quit:
            event.accept()
            return
        # Minimize to tray when user clicks the X button
        event.ignore()
        self.hide()

    def _init_ui(self) -> None:
        self.setWindowTitle("YetiAmbush — Dashboard and Settings")
        self.setMinimumSize(680, 760)
        self.resize(740, 860)

        icon_path = resolve_icon_path(self.engine.config.get("icon_file", ""))
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll)

        container = QWidget()
        container.setObjectName("MainContainer")
        scroll.setWidget(container)

        root = QVBoxLayout(container)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(15)

        # Header
        header_row = QHBoxLayout()
        header_row.setContentsMargins(6, 4, 6, 4)
        header_row.setSpacing(15)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        lbl_title = QLabel("💧 YetiAmbush")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        lbl_title.setFont(title_font)

        lbl_sub = QLabel("ADHD-friendly hydration tray daemon and Yeti tracker")
        lbl_sub.setStyleSheet("color: #94a3b8;")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)
        header_row.addLayout(title_col)
        header_row.addStretch()
        root.addLayout(header_row)

        # Live Dashboard / Status Card
        status_card = QFrame()
        status_card.setObjectName("StatusCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(15, 15, 15, 15)
        status_layout.setSpacing(12)

        top_status_row = QHBoxLayout()
        top_status_row.setSpacing(15)
        self.lbl_state = QLabel("🟢 Active")
        self.lbl_state.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.lbl_intake_summary = QLabel("0 / 2000 ml")
        self.lbl_intake_summary.setStyleSheet("font-weight: bold; color: #38bdf8;")
        top_status_row.addWidget(self.lbl_state)
        top_status_row.addStretch()
        top_status_row.addWidget(self.lbl_intake_summary)
        status_layout.addLayout(top_status_row)

        self.progress_bar = QProgressBar()
        status_layout.addWidget(self.progress_bar)

        quick_row = QHBoxLayout()
        quick_row.setSpacing(10)

        self.btn_log_drink = QPushButton("💧 Log Drink (+250 ml)")
        self.btn_log_drink.setObjectName("LogDrinkBtn")
        self.btn_log_drink.setMinimumHeight(38)
        self.btn_log_drink.clicked.connect(lambda: self.engine.record_drink())

        self.btn_log_yeti = QPushButton("🧊 Full Yeti (+1390 ml)")
        self.btn_log_yeti.setMinimumHeight(38)
        self.btn_log_yeti.clicked.connect(self._on_log_full_yeti)

        self.btn_reset_today = QPushButton("🔄 Reset Today")
        self.btn_reset_today.setMinimumHeight(38)
        self.btn_reset_today.clicked.connect(self._on_reset_today)

        self.btn_stop_enough = QPushButton("🛑 Stop Notifications / I've Drunk Enough")
        self.btn_stop_enough.setObjectName("StopEnoughBtn")
        self.btn_stop_enough.setMinimumHeight(38)
        self.btn_stop_enough.clicked.connect(self._on_stop_or_resume_clicked)

        quick_row.addWidget(self.btn_log_drink)
        quick_row.addWidget(self.btn_log_yeti)
        quick_row.addWidget(self.btn_reset_today)
        quick_row.addStretch()
        status_layout.addLayout(quick_row)
        status_layout.addWidget(self.btn_stop_enough)
        root.addWidget(status_card)

        # Group 1: Reminder Interval and Timing Strategy
        grp_timing = QGroupBox("Reminder Interval and Timing Strategy")
        timing_layout = QVBoxLayout(grp_timing)
        timing_layout.setContentsMargins(15, 15, 15, 15)
        timing_layout.setSpacing(15)

        # Mode 1: Scheduled Interval (Slider + SpinBox)
        self.card_scheduled = QFrame()
        self.card_scheduled.setObjectName("ModeCard")
        sched_layout = QVBoxLayout(self.card_scheduled)
        sched_layout.setContentsMargins(15, 15, 15, 15)
        sched_layout.setSpacing(10)

        self.rb_scheduled = QRadioButton("Scheduled Interval (Fixed Minutes)")
        self.rb_scheduled.setMinimumHeight(35)
        self.rb_scheduled.toggled.connect(self._update_mode_states)
        sched_layout.addWidget(self.rb_scheduled)

        sched_row = QHBoxLayout()
        sched_row.setSpacing(15)
        lbl_sched = QLabel("Reminder Interval:")
        lbl_sched.setMinimumHeight(35)
        self.slider_scheduled, self.spin_scheduled = _create_synced_slider_spin(5, 180, 5, " mins")
        sched_row.addWidget(lbl_sched)
        sched_row.addWidget(self.slider_scheduled, stretch=1)
        sched_row.addWidget(self.spin_scheduled)
        sched_layout.addLayout(sched_row)
        timing_layout.addWidget(self.card_scheduled)

        # Mode 2: Random Ambush (Min & Max Sliders + SpinBoxes)
        self.card_random = QFrame()
        self.card_random.setObjectName("ModeCard")
        rand_layout = QVBoxLayout(self.card_random)
        rand_layout.setContentsMargins(15, 15, 15, 15)
        rand_layout.setSpacing(12)

        self.rb_random = QRadioButton("Random Ambush Mode (ADHD Anti-Habituation)")
        self.rb_random.setMinimumHeight(35)
        self.rb_random.toggled.connect(self._update_mode_states)
        rand_layout.addWidget(self.rb_random)

        min_row = QHBoxLayout()
        min_row.setSpacing(15)
        lbl_min = QLabel("Min Interval:")
        lbl_min.setMinimumWidth(95)
        lbl_min.setMinimumHeight(35)
        self.slider_rand_min, self.spin_rand_min = _create_synced_slider_spin(5, 180, 5, " mins")
        self.spin_rand_min.valueChanged.connect(self._on_min_changed)
        min_row.addWidget(lbl_min)
        min_row.addWidget(self.slider_rand_min, stretch=1)
        min_row.addWidget(self.spin_rand_min)
        rand_layout.addLayout(min_row)

        max_row = QHBoxLayout()
        max_row.setSpacing(15)
        lbl_max = QLabel("Max Interval:")
        lbl_max.setMinimumWidth(95)
        lbl_max.setMinimumHeight(35)
        self.slider_rand_max, self.spin_rand_max = _create_synced_slider_spin(5, 180, 5, " mins")
        self.spin_rand_max.valueChanged.connect(self._on_max_changed)
        max_row.addWidget(lbl_max)
        max_row.addWidget(self.slider_rand_max, stretch=1)
        max_row.addWidget(self.spin_rand_max)
        rand_layout.addLayout(max_row)
        timing_layout.addWidget(self.card_random)

        # Quiet Hours inside timing card
        qh_row = QHBoxLayout()
        qh_row.setSpacing(15)
        lbl_qh_start = QLabel("Quiet Hours Start:")
        lbl_qh_start.setMinimumHeight(35)
        self.time_quiet_start = NoWheelTimeEdit()
        self.time_quiet_start.setDisplayFormat("HH:mm")
        self.time_quiet_start.setMinimumHeight(35)
        self.time_quiet_start.setMinimumWidth(110)

        lbl_qh_end = QLabel("End:")
        lbl_qh_end.setMinimumHeight(35)
        self.time_quiet_end = NoWheelTimeEdit()
        self.time_quiet_end.setDisplayFormat("HH:mm")
        self.time_quiet_end.setMinimumHeight(35)
        self.time_quiet_end.setMinimumWidth(110)

        qh_row.addWidget(lbl_qh_start)
        qh_row.addWidget(self.time_quiet_start)
        qh_row.addSpacing(20)
        qh_row.addWidget(lbl_qh_end)
        qh_row.addWidget(self.time_quiet_end)
        qh_row.addStretch()
        timing_layout.addLayout(qh_row)

        root.addWidget(grp_timing)

        # Group 2: Daily Water Goal and Yeti Bottle
        grp_goals = QGroupBox("Daily Water Goal and Yeti Tracking")
        goals_form = QFormLayout(grp_goals)
        goals_form.setContentsMargins(15, 15, 15, 15)
        goals_form.setSpacing(15)
        goals_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.spin_daily_goal = NoWheelSpinBox()
        self.spin_daily_goal.setRange(250, 10000)
        self.spin_daily_goal.setSingleStep(50)
        self.spin_daily_goal.setSuffix(" ml")
        self.spin_daily_goal.setMinimumHeight(35)
        self.spin_daily_goal.valueChanged.connect(self._update_goal_preview)

        self.combo_yeti_size = NoWheelComboBox()
        self.combo_yeti_size.addItems(["1.39L (1390 ml)", "796 ml", "Custom"])
        self.combo_yeti_size.setMinimumHeight(35)
        self.combo_yeti_size.currentTextChanged.connect(self._on_yeti_changed)

        self.spin_custom_yeti = NoWheelSpinBox()
        self.spin_custom_yeti.setRange(100, 5000)
        self.spin_custom_yeti.setSingleStep(50)
        self.spin_custom_yeti.setSuffix(" ml")
        self.spin_custom_yeti.setMinimumHeight(35)
        self.spin_custom_yeti.valueChanged.connect(self._update_goal_preview)
        self.spin_custom_yeti.setVisible(False)

        self.spin_drink_amt = NoWheelSpinBox()
        self.spin_drink_amt.setRange(25, 2000)
        self.spin_drink_amt.setSingleStep(25)
        self.spin_drink_amt.setSuffix(" ml")
        self.spin_drink_amt.setMinimumHeight(35)

        self.lbl_equates = QLabel("")
        self.lbl_equates.setMinimumHeight(35)
        self.lbl_equates.setStyleSheet("color: #38bdf8; font-weight: bold;")

        self.lbl_custom_yeti = QLabel("Custom Yeti Size:")
        self.lbl_custom_yeti.setMinimumHeight(35)
        self.lbl_custom_yeti.setVisible(False)

        goals_form.addRow(self._mk_label("Daily Water Goal:"), self.spin_daily_goal)
        goals_form.addRow(self._mk_label("Yeti Bottle Size:"), self.combo_yeti_size)
        goals_form.addRow(self.lbl_custom_yeti, self.spin_custom_yeti)
        goals_form.addRow(self._mk_label("Amount per Drink:"), self.spin_drink_amt)
        goals_form.addRow(self._mk_label("Equates to:"), self.lbl_equates)
        root.addWidget(grp_goals)

        # Group 3: Notification Mode, Sound, Quotes, and System
        grp_notif = QGroupBox("Notifications, Audio, and System")
        notif_layout = QVBoxLayout(grp_notif)
        notif_layout.setContentsMargins(15, 15, 15, 15)
        notif_layout.setSpacing(15)

        notif_form = QFormLayout()
        notif_form.setSpacing(15)
        notif_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.combo_notif_mode = NoWheelComboBox()
        self.combo_notif_mode.addItem("Native Desktop Notification (notify-send / D-Bus)", "native")
        self.combo_notif_mode.addItem("Visual Ambush Popup Window", "popup")
        self.combo_notif_mode.setMinimumHeight(35)
        self.combo_notif_mode.currentIndexChanged.connect(self._update_notif_mode_states)

        self.combo_quote_style = NoWheelComboBox()
        self.combo_quote_style.addItems(["Unhinged", "Polite", "Mixed", "Custom"])
        self.combo_quote_style.setMinimumHeight(35)
        self.combo_quote_style.currentTextChanged.connect(self._update_quote_states)

        self.txt_custom_quote = QLineEdit()
        self.txt_custom_quote.setMinimumHeight(35)
        self.txt_custom_quote.setPlaceholderText("Enter custom hydration message...")

        notif_form.addRow(self._mk_label("Notification Mode:"), self.combo_notif_mode)
        notif_form.addRow(self._mk_label("Quote Style:"), self.combo_quote_style)
        notif_form.addRow(self._mk_label("Custom Text:"), self.txt_custom_quote)
        notif_layout.addLayout(notif_form)

        self.chk_interactive = QCheckBox("Show inline Plasma action buttons (Drank It, 5m, 15m) on native alerts")
        self.chk_interactive.setMinimumHeight(35)
        notif_layout.addWidget(self.chk_interactive)

        # Sound Controls
        self.chk_sound = QCheckBox("Play reminder audio cue")
        self.chk_sound.setMinimumHeight(35)
        self.chk_sound.toggled.connect(self._update_sound_states)
        notif_layout.addWidget(self.chk_sound)

        sound_row = QHBoxLayout()
        sound_row.setContentsMargins(24, 0, 0, 0)
        sound_row.setSpacing(12)

        self.lbl_sound_file = QLabel("Default: drop.wav")
        self.lbl_sound_file.setStyleSheet("color: #94a3b8;")
        self.lbl_sound_file.setMinimumHeight(35)
        self.btn_choose_sound = QPushButton("Choose Audio...")
        self.btn_choose_sound.setMinimumHeight(35)
        self.btn_choose_sound.clicked.connect(self._on_choose_sound)

        self.btn_reset_sound = QPushButton("Reset Default")
        self.btn_reset_sound.setMinimumHeight(35)
        self.btn_reset_sound.clicked.connect(self._on_reset_sound)

        self.btn_test_sound = QPushButton("🔊 Test Sound")
        self.btn_test_sound.setMinimumHeight(35)
        self.btn_test_sound.clicked.connect(self._on_test_sound)

        sound_row.addWidget(self.lbl_sound_file, stretch=1)
        sound_row.addWidget(self.btn_choose_sound)
        sound_row.addWidget(self.btn_reset_sound)
        sound_row.addWidget(self.btn_test_sound)
        notif_layout.addLayout(sound_row)

        # Autostart Checkbox
        self.chk_autostart = QCheckBox("Start with System (manage ~/.config/autostart/yetiambush.desktop)")
        self.chk_autostart.setMinimumHeight(35)
        notif_layout.addWidget(self.chk_autostart)

        root.addWidget(grp_notif)

        # Feedback Toast
        self.lbl_toast = QLabel("")
        self.lbl_toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_toast.setMinimumHeight(35)
        root.addWidget(self.lbl_toast)

        # Footer Buttons
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 4, 0, 4)
        footer_row.setSpacing(15)

        btn_test_notif = QPushButton("⚡ Test Notification")
        btn_test_notif.setMinimumHeight(40)
        btn_test_notif.clicked.connect(lambda: self.engine.trigger_ambush(is_test=True))

        btn_hide = QPushButton("Minimize to Tray")
        btn_hide.setMinimumHeight(40)
        btn_hide.clicked.connect(self.hide)

        btn_save = QPushButton("💾 Save and Apply")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setMinimumHeight(40)
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.on_save_clicked)

        footer_row.addWidget(btn_test_notif)
        footer_row.addWidget(btn_hide)
        footer_row.addStretch()
        footer_row.addWidget(btn_save)
        root.addLayout(footer_row)

    @staticmethod
    def _mk_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setMinimumHeight(35)
        return lbl

    def load_from_config(self) -> None:
        cfg = load_config()
        self.engine.config = cfg

        if int(cfg.get("mode", 2)) == 1:
            self.rb_scheduled.setChecked(True)
        else:
            self.rb_random.setChecked(True)

        self.spin_scheduled.setValue(int(cfg.get("scheduled_interval", 45)))
        self.spin_rand_min.setValue(int(cfg.get("random_min", 30)))
        self.spin_rand_max.setValue(int(cfg.get("random_max", 90)))

        self.time_quiet_start.setTime(QTime.fromString(cfg.get("quiet_start", "22:00"), "HH:mm"))
        self.time_quiet_end.setTime(QTime.fromString(cfg.get("quiet_end", "08:00"), "HH:mm"))

        self.spin_daily_goal.setValue(int(cfg.get("daily_goal_ml", 2000)))
        self.spin_drink_amt.setValue(int(cfg.get("amount_per_drink_ml", 250)))

        yeti_size = int(cfg.get("yeti_size_ml", 1390))
        if yeti_size == 1390:
            self.combo_yeti_size.setCurrentText("1.39L (1390 ml)")
            self.spin_custom_yeti.setValue(1390)
        elif yeti_size == 796:
            self.combo_yeti_size.setCurrentText("796 ml")
            self.spin_custom_yeti.setValue(796)
        else:
            self.combo_yeti_size.setCurrentText("Custom")
            self.spin_custom_yeti.setValue(yeti_size)

        notif_mode = cfg.get("notification_mode", "native")
        idx = self.combo_notif_mode.findData(notif_mode)
        self.combo_notif_mode.setCurrentIndex(max(0, idx))

        style = cfg.get("quote_style", "Unhinged")
        qidx = self.combo_quote_style.findText(style)
        self.combo_quote_style.setCurrentIndex(max(0, qidx))
        self.txt_custom_quote.setText(cfg.get("custom_quote", "Please drink some water."))

        self.chk_interactive.setChecked(bool(cfg.get("interactive_actions", True)))
        self.chk_sound.setChecked(bool(cfg.get("play_sound", True)))
        self._selected_sound_file = str(cfg.get("sound_file", "") or "")
        self._refresh_sound_label()
        self.chk_autostart.setChecked(is_autostart_enabled())

        self._update_mode_states()
        self._update_notif_mode_states()
        self._update_quote_states()
        self._update_sound_states()
        self._update_goal_preview()

    def _update_mode_states(self) -> None:
        is_sched = self.rb_scheduled.isChecked()
        self.slider_scheduled.setEnabled(is_sched)
        self.spin_scheduled.setEnabled(is_sched)
        self.slider_rand_min.setEnabled(not is_sched)
        self.spin_rand_min.setEnabled(not is_sched)
        self.slider_rand_max.setEnabled(not is_sched)
        self.spin_rand_max.setEnabled(not is_sched)

    def _on_min_changed(self, val: int) -> None:
        if self.spin_rand_max.value() < val:
            self.spin_rand_max.setValue(val)

    def _on_max_changed(self, val: int) -> None:
        if self.spin_rand_min.value() > val:
            self.spin_rand_min.setValue(val)

    def _get_yeti_size(self) -> int:
        choice = self.combo_yeti_size.currentText()
        if "1.39L" in choice:
            return 1390
        if "796" in choice:
            return 796
        return self.spin_custom_yeti.value()

    def _on_yeti_changed(self, text: str) -> None:
        is_custom = text == "Custom"
        self.lbl_custom_yeti.setVisible(is_custom)
        self.spin_custom_yeti.setVisible(is_custom)
        self._update_goal_preview()

    def _update_goal_preview(self) -> None:
        goal = self.spin_daily_goal.value()
        yeti_size = self._get_yeti_size()
        refills = goal / yeti_size if yeti_size > 0 else 0
        self.lbl_equates.setText(f"{refills:.1f} Yeti Refills per day")

    def _update_notif_mode_states(self) -> None:
        is_native = self.combo_notif_mode.currentData() == "native"
        self.chk_interactive.setEnabled(is_native)

    def _update_quote_states(self) -> None:
        is_custom = self.combo_quote_style.currentText() == "Custom"
        self.txt_custom_quote.setEnabled(is_custom)

    def _update_sound_states(self) -> None:
        enabled = self.chk_sound.isChecked()
        self.btn_choose_sound.setEnabled(enabled)
        self.btn_reset_sound.setEnabled(enabled)
        self.btn_test_sound.setEnabled(enabled)

    def _refresh_sound_label(self) -> None:
        if self._selected_sound_file and os.path.exists(self._selected_sound_file):
            self.lbl_sound_file.setText(f"Custom: {Path(self._selected_sound_file).name}")
        else:
            self.lbl_sound_file.setText("Default: drop.wav")

    def _on_choose_sound(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Reminder Audio Cue",
            str(Path.home()),
            "Audio Files (*.wav *.oga *.ogg *.mp3 *.flac);;All Files (*)",
        )
        if path:
            self._selected_sound_file = path
            self._refresh_sound_label()

    def _on_reset_sound(self) -> None:
        self._selected_sound_file = ""
        self._refresh_sound_label()

    def _on_test_sound(self) -> None:
        path = resolve_sound_path(self._selected_sound_file)
        if path:
            play_sound(path)
        else:
            self.show_toast("⚠️ No audio file found to play.", is_error=True)

    def _on_log_full_yeti(self) -> None:
        yeti_size = int(self.engine.config.get("yeti_size_ml", 1390))
        self.engine.record_drink(ml=yeti_size)
        self.show_toast(f"🧊 Logged full Yeti ({yeti_size} ml)!")

    def _on_reset_today(self) -> None:
        reply = QMessageBox.question(
            self,
            "Reset Today's Intake",
            "Reset today's logged water intake back to 0 ml?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.engine.reset_today_intake()
            self.show_toast("🔄 Today's hydration intake reset to 0 ml.")

    def _on_stop_or_resume_clicked(self) -> None:
        if self.engine.state == STATE_STOPPED:
            self.engine.resume()
            self.show_toast("▶ Hydration reminders resumed!")
        else:
            self.engine.stop_for_now()
            self.show_toast("🛑 Reminders halted for this session. Great hydration!")

    def refresh_live_status(self) -> None:
        cfg = self.engine.config
        consumed = int(cfg.get("consumed_today_ml", 0))
        goal = max(1, int(cfg.get("daily_goal_ml", 2000)))
        amt = int(cfg.get("amount_per_drink_ml", 250))
        yeti_size = max(1, int(cfg.get("yeti_size_ml", 1390)))

        pct = min(100, int((consumed / goal) * 100))
        self.progress_bar.setMaximum(goal)
        self.progress_bar.setValue(min(consumed, goal))
        self.progress_bar.setFormat(f"{consumed} / {goal} ml ({pct}%)")

        refills_done = consumed / yeti_size
        total_refills = goal / yeti_size
        self.lbl_intake_summary.setText(
            f"💧 {consumed} / {goal} ml ({refills_done:.1f} / {total_refills:.1f} Yeti Refills)"
        )
        self.btn_log_drink.setText(f"💧 Log Drink (+{amt} ml)")
        self.btn_log_yeti.setText(f"🧊 Full Yeti (+{yeti_size} ml)")

        if self.engine.state == STATE_STOPPED:
            self.btn_stop_enough.setObjectName("ResumeBtn")
            self.btn_stop_enough.setText("▶ Resume Hydration Reminders")
        else:
            self.btn_stop_enough.setObjectName("StopEnoughBtn")
            self.btn_stop_enough.setText("🛑 Stop Notifications / I've Drunk Enough")
        # Force QSS refresh when objectName switches
        self.btn_stop_enough.style().unpolish(self.btn_stop_enough)
        self.btn_stop_enough.style().polish(self.btn_stop_enough)

        self._update_countdown_label()

    def _update_countdown_label(self) -> None:
        if not self.isVisible():
            return
        if self.engine.state == STATE_STOPPED:
            self.lbl_state.setText("🛑 Stopped — Drunk Enough for Now (Reminders Halted)")
            return

        rem = self.engine.get_remaining_seconds()
        mins, secs = divmod(rem, 60)
        hours, mins = divmod(mins, 60)
        time_str = f"{hours}h {mins:02d}m" if hours else f"{mins}m {secs:02d}s"

        if self.engine.state == STATE_SNOOZED:
            reason = self.engine.snooze_reason
            self.lbl_state.setText(f"⏸️ Paused ({reason}) — Resumes in {time_str}")
        else:
            mode_name = "Fixed" if int(self.engine.config.get("mode", 2)) == 1 else "Random Ambush"
            self.lbl_state.setText(f"🟢 Active ({mode_name}) — Next ambush in {time_str}")

    def show_toast(self, message: str, is_error: bool = False) -> None:
        bg = "#991b1b" if is_error else "#065f46"
        border = "#ef4444" if is_error else "#10b981"
        self.lbl_toast.setStyleSheet(
            f"background-color: {bg}; color: #ffffff; border: 1px solid {border}; font-weight: bold; padding: 6px; border-radius: 6px;"
        )
        self.lbl_toast.setText(message)
        QTimer.singleShot(4000, self._clear_toast)

    def _clear_toast(self) -> None:
        self.lbl_toast.setText("")
        self.lbl_toast.setStyleSheet("")

    def on_save_clicked(self) -> None:
        new_cfg: Dict[str, Any] = {
            "mode": 1 if self.rb_scheduled.isChecked() else 2,
            "scheduled_interval": self.spin_scheduled.value(),
            "random_min": min(self.spin_rand_min.value(), self.spin_rand_max.value()),
            "random_max": max(self.spin_rand_min.value(), self.spin_rand_max.value()),
            "quiet_start": self.time_quiet_start.time().toString("HH:mm"),
            "quiet_end": self.time_quiet_end.time().toString("HH:mm"),
            "daily_goal_ml": self.spin_daily_goal.value(),
            "yeti_size_ml": self._get_yeti_size(),
            "amount_per_drink_ml": self.spin_drink_amt.value(),
            "notification_mode": self.combo_notif_mode.currentData() or "native",
            "quote_style": self.combo_quote_style.currentText(),
            "custom_quote": self.txt_custom_quote.text().strip() or "Please drink some water.",
            "interactive_actions": self.chk_interactive.isChecked(),
            "play_sound": self.chk_sound.isChecked(),
            "sound_file": self._selected_sound_file,
        }

        self.engine.apply_config(new_cfg)
        autostart_ok = set_autostart_enabled(self.chk_autostart.isChecked())

        if autostart_ok:
            self.show_toast("💾 Settings saved and applied!")
        else:
            self.show_toast("⚠️ Settings saved, but autostart file update failed.", is_error=True)


class YetiTrayController:
    """Manages the persistent System Tray icon (SNI) and context menu."""

    def __init__(self, app: QApplication, engine: HydrationEngine, window: SettingsWindow):
        self.app = app
        self.engine = engine
        self.window = window
        self._last_trigger_ts = 0.0

        icon_path = resolve_icon_path(engine.config.get("icon_file", ""))
        tray_icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon.fromTheme("dialog-information")

        self.tray = QSystemTrayIcon(tray_icon, parent=app)
        self.tray.activated.connect(self._on_activated)

        self._build_menu()
        self.engine.state_changed.connect(self.update_tray_state)
        self.engine.fallback_tray_message.connect(
            lambda title, body: self.tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 8000)
        )
        self.update_tray_state()

    def _build_menu(self) -> None:
        self.menu = QMenu()

        self.act_open = QAction("Open Settings / Dashboard", self.menu)
        self.act_open.triggered.connect(self.show_settings)
        self.menu.addAction(self.act_open)

        self.act_log = QAction("💧 Log Drink", self.menu)
        self.act_log.triggered.connect(lambda: self.engine.record_drink())
        self.menu.addAction(self.act_log)

        self.menu.addSeparator()

        # Pause / Snooze submenu
        self.pause_menu = QMenu("Pause / Snooze Notifications", self.menu)
        act_30m = QAction("30m", self.pause_menu)
        act_30m.triggered.connect(lambda: self.engine.snooze(30, "30m"))
        act_1h = QAction("1h", self.pause_menu)
        act_1h.triggered.connect(lambda: self.engine.snooze(60, "1h"))
        act_rod = QAction("Rest of Day", self.pause_menu)
        act_rod.triggered.connect(self.engine.snooze_rest_of_day)

        self.pause_menu.addAction(act_30m)
        self.pause_menu.addAction(act_1h)
        self.pause_menu.addAction(act_rod)
        self.menu.addMenu(self.pause_menu)

        self.act_resume = QAction("▶ Resume Notifications", self.menu)
        self.act_resume.triggered.connect(self.engine.resume)
        self.menu.addAction(self.act_resume)

        self.act_stop = QAction("Stop / Mute for Now", self.menu)
        self.act_stop.triggered.connect(self.engine.stop_for_now)
        self.menu.addAction(self.act_stop)

        self.menu.addSeparator()

        self.act_quit = QAction("Quit", self.menu)
        self.act_quit.triggered.connect(self.quit_application)
        self.menu.addAction(self.act_quit)

        self.tray.setContextMenu(self.menu)

    def show(self) -> None:
        self.tray.show()

    def show_settings(self) -> None:
        self.window.load_from_config()
        self.window.refresh_live_status()
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def toggle_window(self) -> None:
        if self.window.isVisible() and not self.window.isMinimized():
            self.window.hide()
        else:
            self.show_settings()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        now = time.monotonic()
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._last_trigger_ts = now
            self.toggle_window()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Avoid double-toggling when X11/platforms emit Trigger followed immediately by DoubleClick
            if now - self._last_trigger_ts > 0.35:
                self.toggle_window()

    def update_tray_state(self) -> None:
        cfg = self.engine.config
        consumed = int(cfg.get("consumed_today_ml", 0))
        goal = int(cfg.get("daily_goal_ml", 2000))
        amt = int(cfg.get("amount_per_drink_ml", 250))

        self.act_log.setText(f"💧 Log Drink (+{amt} ml)")
        is_stopped = self.engine.state == STATE_STOPPED
        is_snoozed = self.engine.state == STATE_SNOOZED

        self.act_resume.setVisible(is_stopped or is_snoozed)
        self.act_stop.setEnabled(not is_stopped)

        if is_stopped:
            status_text = "Stopped / Muted for Now"
        elif is_snoozed:
            rem_mins = max(1, int(self.engine.get_remaining_seconds() / 60))
            status_text = f"Paused ({self.engine.snooze_reason}, ~{rem_mins}m left)"
        else:
            rem_mins = max(0, int(self.engine.get_remaining_seconds() / 60))
            status_text = f"Next ambush in ~{rem_mins}m"

        self.tray.setToolTip(f"YetiAmbush 💧\n{status_text}\nToday: {consumed} / {goal} ml")

    def quit_application(self) -> None:
        self.window.allow_quit()
        self.engine.shutdown()
        self.tray.hide()
        self.window.close()
        self.app.quit()
