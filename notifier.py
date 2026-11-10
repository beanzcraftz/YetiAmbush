"""Notification delivery, audio cues, and visual ambush popup for YetiAmbush."""

import os
import shutil
import subprocess
import sys
from typing import Optional

from PyQt6.QtCore import QThread, QUrl, Qt, pyqtSignal
from PyQt6.QtDBus import QDBusInterface, QDBusMessage
from PyQt6.QtGui import QFont, QGuiApplication, QIcon, QKeySequence, QPixmap, QShortcut
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import APP_NAME

_SOUND_CACHE: Optional[QSoundEffect] = None


def play_sound(sound_path: Optional[str]) -> None:
    """Play an alert audio file asynchronously via PipeWire/Pulse/ALSA or QSoundEffect."""
    if not sound_path or not os.path.exists(sound_path):
        return

    players = ["pw-play", "paplay", "aplay", "canberra-gtk-play"]
    for player in players:
        player_bin = shutil.which(player)
        if not player_bin:
            continue
        cmd = [player_bin, "-f", sound_path] if player == "canberra-gtk-play" else [player_bin, sound_path]
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            return
        except Exception:
            continue

    # QtMultimedia fallback if CLI audio utilities are missing
    global _SOUND_CACHE
    try:
        effect = QSoundEffect()
        effect.setSource(QUrl.fromLocalFile(sound_path))
        effect.setVolume(0.9)
        effect.play()
        _SOUND_CACHE = effect
    except Exception as exc:
        print(f"[{APP_NAME}] Could not play audio cue: {exc}", file=sys.stderr)


def send_dbus_notification(
    summary: str,
    body: str,
    icon_path: str = "",
    urgency: int = 2,
    timeout_ms: int = 0,
) -> bool:
    """Send a notification directly over org.freedesktop.Notifications D-Bus."""
    try:
        iface = QDBusInterface(
            "org.freedesktop.Notifications",
            "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications",
        )
        if not iface.isValid():
            return False
        hints = {"urgency": urgency}
        reply = iface.call(
            "Notify",
            APP_NAME,
            0,  # replaces_id
            icon_path or "dialog-information",
            summary,
            body,
            [],  # actions
            hints,
            timeout_ms,
        )
        return reply.type() != QDBusMessage.MessageType.ErrorMessage
    except Exception:
        return False


def send_simple_notification(summary: str, body: str, icon_path: str = "", urgency: str = "normal") -> None:
    """Send a fire-and-forget desktop notification via notify-send or D-Bus fallback."""
    notify_bin = shutil.which("notify-send")
    if notify_bin:
        try:
            subprocess.Popen(
                [notify_bin, "-u", urgency, "-a", APP_NAME, "-i", icon_path or "dialog-information", summary, body],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            return
        except Exception:
            pass
    urgency_int = 2 if urgency == "critical" else (0 if urgency == "low" else 1)
    send_dbus_notification(summary, body, icon_path, urgency=urgency_int)


class NotificationThread(QThread):
    """Non-blocking worker thread running `notify-send -u critical` with action support."""

    action_triggered = pyqtSignal(str)

    def __init__(
        self,
        title: str,
        body: str,
        icon_path: str,
        interactive_actions: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.title = title
        self.body = body
        self.icon_path = icon_path
        self.interactive_actions = interactive_actions
        self._proc: Optional[subprocess.Popen] = None
        self._cancelled = False

    def cancel(self) -> None:
        """Terminate an in-flight waiting notification immediately without blocking the UI."""
        self._cancelled = True
        self.requestInterruption()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    def run(self) -> None:
        notify_bin = shutil.which("notify-send")
        if not notify_bin:
            ok = send_dbus_notification(self.title, self.body, self.icon_path, urgency=2, timeout_ms=0)
            self.action_triggered.emit("dismissed" if ok else "fallback_needed")
            return

        base_cmd = [
            notify_bin,
            "-u",
            "critical",
            "-a",
            APP_NAME,
            "-i",
            self.icon_path or "dialog-information",
        ]

        if not self.interactive_actions:
            try:
                subprocess.run(base_cmd + [self.title, self.body], check=False, timeout=15)
                self.action_triggered.emit("dismissed")
            except Exception:
                self.action_triggered.emit("fallback_needed")
            return

        action_cmd = base_cmd + [
            "-A",
            "drink=Drank It 💧",
            "-A",
            "snooze5=5m ⏰",
            "-A",
            "snooze15=15m ⏳",
            self.title,
            self.body,
        ]
        try:
            self._proc = subprocess.Popen(
                action_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            # Poll in short increments so stop/quit can interrupt immediately
            elapsed_ms = 0
            max_wait_ms = 3600 * 1000
            while self._proc.poll() is None:
                if self._cancelled or self.isInterruptionRequested():
                    self._proc.terminate()
                    try:
                        self._proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        self._proc.kill()
                    return
                if elapsed_ms >= max_wait_ms:
                    self._proc.kill()
                    self.action_triggered.emit("dismissed")
                    return
                self.msleep(150)
                elapsed_ms += 150

            stdout, _ = self._proc.communicate(timeout=1)
            if self._cancelled:
                return
            action = (stdout or "").strip()
            if action in ("drink", "snooze5", "snooze15"):
                self.action_triggered.emit(action)
            else:
                self.action_triggered.emit("dismissed")
        except Exception as exc:
            if not self._cancelled:
                print(f"[{APP_NAME}] notify-send worker failed: {exc}", file=sys.stderr)
                self.action_triggered.emit("fallback_needed")
        finally:
            self._proc = None


class AmbushPopupWindow(QWidget):
    """Dark-themed always-on-top visual popup dialog for ADHD ambush alerts."""

    drank_clicked = pyqtSignal()
    snooze_clicked = pyqtSignal(int)
    stop_clicked = pyqtSignal()
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("YetiAmbush 💧")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFixedWidth(520)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            AmbushPopupWindow {
                background-color: #141923;
                border: 2px solid #38bdf8;
                border-radius: 14px;
            }
            QLabel {
                color: #f1f5f9;
            }
            QProgressBar {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                text-align: center;
                color: #f8fafc;
                font-weight: bold;
                min-height: 20px;
            }
            QProgressBar::chunk {
                background-color: #0ea5e9;
                border-radius: 5px;
            }
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(14)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(12)

        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(44, 44)
        header.addWidget(self.lbl_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.lbl_title = QLabel("YETI AMBUSH 💧")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        self.lbl_title.setFont(title_font)
        self.lbl_title.setStyleSheet("color: #38bdf8; letter-spacing: 0.5px;")

        self.lbl_sub = QLabel("Hydration checkpoint — acknowledge to dismiss")
        self.lbl_sub.setStyleSheet("color: #94a3b8; font-size: 11px;")
        title_col.addWidget(self.lbl_title)
        title_col.addWidget(self.lbl_sub)
        header.addLayout(title_col)
        header.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 30)
        btn_close.setToolTip("Dismiss reminder")
        btn_close.setStyleSheet(
            "QPushButton { background: transparent; color: #94a3b8; border: none; font-size: 15px; border-radius: 6px; }"
            "QPushButton:hover { background: #1e293b; color: #f8fafc; }"
        )
        btn_close.clicked.connect(self._on_dismiss)
        header.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignTop)
        outer.addLayout(header)

        # Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #263144; max-height: 1px; border: none;")
        outer.addWidget(sep)

        # Quote message
        self.lbl_quote = QLabel("")
        quote_font = QFont()
        quote_font.setPointSize(15)
        quote_font.setBold(True)
        self.lbl_quote.setFont(quote_font)
        self.lbl_quote.setWordWrap(True)
        self.lbl_quote.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_quote.setMinimumHeight(80)
        self.lbl_quote.setStyleSheet("padding: 8px 4px; color: #ffffff;")
        outer.addWidget(self.lbl_quote)

        # Progress bar
        self.progress = QProgressBar()
        outer.addWidget(self.progress)

        # Primary CTA
        self.btn_drank = QPushButton("💧 I Drank It!")
        self.btn_drank.setMinimumHeight(44)
        self.btn_drank.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_drank.setStyleSheet(
            "QPushButton { background-color: #0284c7; color: white; font-size: 14px; font-weight: bold; border-radius: 8px; border: none; }"
            "QPushButton:hover { background-color: #0369a1; }"
        )
        self.btn_drank.clicked.connect(self._on_drank)
        outer.addWidget(self.btn_drank)

        # Secondary actions row
        sec_row = QHBoxLayout()
        sec_row.setSpacing(10)

        sec_btn_style = (
            "QPushButton { background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 7px; padding: 6px 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #283548; color: #ffffff; }"
        )
        btn_s5 = QPushButton("⏰ Snooze 5m")
        btn_s5.setMinimumHeight(36)
        btn_s5.setStyleSheet(sec_btn_style)
        btn_s5.clicked.connect(lambda: self._on_snooze(5))

        btn_s15 = QPushButton("⏳ Snooze 15m")
        btn_s15.setMinimumHeight(36)
        btn_s15.setStyleSheet(sec_btn_style)
        btn_s15.clicked.connect(lambda: self._on_snooze(15))

        btn_stop = QPushButton("🛑 Drunk Enough")
        btn_stop.setMinimumHeight(36)
        btn_stop.setToolTip("Stop notifications for the rest of this session")
        btn_stop.setStyleSheet(
            "QPushButton { background-color: #451a1d; color: #fca5a5; border: 1px solid #7f1d1d; border-radius: 7px; padding: 6px 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #7f1d1d; color: #ffffff; }"
        )
        btn_stop.clicked.connect(self._on_stop)

        sec_row.addWidget(btn_s5)
        sec_row.addWidget(btn_s15)
        sec_row.addWidget(btn_stop)
        outer.addLayout(sec_row)

        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self._on_drank)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, self._on_drank)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_dismiss)

    def show_ambush(
        self,
        quote: str,
        icon_path: str,
        consumed_ml: int,
        goal_ml: int,
        amt_ml: int,
        is_test: bool = False,
    ) -> None:
        """Populate and display the popup centered on the primary screen."""
        self.lbl_title.setText("YETI AMBUSH 💧 [TEST]" if is_test else "YETI AMBUSH 💧")
        self.lbl_quote.setText(quote)
        self.btn_drank.setText(f"💧 I Drank It! (+{amt_ml} ml)")

        if icon_path and os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_icon.setPixmap(pix)
            self.setWindowIcon(QIcon(icon_path))

        pct = min(100, int((consumed_ml / goal_ml) * 100)) if goal_ml > 0 else 0
        self.progress.setMaximum(max(1, goal_ml))
        self.progress.setValue(min(consumed_ml, max(1, goal_ml)))
        self.progress.setFormat(f"{consumed_ml} / {goal_ml} ml ({pct}%)")

        self.adjustSize()
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)

        self.show()
        self.raise_()
        self.activateWindow()

    def _on_drank(self) -> None:
        self.hide()
        self.drank_clicked.emit()

    def _on_snooze(self, minutes: int) -> None:
        self.hide()
        self.snooze_clicked.emit(minutes)

    def _on_stop(self) -> None:
        self.hide()
        self.stop_clicked.emit()

    def _on_dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()
