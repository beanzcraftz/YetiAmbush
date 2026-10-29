#!/usr/bin/env python3
"""
YetiAmbush Configuration GUI for KDE Plasma (PyQt6)
A native, lightweight configuration manager for the YetiAmbush background daemon.

Features:
- Native KDE Plasma look and feel via PyQt6.
- Full two-way data binding with ~/.config/yetiambush/config.json.
- Generous spacing, padding, and minimum widget heights (>= 35px) for KDE themes.
- Custom non-scrolling inputs (NoWheelSpinBox, NoWheelComboBox, NoWheelTimeEdit) to prevent accidental changes.
- Yeti bottle size presets (1.39L, 796ml, Custom) with live refill calculations.
- Clean text with no mnemonic ampersand accelerator glitches.
- "Save and Apply" triggers atomic file write and sends SIGHUP to the daemon via `yetiambush-daemon --reload`.
- In-app status card and toast feedback.
- "Test Ambush" button to verify sound and notification styling on the spot.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from PyQt6.QtCore import QTime, QTimer, Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "yetiambush"
CONFIG_FILE = CONFIG_DIR / "config.json"
STATE_FILE = CONFIG_DIR / "state.json"
ICON_PATH = CONFIG_DIR / "icon.png"

DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": 2,  # 1 = Scheduled Interval, 2 = Random Ambush
    "scheduled_interval": 45,
    "random_min": 30,
    "random_max": 90,
    "quiet_start": "22:00",
    "quiet_end": "08:00",
    "quote_style": "Unhinged",
    "custom_quote": "Please drink some water.",
    "daily_goal_ml": 2000,
    "amount_per_drink_ml": 250,
    "yeti_size_ml": 1390,
    "consumed_today_ml": 0,
    "last_drink_date": str(datetime.date.today()),
    "play_sound": True,
    "sound_file": "",
    "icon_file": "",
    "interactive_actions": True,
}


def load_config() -> Dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return DEFAULT_CONFIG.copy()


def save_config(config_data: Dict[str, Any]) -> bool:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    today_str = str(datetime.date.today())
    if config_data.get("last_drink_date") != today_str:
        config_data["consumed_today_ml"] = 0
        config_data["last_drink_date"] = today_str
    temp_file = CONFIG_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        temp_file.replace(CONFIG_FILE)
        return True
    except Exception as e:
        print(f"Error saving config: {e}", file=sys.stderr)
        return False


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# Custom widgets that ignore mouse wheel events to prevent accidental value changes while scrolling
class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelTimeEdit(QTimeEdit):
    def wheelEvent(self, event):
        event.ignore()


class YetiAmbushConfigWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.init_ui()
        self.load_values_into_ui()
        self.update_mode_widget_states()
        self.update_quote_style_states()
        self.update_goal_calculation()

        # Periodic refresh of daemon status banner
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_daemon_status)
        self.status_timer.start(5000)
        self.refresh_daemon_status()

    def init_ui(self):
        self.setWindowTitle("YetiAmbush — Hydration Configuration")
        # Generous minimum window size to prevent compression under KDE Plasma
        self.setMinimumSize(650, 750)
        self.resize(680, 820)

        # Window Icon
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        # Root Scroll Area so varying DPI scaling never clips content
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll_area)

        container = QWidget()
        scroll_area.setWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Header Title and Subtitle
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(15, 15, 15, 15)
        header_layout.setSpacing(15)

        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(5)

        header_title = QLabel("💧 YetiAmbush Configuration")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        header_title.setFont(title_font)

        header_sub = QLabel("ADHD-friendly hydration daemon settings for KDE Plasma")
        header_sub.setStyleSheet("color: gray;")

        header_text_layout.addWidget(header_title)
        header_text_layout.addWidget(header_sub)
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Daemon Live Status Card
        self.status_card = QFrame()
        self.status_card.setFrameShape(QFrame.Shape.StyledPanel)
        self.status_card.setStyleSheet("background-color: rgba(31, 83, 141, 0.18); border-radius: 8px;")
        status_card_layout = QHBoxLayout(self.status_card)
        status_card_layout.setContentsMargins(15, 15, 15, 15)
        status_card_layout.setSpacing(15)

        self.lbl_daemon_status = QLabel("Checking daemon status...")
        self.lbl_intake_status = QLabel("")
        status_card_layout.addWidget(self.lbl_daemon_status)
        status_card_layout.addStretch()
        status_card_layout.addWidget(self.lbl_intake_status)
        main_layout.addWidget(self.status_card)

        # -------------------------------------------------------------
        # Group 1: Timing Strategy (Mode Selection)
        # -------------------------------------------------------------
        grp_mode = QGroupBox("Timing Strategy")
        layout_mode = QVBoxLayout(grp_mode)
        layout_mode.setContentsMargins(15, 15, 15, 15)
        layout_mode.setSpacing(15)

        # Sub-Card: Mode 2 (Random Ambush)
        self.frame_mode2 = QFrame()
        self.frame_mode2.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_mode2.setStyleSheet("background-color: rgba(255, 255, 255, 0.03); border-radius: 6px;")
        layout_mode2_card = QVBoxLayout(self.frame_mode2)
        layout_mode2_card.setContentsMargins(15, 15, 15, 15)
        layout_mode2_card.setSpacing(12)

        self.rb_random = QRadioButton("Mode 2: Random Ambush (Recommended for ADHD)")
        rb_font = QFont()
        rb_font.setBold(True)
        self.rb_random.setFont(rb_font)
        self.rb_random.setMinimumHeight(35)
        self.rb_random.toggled.connect(self.update_mode_widget_states)
        layout_mode2_card.addWidget(self.rb_random)

        desc_random = QLabel("Fires reminders unpredictably between min and max bounds to prevent habituation.")
        desc_random.setStyleSheet("color: gray;")
        desc_random.setWordWrap(True)
        layout_mode2_card.addWidget(desc_random)

        # Mode 2 Inputs Row
        self.frame_random_inputs = QFrame()
        layout_random_inputs = QHBoxLayout(self.frame_random_inputs)
        layout_random_inputs.setContentsMargins(0, 5, 0, 0)
        layout_random_inputs.setSpacing(15)

        lbl_min = QLabel("Min Interval:")
        lbl_min.setMinimumHeight(35)
        self.spin_random_min = NoWheelSpinBox()
        self.spin_random_min.setRange(5, 360)
        self.spin_random_min.setSingleStep(5)
        self.spin_random_min.setSuffix(" mins")
        self.spin_random_min.setMinimumHeight(35)
        self.spin_random_min.setMinimumWidth(120)
        self.spin_random_min.valueChanged.connect(self.on_min_interval_changed)

        lbl_max = QLabel("Max Interval:")
        lbl_max.setMinimumHeight(35)
        self.spin_random_max = NoWheelSpinBox()
        self.spin_random_max.setRange(5, 360)
        self.spin_random_max.setSingleStep(5)
        self.spin_random_max.setSuffix(" mins")
        self.spin_random_max.setMinimumHeight(35)
        self.spin_random_max.setMinimumWidth(120)

        layout_random_inputs.addWidget(lbl_min)
        layout_random_inputs.addWidget(self.spin_random_min)
        layout_random_inputs.addSpacing(20)
        layout_random_inputs.addWidget(lbl_max)
        layout_random_inputs.addWidget(self.spin_random_max)
        layout_random_inputs.addStretch()

        layout_mode2_card.addWidget(self.frame_random_inputs)
        layout_mode.addWidget(self.frame_mode2)

        # Sub-Card: Mode 1 (Scheduled Chug)
        self.frame_mode1 = QFrame()
        self.frame_mode1.setFrameShape(QFrame.Shape.StyledPanel)
        self.frame_mode1.setStyleSheet("background-color: rgba(255, 255, 255, 0.03); border-radius: 6px;")
        layout_mode1_card = QVBoxLayout(self.frame_mode1)
        layout_mode1_card.setContentsMargins(15, 15, 15, 15)
        layout_mode1_card.setSpacing(12)

        self.rb_scheduled = QRadioButton("Mode 1: Scheduled Chug (Fixed Intervals)")
        self.rb_scheduled.setFont(rb_font)
        self.rb_scheduled.setMinimumHeight(35)
        self.rb_scheduled.toggled.connect(self.update_mode_widget_states)
        layout_mode1_card.addWidget(self.rb_scheduled)

        desc_sched = QLabel("Strict, recurring interval timer (e.g., alert exactly every 45 minutes).")
        desc_sched.setStyleSheet("color: gray;")
        desc_sched.setWordWrap(True)
        layout_mode1_card.addWidget(desc_sched)

        # Mode 1 Inputs Row
        self.frame_scheduled_inputs = QFrame()
        layout_scheduled_inputs = QHBoxLayout(self.frame_scheduled_inputs)
        layout_scheduled_inputs.setContentsMargins(0, 5, 0, 0)
        layout_scheduled_inputs.setSpacing(15)

        lbl_sched = QLabel("Reminder Interval:")
        lbl_sched.setMinimumHeight(35)
        self.spin_scheduled = NoWheelSpinBox()
        self.spin_scheduled.setRange(5, 360)
        self.spin_scheduled.setSingleStep(5)
        self.spin_scheduled.setSuffix(" mins")
        self.spin_scheduled.setMinimumHeight(35)
        self.spin_scheduled.setMinimumWidth(120)

        layout_scheduled_inputs.addWidget(lbl_sched)
        layout_scheduled_inputs.addWidget(self.spin_scheduled)
        layout_scheduled_inputs.addStretch()

        layout_mode1_card.addWidget(self.frame_scheduled_inputs)
        layout_mode.addWidget(self.frame_mode1)

        main_layout.addWidget(grp_mode)

        # -------------------------------------------------------------
        # Group 2: Quiet Hours
        # -------------------------------------------------------------
        grp_quiet = QGroupBox("Quiet Hours")
        layout_quiet = QHBoxLayout(grp_quiet)
        layout_quiet.setContentsMargins(15, 15, 15, 15)
        layout_quiet.setSpacing(15)

        lbl_qstart = QLabel("Sleep and Silence Start:")
        lbl_qstart.setMinimumHeight(35)
        self.time_quiet_start = NoWheelTimeEdit()
        self.time_quiet_start.setDisplayFormat("HH:mm")
        self.time_quiet_start.setMinimumHeight(35)
        self.time_quiet_start.setMinimumWidth(110)

        lbl_qend = QLabel("End:")
        lbl_qend.setMinimumHeight(35)
        self.time_quiet_end = NoWheelTimeEdit()
        self.time_quiet_end.setDisplayFormat("HH:mm")
        self.time_quiet_end.setMinimumHeight(35)
        self.time_quiet_end.setMinimumWidth(110)

        layout_quiet.addWidget(lbl_qstart)
        layout_quiet.addWidget(self.time_quiet_start)
        layout_quiet.addSpacing(25)
        layout_quiet.addWidget(lbl_qend)
        layout_quiet.addWidget(self.time_quiet_end)
        layout_quiet.addStretch()

        main_layout.addWidget(grp_quiet)

        # -------------------------------------------------------------
        # Group 3: Hydration Goals and Tracking
        # -------------------------------------------------------------
        grp_goals = QGroupBox("Daily Hydration Target")
        form_goals = QFormLayout(grp_goals)
        form_goals.setContentsMargins(15, 15, 15, 15)
        form_goals.setSpacing(15)
        form_goals.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.spin_daily_goal = NoWheelSpinBox()
        self.spin_daily_goal.setRange(250, 10000)
        self.spin_daily_goal.setSingleStep(50)
        self.spin_daily_goal.setSuffix(" ml")
        self.spin_daily_goal.setMinimumHeight(35)
        self.spin_daily_goal.valueChanged.connect(self.update_goal_calculation)

        self.combo_yeti_size = NoWheelComboBox()
        self.combo_yeti_size.addItems(["1.39L (1390 ml)", "796 ml", "Custom"])
        self.combo_yeti_size.setMinimumHeight(35)
        self.combo_yeti_size.currentTextChanged.connect(self.on_yeti_size_changed)

        self.spin_custom_yeti = NoWheelSpinBox()
        self.spin_custom_yeti.setRange(100, 5000)
        self.spin_custom_yeti.setSingleStep(50)
        self.spin_custom_yeti.setSuffix(" ml")
        self.spin_custom_yeti.setMinimumHeight(35)
        self.spin_custom_yeti.setValue(1390)
        self.spin_custom_yeti.valueChanged.connect(self.update_goal_calculation)
        self.spin_custom_yeti.setVisible(False)

        self.spin_amount_per_drink = NoWheelSpinBox()
        self.spin_amount_per_drink.setRange(50, 2000)
        self.spin_amount_per_drink.setSingleStep(25)
        self.spin_amount_per_drink.setSuffix(" ml")
        self.spin_amount_per_drink.setMinimumHeight(35)
        self.spin_amount_per_drink.valueChanged.connect(self.update_goal_calculation)

        self.lbl_bottle_calc = QLabel("")
        self.lbl_bottle_calc.setMinimumHeight(35)
        self.lbl_bottle_calc.setStyleSheet("color: #3daee9; font-weight: bold;")

        lbl_dg = QLabel("Daily Goal:")
        lbl_dg.setMinimumHeight(35)
        lbl_ys = QLabel("Yeti Bottle Size:")
        lbl_ys.setMinimumHeight(35)
        self.lbl_cys = QLabel("Custom Yeti Size:")
        self.lbl_cys.setMinimumHeight(35)
        self.lbl_cys.setVisible(False)
        lbl_apd = QLabel("Amount per Drink:")
        lbl_apd.setMinimumHeight(35)
        lbl_eq = QLabel("Equates to:")
        lbl_eq.setMinimumHeight(35)

        form_goals.addRow(lbl_dg, self.spin_daily_goal)
        form_goals.addRow(lbl_ys, self.combo_yeti_size)
        form_goals.addRow(self.lbl_cys, self.spin_custom_yeti)
        form_goals.addRow(lbl_apd, self.spin_amount_per_drink)
        form_goals.addRow(lbl_eq, self.lbl_bottle_calc)

        main_layout.addWidget(grp_goals)

        # -------------------------------------------------------------
        # Group 4: Personality and Notification Behavior
        # -------------------------------------------------------------
        grp_personality = QGroupBox("Notification Personality and Behavior")
        layout_personality = QVBoxLayout(grp_personality)
        layout_personality.setContentsMargins(15, 15, 15, 15)
        layout_personality.setSpacing(15)

        form_quote = QFormLayout()
        form_quote.setContentsMargins(0, 0, 0, 0)
        form_quote.setSpacing(15)

        lbl_qs = QLabel("Quote Style:")
        lbl_qs.setMinimumHeight(35)
        self.combo_quote_style = NoWheelComboBox()
        self.combo_quote_style.addItems(["Unhinged", "Polite", "Mixed", "Custom"])
        self.combo_quote_style.setMinimumHeight(35)
        self.combo_quote_style.currentTextChanged.connect(self.update_quote_style_states)
        form_quote.addRow(lbl_qs, self.combo_quote_style)

        lbl_ct = QLabel("Custom Text:")
        lbl_ct.setMinimumHeight(35)
        self.txt_custom_quote = QLineEdit()
        self.txt_custom_quote.setPlaceholderText("Enter your custom hydration reminder text here...")
        self.txt_custom_quote.setMinimumHeight(35)
        form_quote.addRow(lbl_ct, self.txt_custom_quote)
        layout_personality.addLayout(form_quote)

        # Toggles
        self.chk_sound = QCheckBox("Play sound cue (drop.wav via PipeWire) on alert")
        self.chk_sound.setMinimumHeight(35)
        self.chk_actions = QCheckBox("Show interactive action buttons (I Drank It, Snooze) in Plasma popup")
        self.chk_actions.setMinimumHeight(35)
        layout_personality.addWidget(self.chk_sound)
        layout_personality.addWidget(self.chk_actions)

        main_layout.addWidget(grp_personality)

        # Feedback Toast Area
        self.lbl_toast = QLabel("")
        self.lbl_toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_toast.setMinimumHeight(35)
        self.lbl_toast.setStyleSheet("font-weight: bold; padding: 6px; border-radius: 4px;")
        main_layout.addWidget(self.lbl_toast)

        # Bottom Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(15, 5, 15, 15)
        btn_layout.setSpacing(15)

        self.btn_test = QPushButton("⚡ Test Ambush")
        self.btn_test.setMinimumHeight(40)
        self.btn_test.setToolTip("Sends an immediate critical notification to verify your settings")
        self.btn_test.clicked.connect(self.on_test_ambush_clicked)

        self.btn_reset_intake = QPushButton("🔄 Reset Intake")
        self.btn_reset_intake.setMinimumHeight(40)
        self.btn_reset_intake.setToolTip("Reset today's consumed ml back to 0")
        self.btn_reset_intake.clicked.connect(self.on_reset_intake_clicked)

        self.btn_save = QPushButton("💾 Save and Apply")
        self.btn_save.setDefault(True)
        self.btn_save.setMinimumHeight(40)
        self.btn_save.setStyleSheet("font-weight: bold; padding: 8px 18px;")
        self.btn_save.clicked.connect(self.on_save_clicked)

        btn_layout.addWidget(self.btn_test)
        btn_layout.addWidget(self.btn_reset_intake)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)

        main_layout.addLayout(btn_layout)

    def load_values_into_ui(self):
        mode = self.config.get("mode", 2)
        if mode == 1:
            self.rb_scheduled.setChecked(True)
        else:
            self.rb_random.setChecked(True)

        self.spin_scheduled.setValue(int(self.config.get("scheduled_interval", 45)))
        self.spin_random_min.setValue(int(self.config.get("random_min", 30)))
        self.spin_random_max.setValue(int(self.config.get("random_max", 90)))

        start_str = self.config.get("quiet_start", "22:00")
        end_str = self.config.get("quiet_end", "08:00")
        self.time_quiet_start.setTime(QTime.fromString(start_str, "HH:mm"))
        self.time_quiet_end.setTime(QTime.fromString(end_str, "HH:mm"))

        self.spin_daily_goal.setValue(int(self.config.get("daily_goal_ml", 2000)))
        self.spin_amount_per_drink.setValue(int(self.config.get("amount_per_drink_ml", 250)))

        # Yeti Bottle Size
        yeti_size = int(self.config.get("yeti_size_ml", 1390))
        if yeti_size == 1390:
            self.combo_yeti_size.setCurrentText("1.39L (1390 ml)")
            self.spin_custom_yeti.setValue(1390)
        elif yeti_size == 796:
            self.combo_yeti_size.setCurrentText("796 ml")
            self.spin_custom_yeti.setValue(796)
        else:
            self.combo_yeti_size.setCurrentText("Custom")
            self.spin_custom_yeti.setValue(yeti_size)
        self.on_yeti_size_changed(self.combo_yeti_size.currentText())

        style = self.config.get("quote_style", "Unhinged")
        idx = self.combo_quote_style.findText(style)
        if idx >= 0:
            self.combo_quote_style.setCurrentIndex(idx)
        else:
            self.combo_quote_style.setCurrentText("Unhinged")

        self.txt_custom_quote.setText(self.config.get("custom_quote", "Please drink some water."))
        self.chk_sound.setChecked(bool(self.config.get("play_sound", True)))
        self.chk_actions.setChecked(bool(self.config.get("interactive_actions", True)))

    def update_mode_widget_states(self):
        is_random = self.rb_random.isChecked()
        self.frame_mode2.setEnabled(is_random)
        self.frame_mode1.setEnabled(not is_random)

    def on_min_interval_changed(self, val):
        if self.spin_random_max.value() < val:
            self.spin_random_max.setValue(val)

    def get_current_yeti_size(self) -> int:
        choice = self.combo_yeti_size.currentText()
        if "1.39L" in choice:
            return 1390
        elif "796" in choice:
            return 796
        else:
            return self.spin_custom_yeti.value()

    def on_yeti_size_changed(self, text: str):
        is_custom = (text == "Custom")
        self.lbl_cys.setVisible(is_custom)
        self.spin_custom_yeti.setVisible(is_custom)
        self.update_goal_calculation()

    def update_quote_style_states(self):
        is_custom = self.combo_quote_style.currentText() == "Custom"
        self.txt_custom_quote.setEnabled(is_custom)
        if is_custom:
            self.txt_custom_quote.setFocus()

    def update_goal_calculation(self):
        goal = self.spin_daily_goal.value()
        yeti_size = self.get_current_yeti_size()
        refills = round(goal / yeti_size, 1) if yeti_size > 0 else 0
        self.lbl_bottle_calc.setText(f"Equates to: {refills:.1f} Yeti Refills per day")

    def refresh_daemon_status(self):
        state = load_state()
        pid = state.get("pid")
        is_alive = False

        if pid:
            try:
                os.kill(pid, 0)
                is_alive = True
            except OSError:
                is_alive = False

        if is_alive:
            rem = state.get("minutes_remaining", 0)
            self.lbl_daemon_status.setText(f"🟢 <b>Daemon:</b> Active (PID {pid}) — Next ambush in ~{rem}m")
        else:
            self.lbl_daemon_status.setText("🔴 <b>Daemon:</b> Inactive (run <code>systemctl --user start yetiambush</code>)")

        cfg = load_config()
        today_str = str(datetime.date.today())
        if cfg.get("last_drink_date") != today_str:
            cfg["consumed_today_ml"] = 0
            cfg["last_drink_date"] = today_str
            save_config(cfg)
        consumed = cfg.get("consumed_today_ml", 0)
        goal = cfg.get("daily_goal_ml", 2000)
        yeti_size = int(cfg.get("yeti_size_ml", 1390)) or 1390
        refills_done = consumed / yeti_size
        total_refills = goal / yeti_size
        pct = (consumed / goal * 100) if goal > 0 else 0
        self.lbl_intake_status.setText(f"💧 Today: <b>{consumed}/{goal} ml</b> [{pct:.0f}%] ({refills_done:.1f}/{total_refills:.1f} Yeti Refills)")

    def show_toast(self, message: str, is_error: bool = False):
        bg = "#da4453" if is_error else "#27ae60"
        self.lbl_toast.setStyleSheet(f"background-color: {bg}; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.lbl_toast.setText(message)
        QTimer.singleShot(4000, lambda: self.lbl_toast.setText(""))

    def on_save_clicked(self):
        if self.rb_random.isChecked():
            min_val = self.spin_random_min.value()
            max_val = self.spin_random_max.value()
            if min_val > max_val:
                self.spin_random_max.setValue(min_val)

        self.config["mode"] = 2 if self.rb_random.isChecked() else 1
        self.config["scheduled_interval"] = self.spin_scheduled.value()
        self.config["random_min"] = self.spin_random_min.value()
        self.config["random_max"] = self.spin_random_max.value()
        self.config["quiet_start"] = self.time_quiet_start.time().toString("HH:mm")
        self.config["quiet_end"] = self.time_quiet_end.time().toString("HH:mm")
        self.config["daily_goal_ml"] = self.spin_daily_goal.value()
        self.config["amount_per_drink_ml"] = self.spin_amount_per_drink.value()
        self.config["yeti_size_ml"] = self.get_current_yeti_size()
        self.config["quote_style"] = self.combo_quote_style.currentText()
        self.config["custom_quote"] = self.txt_custom_quote.text().strip()
        self.config["play_sound"] = self.chk_sound.isChecked()
        self.config["interactive_actions"] = self.chk_actions.isChecked()

        if not save_config(self.config):
            self.show_toast("❌ Failed to save configuration file!", is_error=True)
            return

        reload_success = self.trigger_daemon_reload()

        if reload_success:
            self.show_toast("✅ Settings saved and applied to background daemon!")
        else:
            self.show_toast("⚠️ Settings saved, but daemon could not be reloaded (is it running?)", is_error=True)

        self.refresh_daemon_status()

    def trigger_daemon_reload(self) -> bool:
        daemon_bin = shutil.which("yetiambush-daemon")
        if daemon_bin:
            try:
                res = subprocess.run([daemon_bin, "--reload"], capture_output=True, timeout=3)
                return res.returncode == 0
            except Exception:
                pass

        state = load_state()
        pid = state.get("pid")
        if pid:
            try:
                import signal
                os.kill(pid, signal.SIGHUP)
                return True
            except OSError:
                pass

        return False

    def on_test_ambush_clicked(self):
        daemon_bin = shutil.which("yetiambush-daemon")
        if not daemon_bin:
            local_bin = Path.home() / ".local/bin/yetiambush-daemon"
            if local_bin.exists():
                daemon_bin = str(local_bin)

        if daemon_bin:
            try:
                subprocess.Popen([daemon_bin, "--test"])
                self.show_toast("⚡ Test ambush notification dispatched!")
                return
            except Exception as e:
                self.show_toast(f"❌ Failed to run test: {e}", is_error=True)
        else:
            self.show_toast("❌ 'yetiambush-daemon' binary not found in PATH!", is_error=True)

    def on_reset_intake_clicked(self):
        reply = QMessageBox.question(
            self,
            "Reset Intake",
            "Are you sure you want to reset today's consumed water counter back to 0 ml?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config["consumed_today_ml"] = 0
            save_config(self.config)
            self.trigger_daemon_reload()
            self.refresh_daemon_status()
            self.show_toast("🔄 Today's hydration counter reset to 0 ml.")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("YetiAmbush")
    app.setDesktopFileName("yetiambush-config")
    window = YetiAmbushConfigWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
