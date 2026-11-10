"""Non-blocking hydration scheduling engine and state machine for YetiAmbush."""

import datetime
import random
import time
from typing import Any, Dict, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from config import (
    APP_NAME,
    apply_day_rollover,
    get_quote,
    is_quiet_hour,
    load_config,
    resolve_icon_path,
    resolve_sound_path,
    save_config,
    save_state,
)
from notifier import (
    AmbushPopupWindow,
    NotificationThread,
    play_sound,
    send_simple_notification,
)

STATE_ACTIVE = "active"
STATE_SNOOZED = "snoozed"
STATE_STOPPED = "stopped"


class HydrationEngine(QObject):
    """Manages non-blocking reminder timers, notifications, intake tracking, and rollovers."""

    state_changed = pyqtSignal()
    fallback_tray_message = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config: Dict[str, Any] = load_config()
        self.state: str = STATE_ACTIVE
        self.snooze_reason: str = ""
        self.target_timestamp: float = 0.0
        self.ambush_in_flight: bool = False
        self._notify_thread: Optional[NotificationThread] = None

        self.popup = AmbushPopupWindow()
        self.popup.drank_clicked.connect(self._on_popup_drank)
        self.popup.snooze_clicked.connect(self._on_popup_snooze)
        self.popup.stop_clicked.connect(self.stop_for_now)
        self.popup.dismissed.connect(self._on_popup_dismissed)

        # Non-blocking 1-second timer drives countdown, rollover, and quiet hours
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

    def start(self) -> None:
        """Schedule the initial reminder and start the non-blocking timer."""
        self.state = STATE_ACTIVE
        self.snooze_reason = ""
        self._schedule_next_interval()
        self._tick_timer.start()
        self.state_changed.emit()

    def _calculate_interval_minutes(self) -> int:
        mode = int(self.config.get("mode", 2))
        if mode == 1:
            return max(1, int(self.config.get("scheduled_interval", 45)))
        min_val = max(1, int(self.config.get("random_min", 30)))
        max_val = max(1, int(self.config.get("random_max", 90)))
        if min_val > max_val:
            min_val, max_val = max_val, min_val
        return random.randint(min_val, max_val)

    def _schedule_next_interval(self) -> None:
        minutes = self._calculate_interval_minutes()
        self.target_timestamp = time.time() + (minutes * 60)
        self._persist_runtime_state()

    def _cancel_inflight_ambush(self) -> None:
        self.ambush_in_flight = False
        if self.popup.isVisible():
            self.popup.hide()
        if self._notify_thread and self._notify_thread.isRunning():
            self._notify_thread.cancel()
            self._notify_thread.wait(500)
            self._notify_thread = None

    def stop_for_now(self) -> None:
        """Immediately halt active reminder timers and clear open prompts without freezing UI."""
        self._tick_timer.stop()
        self._cancel_inflight_ambush()
        self.state = STATE_STOPPED
        self.snooze_reason = "Stopped for this session"
        self.target_timestamp = 0.0
        self._persist_runtime_state()
        self.state_changed.emit()

    def resume(self) -> None:
        """Resume reminder timers from stopped or snoozed state."""
        self._cancel_inflight_ambush()
        self.state = STATE_ACTIVE
        self.snooze_reason = ""
        self._schedule_next_interval()
        if not self._tick_timer.isActive():
            self._tick_timer.start()
        self.state_changed.emit()

    def snooze(self, minutes: int, label: str = "") -> None:
        """Pause notifications for the specified duration in minutes."""
        self._cancel_inflight_ambush()
        self.state = STATE_SNOOZED
        self.snooze_reason = label or f"{minutes}m"
        self.target_timestamp = time.time() + (minutes * 60)
        if not self._tick_timer.isActive():
            self._tick_timer.start()
        self._persist_runtime_state()
        self.state_changed.emit()

    def snooze_rest_of_day(self) -> None:
        """Pause notifications until midnight (start of next calendar day)."""
        now = datetime.datetime.now()
        tomorrow = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
        minutes = max(1, int((tomorrow - now).total_seconds() / 60))
        self._cancel_inflight_ambush()
        self.state = STATE_SNOOZED
        self.snooze_reason = "Rest of Day"
        self.target_timestamp = tomorrow.timestamp()
        if not self._tick_timer.isActive():
            self._tick_timer.start()
        self._persist_runtime_state()
        self.state_changed.emit()

    def record_drink(self, ml: Optional[int] = None) -> None:
        """Log water intake, check daily goal celebration, and reset active countdown."""
        apply_day_rollover(self.config)
        amt = ml if ml is not None else int(self.config.get("amount_per_drink_ml", 250))
        goal = int(self.config.get("daily_goal_ml", 2000))
        consumed = int(self.config.get("consumed_today_ml", 0))

        was_below = consumed < goal
        consumed += amt
        self.config["consumed_today_ml"] = consumed
        save_config(self.config)

        if was_below and consumed >= goal:
            self._send_goal_celebration(consumed, goal)

        if self.state == STATE_ACTIVE:
            self._schedule_next_interval()
        else:
            self._persist_runtime_state()
        self.state_changed.emit()

    def reset_today_intake(self) -> None:
        """Reset today's consumed water counter back to 0 ml."""
        self.config["consumed_today_ml"] = 0
        self.config["last_drink_date"] = str(datetime.date.today())
        save_config(self.config)
        self._persist_runtime_state()
        self.state_changed.emit()

    def apply_config(self, new_config: Dict[str, Any]) -> None:
        """Apply updated settings from the GUI, persist to JSON, and reschedule if active."""
        self.config.update(new_config)
        apply_day_rollover(self.config)
        save_config(self.config)
        if self.state == STATE_ACTIVE:
            self._schedule_next_interval()
        else:
            self._persist_runtime_state()
        self.state_changed.emit()

    def get_remaining_seconds(self) -> int:
        if self.state == STATE_STOPPED or self.target_timestamp <= 0:
            return 0
        return max(0, int(self.target_timestamp - time.time()))

    def _on_tick(self) -> None:
        # Midnight rollover check
        if apply_day_rollover(self.config):
            save_config(self.config)
            if self.state == STATE_SNOOZED and self.snooze_reason == "Rest of Day":
                self.state = STATE_ACTIVE
                self.snooze_reason = ""
                self._schedule_next_interval()
            self.state_changed.emit()
            return

        if self.state == STATE_STOPPED or self.ambush_in_flight:
            return

        now = time.time()
        if self.state == STATE_SNOOZED:
            if now >= self.target_timestamp:
                self.state = STATE_ACTIVE
                self.snooze_reason = ""
                # Fire immediately upon snooze expiration unless in quiet hours
                if is_quiet_hour(self.config):
                    self.target_timestamp = now + 300
                else:
                    self.trigger_ambush()
                self.state_changed.emit()
            elif int(now) % 15 == 0:
                self.state_changed.emit()
            return

        # Active state
        if now >= self.target_timestamp:
            if is_quiet_hour(self.config):
                self.target_timestamp = now + 300
                self._persist_runtime_state()
                self.state_changed.emit()
            else:
                self.trigger_ambush()
        elif int(now) % 15 == 0:
            self._persist_runtime_state()
            self.state_changed.emit()

    def trigger_ambush(self, is_test: bool = False) -> None:
        """Dispatch either a native desktop notification (QThread) or visual PyQt6 popup."""
        if self.ambush_in_flight and not is_test:
            return

        if is_test and self.ambush_in_flight:
            self._cancel_inflight_ambush()

        quote = get_quote(self.config)
        icon_path = resolve_icon_path(self.config.get("icon_file", ""))

        if self.config.get("play_sound", True):
            sound_path = resolve_sound_path(self.config.get("sound_file", ""))
            play_sound(sound_path)

        notif_mode = self.config.get("notification_mode", "native")
        if notif_mode == "popup":
            self.ambush_in_flight = True
            self.popup.show_ambush(
                quote=quote,
                icon_path=icon_path,
                consumed_ml=int(self.config.get("consumed_today_ml", 0)),
                goal_ml=int(self.config.get("daily_goal_ml", 2000)),
                amt_ml=int(self.config.get("amount_per_drink_ml", 250)),
                is_test=is_test,
            )
            return

        # Native notification on non-blocking QThread
        self.ambush_in_flight = True
        title = "YetiAmbush 💧 [TEST]" if is_test else "YetiAmbush 💧"
        interactive = bool(self.config.get("interactive_actions", True))
        thread = NotificationThread(
            title=title,
            body=quote,
            icon_path=icon_path,
            interactive_actions=interactive,
            parent=self,
        )
        thread.action_triggered.connect(lambda act, t=is_test: self._on_native_action(act, t))
        thread.finished.connect(thread.deleteLater)
        self._notify_thread = thread
        thread.start()

    def _on_native_action(self, action: str, is_test: bool) -> None:
        self.ambush_in_flight = False
        self._notify_thread = None

        if action == "fallback_needed":
            self.fallback_tray_message.emit(APP_NAME, get_quote(self.config))
            if not is_test and self.state == STATE_ACTIVE:
                self._schedule_next_interval()
            self.state_changed.emit()
            return

        if action == "drink":
            self.record_drink()
            return
        if action == "snooze5":
            self.snooze(5, "5m")
            return
        if action == "snooze15":
            self.snooze(15, "15m")
            return

        # Dismissed manually
        if not is_test and self.state == STATE_ACTIVE:
            self._schedule_next_interval()
            self.state_changed.emit()

    def _on_popup_drank(self) -> None:
        self.ambush_in_flight = False
        self.record_drink()

    def _on_popup_snooze(self, minutes: int) -> None:
        self.ambush_in_flight = False
        self.snooze(minutes, f"{minutes}m")

    def _on_popup_dismissed(self) -> None:
        self.ambush_in_flight = False
        if self.state == STATE_ACTIVE:
            self._schedule_next_interval()
            self.state_changed.emit()

    def _send_goal_celebration(self, consumed: int, goal: int) -> None:
        icon_path = resolve_icon_path(self.config.get("icon_file", ""))
        yeti_size = int(self.config.get("yeti_size_ml", 1390)) or 1390
        refills = consumed / yeti_size
        msg = (
            f"🎉 DAILY GOAL REACHED! 🎉\n"
            f"You've crushed {consumed}/{goal} ml ({refills:.1f} Yeti Refills) today! Outstanding hydration!"
        )
        send_simple_notification("YetiAmbush 🏆 Goal Achieved!", msg, icon_path=icon_path, urgency="normal")

    def _persist_runtime_state(self) -> None:
        goal = int(self.config.get("daily_goal_ml", 2000))
        consumed = int(self.config.get("consumed_today_ml", 0))
        yeti_size = int(self.config.get("yeti_size_ml", 1390)) or 1390
        rem_mins = max(0, int(self.get_remaining_seconds() / 60))

        save_state(
            {
                "state": self.state,
                "snooze_reason": self.snooze_reason,
                "target_timestamp": self.target_timestamp,
                "minutes_remaining": rem_mins,
                "mode": "Scheduled" if self.config.get("mode") == 1 else "Random Ambush",
                "notification_mode": self.config.get("notification_mode", "native"),
                "daily_goal_ml": goal,
                "consumed_today_ml": consumed,
                "yeti_size_ml": yeti_size,
                "refills_done": round(consumed / yeti_size, 1),
                "total_refills": round(goal / yeti_size, 1),
                "in_quiet_hours": is_quiet_hour(self.config),
                "last_updated": datetime.datetime.now().isoformat(),
            }
        )

    def shutdown(self) -> None:
        """Stop timers, close popups, and clean up background notification threads on quit."""
        self._tick_timer.stop()
        self._cancel_inflight_ambush()
        self.popup.close()
