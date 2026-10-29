#!/usr/bin/env python3
"""
YetiAmbush ADHD Hydration Daemon for Linux (CachyOS / KDE Plasma)
Native background service designed to eliminate notification habituation.

Features:
- Native Linux `notify-send` delivery with `-u critical` for ADHD persistence (pins alert in KDE Plasma).
- Interactive notification actions (Drank It, 5m, 15m) right inside KDE Plasma.
- Exact sarcastic/unhinged and polite quotes from original repos.
- Randomized ambush interval logic to prevent ADHD habituation / notification blindness.
- Quiet hours scheduling (handles overnight spans crossing midnight).
- Yeti bottle metrics tracking (1.39L, 796ml, or custom) with celebration alerts.
- Automatic midnight rollover detection to reset daily intake across long daemon runtimes.
- Background audio cue via PipeWire (pw-play) with paplay/aplay fallbacks.
- Full systemd user service integration with graceful signal handling (SIGHUP, SIGUSR1, SIGUSR2, SIGTERM).
- CLI commands: --daemon, --status, --drink, --snooze, --test, --reload, --config.
"""

import argparse
import datetime
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Exact message arrays from original repositories
UNHINGED_QUOTES = [
    "HEY DRINK SOME MF WATER!",
    "Your brain is currently functioning on 90% dust. Fix it.",
    "You are basically a complicated houseplant with anxiety. Water yourself.",
    "Hydrate or diedrate. The choice is yours.",
    "Warning: User is approaching raisin status. Please add water.",
    "I know you are hyperfocusing, but your kidneys are staging a protest. Chug.",
    "This is your required dopamine delivery fluid. Drink up.",
    "Stop what you are doing. Drink the Yeti. You know which one.",
    "Error 404: Hydration not found. Please reboot with H2O.",
    "Take a sip right now, or I will close all your browser tabs. Just kidding, but seriously drink.",
    "Your blood is currently the consistency of pancake syrup. Thin it out.",
    "Do it for the dopamine.",
]

POLITE_QUOTES = [
    "It's time for a water break.",
    "Please take a moment to hydrate.",
    "A gentle reminder to drink some water.",
    "Staying hydrated helps you focus.",
    "Refresh yourself with a sip of water.",
]

APP_NAME = "YetiAmbush"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "yetiambush"
CONFIG_FILE = CONFIG_DIR / "config.json"
STATE_FILE = CONFIG_DIR / "state.json"
PID_FILE = CONFIG_DIR / "daemon.pid"

DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": 2,  # 1 = Scheduled Interval, 2 = Random Ambush
    "scheduled_interval": 45,  # minutes
    "random_min": 30,  # minutes
    "random_max": 90,  # minutes
    "quiet_start": "22:00",
    "quiet_end": "08:00",
    "quote_style": "Unhinged",  # "Unhinged", "Polite", "Custom", or "Mixed"
    "custom_quote": "Please drink some water.",
    "daily_goal_ml": 2000,
    "amount_per_drink_ml": 250,
    "yeti_size_ml": 1390,  # 1.39L (1390 ml), 796 ml, or custom
    "consumed_today_ml": 0,
    "last_drink_date": str(datetime.date.today()),
    "play_sound": True,
    "sound_file": "",  # Auto-detected if empty
    "icon_file": "",  # Auto-detected if empty
    "interactive_actions": True,  # Uses notify-send -A for Plasma inline action buttons
}


def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def load_config() -> Dict[str, Any]:
    ensure_config_dir()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure missing keys get default values
            for key, val in DEFAULT_CONFIG.items():
                if key not in data:
                    data[key] = val

            # Reset daily progress if new calendar day
            today_str = str(datetime.date.today())
            if data.get("last_drink_date") != today_str:
                data["consumed_today_ml"] = 0
                data["last_drink_date"] = today_str

            return data
    except Exception as e:
        print(f"[{APP_NAME}] Warning: Error loading config ({e}), using defaults.", file=sys.stderr)
        return DEFAULT_CONFIG.copy()


def save_config(config_data: Dict[str, Any]) -> None:
    ensure_config_dir()
    today_str = str(datetime.date.today())
    if config_data.get("last_drink_date") != today_str:
        config_data["consumed_today_ml"] = 0
        config_data["last_drink_date"] = today_str
    temp_file = CONFIG_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        temp_file.replace(CONFIG_FILE)
    except Exception as e:
        print(f"[{APP_NAME}] Error saving config ({e})", file=sys.stderr)


def save_state(state_data: Dict[str, Any]) -> None:
    ensure_config_dir()
    temp_file = STATE_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=4)
        temp_file.replace(STATE_FILE)
    except Exception:
        pass


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def resolve_icon_path(custom_path: str = "") -> str:
    if custom_path and os.path.exists(custom_path):
        return custom_path

    # Candidate paths
    candidates = [
        CONFIG_DIR / "icon.png",
        Path(__file__).resolve().parent / "icon.png",
        Path.home() / ".local/share/icons/yetiambush.png",
        Path.home() / ".local/share/icons/hicolor/256x256/apps/yetiambush.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # Standard freedesktop icon fallback
    return "water"


def resolve_sound_path(custom_path: str = "") -> Optional[str]:
    if custom_path and os.path.exists(custom_path):
        return custom_path

    candidates = [
        CONFIG_DIR / "drop.wav",
        Path(__file__).resolve().parent / "drop.wav",
        Path("/usr/share/sounds/freedesktop/stereo/message.oga"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def play_alert_sound(sound_path: Optional[str]) -> None:
    if not sound_path or not os.path.exists(sound_path):
        return

    # Try preferred Linux sound players in order
    players = ["pw-play", "paplay", "aplay", "canberra-gtk-play"]
    for player in players:
        player_bin = shutil.which(player)
        if player_bin:
            try:
                cmd = [player_bin, sound_path]
                if player == "canberra-gtk-play":
                    cmd = [player_bin, "-f", sound_path]
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


def is_quiet_hour(config: Dict[str, Any]) -> bool:
    start_str = config.get("quiet_start", "22:00")
    end_str = config.get("quiet_end", "08:00")
    try:
        start_time = datetime.datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.datetime.strptime(end_str, "%H:%M").time()
        now = datetime.datetime.now().time()
        if start_time < end_time:
            return start_time <= now <= end_time
        else:  # Spans across midnight (e.g. 22:00 -> 08:00)
            return now >= start_time or now <= end_time
    except Exception:
        return False


def get_quote(config: Dict[str, Any]) -> str:
    style = config.get("quote_style", "Unhinged")
    if style == "Polite":
        return random.choice(POLITE_QUOTES)
    elif style == "Custom":
        return config.get("custom_quote", "Please drink some water.")
    elif style == "Mixed":
        return random.choice(UNHINGED_QUOTES + POLITE_QUOTES)
    else:  # Default to Unhinged
        return random.choice(UNHINGED_QUOTES)


def get_running_daemon_pid() -> Optional[int]:
    if not PID_FILE.exists():
        return None
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        # Check if process is alive
        os.kill(pid, 0)
        return pid
    except (ValueError, OSError):
        # Stale PID file
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        return None


class HydrationDaemon:
    def __init__(self):
        self.running = True
        self.config = load_config()
        self.target_time = 0.0
        self.force_trigger = False
        self.manual_drink_logged = False
        self.active_notify_proc: Optional[subprocess.Popen] = None

    def setup_signals(self) -> None:
        signal.signal(signal.SIGTERM, self._handle_exit)
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGHUP, self._handle_reload)
        signal.signal(signal.SIGUSR1, self._handle_force_trigger)
        signal.signal(signal.SIGUSR2, self._handle_drink_logged)

    def _handle_exit(self, signum, frame) -> None:
        print(f"[{APP_NAME}] Received exit signal {signum}. Shutting down cleanly...")
        self.running = False
        if self.active_notify_proc and self.active_notify_proc.poll() is None:
            try:
                self.active_notify_proc.terminate()
            except Exception:
                pass

    def _handle_reload(self, signum, frame) -> None:
        print(f"[{APP_NAME}] Received SIGHUP. Reloading configuration...")
        self.config = load_config()
        # Check if an external snooze was requested via state file
        state = load_state()
        req_target = state.get("requested_snooze_target")
        if req_target and req_target > time.time():
            self.target_time = req_target
            state["requested_snooze_target"] = None
            save_state(state)
            print(f"[{APP_NAME}] Applied external snooze until {datetime.datetime.fromtimestamp(self.target_time).strftime('%H:%M:%S')}.")
            self._sync_state()
        else:
            self.reset_timer()

    def _handle_force_trigger(self, signum, frame) -> None:
        print(f"[{APP_NAME}] Received SIGUSR1. Forcing immediate ambush!")
        self.force_trigger = True

    def _handle_drink_logged(self, signum, frame) -> None:
        print(f"[{APP_NAME}] Received SIGUSR2. Early drink logged!")
        self.manual_drink_logged = True

    def _check_day_rollover(self) -> bool:
        """Checks if calendar date has changed past midnight. If so, resets daily consumption."""
        today_str = str(datetime.date.today())
        if self.config.get("last_drink_date") != today_str:
            old_val = self.config.get("consumed_today_ml", 0)
            old_date = self.config.get("last_drink_date", "unknown")
            print(f"[{APP_NAME}] Midnight rollover detected ({old_date} -> {today_str}). Resetting daily intake (was {old_val} ml).")
            self.config["consumed_today_ml"] = 0
            self.config["last_drink_date"] = today_str
            save_config(self.config)
            return True
        return False

    def calculate_next_interval(self) -> int:
        """Returns interval in minutes based on configured mode."""
        mode = self.config.get("mode", 2)
        if mode == 1:
            return int(self.config.get("scheduled_interval", 45))
        else:
            min_val = int(self.config.get("random_min", 30))
            max_val = int(self.config.get("random_max", 90))
            if min_val > max_val:
                min_val, max_val = max_val, min_val
            return random.randint(min_val, max_val)

    def reset_timer(self) -> None:
        minutes = self.calculate_next_interval()
        self.target_time = time.time() + (minutes * 60)
        print(f"[{APP_NAME}] Next ambush scheduled in {minutes} minutes ({datetime.datetime.fromtimestamp(self.target_time).strftime('%H:%M:%S')}).")
        self._sync_state()

    def snooze(self, minutes: int = 5) -> None:
        self.target_time = time.time() + (minutes * 60)
        print(f"[{APP_NAME}] Snoozed for {minutes} minutes until {datetime.datetime.fromtimestamp(self.target_time).strftime('%H:%M:%S')}.")
        self._sync_state()

    def _sync_state(self) -> None:
        self._check_day_rollover()
        goal = int(self.config.get("daily_goal_ml", 2000))
        consumed = int(self.config.get("consumed_today_ml", 0))
        amt = int(self.config.get("amount_per_drink_ml", 250))
        yeti_size = int(self.config.get("yeti_size_ml", 1390)) or 1390
        diff = max(0, int((self.target_time - time.time()) / 60))

        refills_done = round(consumed / yeti_size, 1)
        total_refills = round(goal / yeti_size, 1)

        state = {
            "pid": os.getpid(),
            "target_timestamp": self.target_time,
            "target_time_iso": datetime.datetime.fromtimestamp(self.target_time).isoformat() if self.target_time else None,
            "minutes_remaining": diff,
            "mode": "Scheduled" if self.config.get("mode") == 1 else "Random Ambush",
            "daily_goal_ml": goal,
            "consumed_today_ml": consumed,
            "yeti_size_ml": yeti_size,
            "refills_done": refills_done,
            "total_refills": total_refills,
            "in_quiet_hours": is_quiet_hour(self.config),
            "last_updated": datetime.datetime.now().isoformat(),
        }
        save_state(state)

    def record_drink(self, ml: Optional[int] = None) -> None:
        self.config = load_config()  # Refresh state
        self._check_day_rollover()
        amt = ml if ml is not None else int(self.config.get("amount_per_drink_ml", 250))
        goal = int(self.config.get("daily_goal_ml", 2000))
        consumed = int(self.config.get("consumed_today_ml", 0))
        yeti_size = int(self.config.get("yeti_size_ml", 1390)) or 1390

        was_below = consumed < goal
        consumed += amt
        self.config["consumed_today_ml"] = consumed
        save_config(self.config)

        refills_done = consumed / yeti_size
        total_refills = goal / yeti_size
        print(f"[{APP_NAME}] Logged {amt} ml! Daily total: {consumed}/{goal} ml ({refills_done:.1f}/{total_refills:.1f} Yeti Refills).")

        # Goal celebration alert
        if was_below and consumed >= goal:
            self.send_goal_celebration(consumed, goal)

        self.reset_timer()

    def send_goal_celebration(self, consumed: int, goal: int) -> None:
        icon = resolve_icon_path(self.config.get("icon_file", ""))
        yeti_size = int(self.config.get("yeti_size_ml", 1390)) or 1390
        refills = round(consumed / yeti_size, 1)
        celebration_msg = f"🎉 DAILY GOAL REACHED! 🎉\nYou've crushed {consumed}/{goal} ml ({refills:.1f} Yeti Refills) today! Outstanding hydration!"
        cmd = [
            "notify-send",
            "-u", "normal",
            "-a", APP_NAME,
            "-i", icon,
            "YetiAmbush 🏆 Goal Achieved!",
            celebration_msg,
        ]
        try:
            subprocess.run(cmd, check=False)
        except Exception as e:
            print(f"[{APP_NAME}] Error sending celebration notification: {e}", file=sys.stderr)

    def trigger_ambush(self) -> None:
        quote = get_quote(self.config)
        icon = resolve_icon_path(self.config.get("icon_file", ""))
        sound = resolve_sound_path(self.config.get("sound_file", ""))

        print(f"[{APP_NAME}] AMBUSH TRIGGERED: {quote}")

        # Optional audio cue
        if self.config.get("play_sound", True):
            play_alert_sound(sound)

        # Build notification command
        # Critical urgency (-u critical) tells KDE Plasma to pin the alert until dismissed.
        base_cmd = [
            "notify-send",
            "-u", "critical",
            "-a", APP_NAME,
            "-i", icon,
        ]

        use_actions = self.config.get("interactive_actions", True)

        if use_actions:
            # Shortened action labels for KDE Plasma to prevent ellipsis truncation (...)
            action_cmd = base_cmd + [
                "-A", "drink=Drank It 💧",
                "-A", "snooze5=5m ⏰",
                "-A", "snooze15=15m ⏳",
                "YetiAmbush 💧",
                quote,
            ]
            try:
                # notify-send with -A waits for the user to interact or dismiss
                self.active_notify_proc = subprocess.Popen(
                    action_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                stdout, _ = self.active_notify_proc.communicate(timeout=3600)  # 1 hour safety timeout
                self.active_notify_proc = None

                action = stdout.strip()
                if action == "drink":
                    self.record_drink()
                    return
                elif action == "snooze5":
                    self.snooze(5)
                    return
                elif action == "snooze15":
                    self.snooze(15)
                    return
                else:
                    # User closed the notification or manual dismissal
                    print(f"[{APP_NAME}] Notification dismissed manually without action.")
                    self.reset_timer()
                    return
            except subprocess.TimeoutExpired:
                if self.active_notify_proc:
                    self.active_notify_proc.kill()
                    self.active_notify_proc = None
                print(f"[{APP_NAME}] Ambush notification timed out after 1 hour.")
                self.reset_timer()
                return
            except Exception as e:
                self.active_notify_proc = None
                print(f"[{APP_NAME}] Action buttons fallback: {e}", file=sys.stderr)

        # Fallback to fire-and-forget critical notification
        fallback_cmd = base_cmd + ["YetiAmbush 💧", quote]
        try:
            subprocess.run(fallback_cmd, check=False)
        except Exception as e:
            print(f"[{APP_NAME}] Failed to execute notify-send: {e}", file=sys.stderr)

        self.reset_timer()

    def run(self) -> None:
        self.setup_signals()
        ensure_config_dir()

        # Write PID file
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))

        print(f"[{APP_NAME}] Daemon started (PID {os.getpid()}).")
        self.reset_timer()

        try:
            while self.running:
                now = time.time()

                if self.manual_drink_logged:
                    self.manual_drink_logged = False
                    self.record_drink()

                if self.force_trigger:
                    self.force_trigger = False
                    self.trigger_ambush()
                    continue

                if now >= self.target_time:
                    if is_quiet_hour(self.config):
                        print(f"[{APP_NAME}] Quiet hours active ({self.config.get('quiet_start')} - {self.config.get('quiet_end')}). Postponing 5 mins.")
                        self.snooze(5)
                    else:
                        self.trigger_ambush()

                # Periodic state sync every 15 seconds
                self._sync_state()

                # Sleep in 1-second ticks for responsive signal handling
                for _ in range(5):
                    if not self.running or self.force_trigger or self.manual_drink_logged:
                        break
                    time.sleep(1)

        finally:
            print(f"[{APP_NAME}] Cleaning up and stopping daemon...")
            try:
                PID_FILE.unlink(missing_ok=True)
            except OSError:
                pass


# CLI Helper Commands
def cmd_status() -> None:
    pid = get_running_daemon_pid()
    config = load_config()
    today_str = str(datetime.date.today())
    if config.get("last_drink_date") != today_str:
        config["consumed_today_ml"] = 0
        config["last_drink_date"] = today_str
        save_config(config)
    state = load_state()

    print("========================================")
    print("        💧 YetiAmbush Status 💧         ")
    print("========================================")
    if pid:
        print(f" Daemon State   : ACTIVE (PID {pid})")
    else:
        print(" Daemon State   : NOT RUNNING (run 'systemctl --user start yetiambush.service')")

    mode = "Scheduled Interval" if config.get("mode") == 1 else "Random Ambush"
    print(f" Mode           : {mode}")

    if config.get("mode") == 1:
        print(f" Interval       : Every {config.get('scheduled_interval')} minutes")
    else:
        print(f" Interval Range : Between {config.get('random_min')} and {config.get('random_max')} minutes")

    if pid and state.get("target_timestamp"):
        rem = max(0, int((state["target_timestamp"] - time.time()) / 60))
        target_str = datetime.datetime.fromtimestamp(state["target_timestamp"]).strftime("%H:%M:%S")
        print(f" Next Ambush In : ~{rem} minutes ({target_str})")

    goal = config.get("daily_goal_ml", 2000)
    consumed = config.get("consumed_today_ml", 0)
    amt = config.get("amount_per_drink_ml", 250)
    yeti_size = config.get("yeti_size_ml", 1390) or 1390
    refills_done = consumed / yeti_size
    total_refills = goal / yeti_size
    pct = min(100.0, (consumed / goal) * 100) if goal > 0 else 0.0

    print(f" Intake Today   : {consumed} / {goal} ml [{pct:.1f}%] ({refills_done:.1f} / {total_refills:.1f} Yeti Refills)")
    print(f" Yeti Bottle    : {yeti_size} ml (~{total_refills:.1f} refills to reach daily goal)")
    print(f" Quiet Hours    : {config.get('quiet_start')} - {config.get('quiet_end')} (Active: {is_quiet_hour(config)})")
    print(f" Quote Style    : {config.get('quote_style')}")
    print(f" Config File    : {CONFIG_FILE}")
    print("========================================")


def cmd_test() -> None:
    pid = get_running_daemon_pid()
    if pid:
        print(f"Signaling running daemon (PID {pid}) to trigger an ambush...")
        os.kill(pid, signal.SIGUSR1)
    else:
        print("Daemon is not currently running. Sending standalone test ambush...")
        config = load_config()
        quote = get_quote(config)
        icon = resolve_icon_path(config.get("icon_file", ""))
        sound = resolve_sound_path(config.get("sound_file", ""))
        play_alert_sound(sound)
        cmd = [
            "notify-send",
            "-u", "critical",
            "-a", APP_NAME,
            "-i", icon,
            "YetiAmbush 💧 [TEST AMBUSH]",
            quote,
        ]
        subprocess.run(cmd)
        print("Ambush notification dispatched successfully.")


def cmd_drink(amount: Optional[int]) -> None:
    pid = get_running_daemon_pid()
    if pid:
        # If custom amount was specified, update amount_per_drink_ml in config first
        if amount is not None:
            config = load_config()
            config["amount_per_drink_ml"] = amount
            save_config(config)
        print(f"💧 Signaling daemon (PID {pid}) that you drank water...")
        os.kill(pid, signal.SIGUSR2)
    else:
        config = load_config()
        today_str = str(datetime.date.today())
        if config.get("last_drink_date") != today_str:
            config["consumed_today_ml"] = 0
            config["last_drink_date"] = today_str
        amt = amount if amount is not None else int(config.get("amount_per_drink_ml", 250))
        goal = int(config.get("daily_goal_ml", 2000))
        consumed = int(config.get("consumed_today_ml", 0)) + amt
        config["consumed_today_ml"] = consumed
        save_config(config)
        yeti_size = int(config.get("yeti_size_ml", 1390)) or 1390
        refills_done = consumed / yeti_size
        total_refills = goal / yeti_size
        print(f"💧 Logged {amt} ml! Consumed today: {consumed} / {goal} ml ({refills_done:.1f} / {total_refills:.1f} Yeti Refills).")


def cmd_snooze(minutes: int) -> None:
    pid = get_running_daemon_pid()
    if not pid:
        print("YetiAmbush daemon is not running. Start it with 'systemctl --user start yetiambush.service'")
        return

    state = load_state()
    new_target = time.time() + (minutes * 60)
    state["requested_snooze_target"] = new_target
    save_state(state)
    print(f"Signaled daemon: snoozed for {minutes} minutes (until {datetime.datetime.fromtimestamp(new_target).strftime('%H:%M:%S')}).")
    os.kill(pid, signal.SIGHUP)


def cmd_reload() -> None:
    pid = get_running_daemon_pid()
    if pid:
        os.kill(pid, signal.SIGHUP)
        print(f"Sent SIGHUP to YetiAmbush daemon (PID {pid}). Configuration reloaded.")
    else:
        print("Daemon is not running.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="YetiAmbush ADHD Hydration Daemon for Linux / KDE Plasma",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run the hydration daemon loop (used by systemd).",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show live daemon status, countdown timer, and daily hydration progress.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Trigger an immediate critical ambush notification.",
    )
    parser.add_argument(
        "--drink",
        nargs="?",
        const=250,
        type=int,
        metavar="ML",
        help="Log a drink (default 250 ml) and reset interval timer.",
    )
    parser.add_argument(
        "--snooze",
        nargs="?",
        const=60,
        type=int,
        metavar="MINS",
        help="Snooze ambush reminders (default 60 mins for Meeting Mode).",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Reload configuration on the running daemon via SIGHUP.",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Print path to config file and display current JSON settings.",
    )

    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.test:
        cmd_test()
    elif args.drink is not None:
        cmd_drink(args.drink)
    elif args.snooze is not None:
        cmd_snooze(args.snooze)
    elif args.reload:
        cmd_reload()
    elif args.config:
        cfg = load_config()
        print(f"Config path: {CONFIG_FILE}\n")
        print(json.dumps(cfg, indent=4))
    else:
        daemon = HydrationDaemon()
        daemon.run()


if __name__ == "__main__":
    main()
