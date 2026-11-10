"""Configuration, quote arrays, asset resolution, and autostart management for YetiAmbush."""

import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

APP_NAME = "YetiAmbush"
REPO_DIR = Path(__file__).resolve().parent
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "yetiambush"
CONFIG_FILE = CONFIG_DIR / "config.json"
STATE_FILE = CONFIG_DIR / "state.json"
AUTOSTART_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "yetiambush.desktop"
APPLICATIONS_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"
DESKTOP_FILE = APPLICATIONS_DIR / "yetiambush.desktop"

# Exact message arrays preserved from original WaterJug / DrinkDrank repositories
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

DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": 2,  # 1 = Scheduled Interval, 2 = Random Ambush
    "scheduled_interval": 45,  # minutes
    "random_min": 30,  # minutes
    "random_max": 90,  # minutes
    "quiet_start": "22:00",
    "quiet_end": "08:00",
    "quote_style": "Unhinged",  # "Unhinged", "Polite", "Mixed", or "Custom"
    "custom_quote": "Please drink some water.",
    "daily_goal_ml": 2000,
    "amount_per_drink_ml": 250,
    "yeti_size_ml": 1390,
    "consumed_today_ml": 0,
    "last_drink_date": str(datetime.date.today()),
    "notification_mode": "native",  # "native" (notify-send / D-Bus) or "popup" (visual PyQt6 window)
    "interactive_actions": True,
    "play_sound": True,
    "sound_file": "",
    "icon_file": "",
}


def ensure_config_dir() -> Path:
    """Create the YetiAmbush config directory if it does not exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def apply_day_rollover(config_data: Dict[str, Any]) -> bool:
    """Reset daily intake if the calendar date has crossed midnight. Returns True if reset."""
    today_str = str(datetime.date.today())
    if config_data.get("last_drink_date") != today_str:
        config_data["consumed_today_ml"] = 0
        config_data["last_drink_date"] = today_str
        return True
    return False


def load_config() -> Dict[str, Any]:
    """Load persisted configuration from JSON, applying defaults and midnight rollover."""
    ensure_config_dir()
    if not CONFIG_FILE.exists():
        data = DEFAULT_CONFIG.copy()
        save_config(data)
        return data

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, val in DEFAULT_CONFIG.items():
            if key not in data:
                data[key] = val
        if apply_day_rollover(data):
            save_config(data)
        return data
    except Exception as exc:
        print(f"[{APP_NAME}] Warning: failed loading config ({exc}); using defaults.", file=sys.stderr)
        return DEFAULT_CONFIG.copy()


def save_config(config_data: Dict[str, Any]) -> bool:
    """Atomically persist configuration to ~/.config/yetiambush/config.json."""
    ensure_config_dir()
    apply_day_rollover(config_data)
    temp_file = CONFIG_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        temp_file.replace(CONFIG_FILE)
        return True
    except Exception as exc:
        print(f"[{APP_NAME}] Error saving config: {exc}", file=sys.stderr)
        return False


def save_state(state_data: Dict[str, Any]) -> None:
    """Atomically write live runtime state for diagnostics."""
    ensure_config_dir()
    temp_file = STATE_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=4)
        temp_file.replace(STATE_FILE)
    except Exception:
        pass


def resolve_icon_path(custom_path: str = "") -> str:
    """Return path to the Yeti icon PNG or a freedesktop icon name fallback."""
    if custom_path and os.path.exists(custom_path):
        return custom_path

    candidates = [
        CONFIG_DIR / "icon.png",
        REPO_DIR / "icon.png",
        Path.home() / ".local/share/icons/yetiambush.png",
        Path.home() / ".local/share/icons/hicolor/256x256/apps/yetiambush.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return "dialog-information"


def resolve_sound_path(custom_path: str = "") -> Optional[str]:
    """Return path to the configured reminder audio file or default drop.wav."""
    if custom_path and os.path.exists(custom_path):
        return custom_path

    candidates = [
        CONFIG_DIR / "drop.wav",
        REPO_DIR / "drop.wav",
        Path("/usr/share/sounds/freedesktop/stereo/message.oga"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def is_quiet_hour(config_data: Dict[str, Any]) -> bool:
    """Return True if current local time falls inside configured quiet hours."""
    start_str = config_data.get("quiet_start", "22:00")
    end_str = config_data.get("quiet_end", "08:00")
    try:
        start_time = datetime.datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.datetime.strptime(end_str, "%H:%M").time()
        now = datetime.datetime.now().time()
        if start_time < end_time:
            return start_time <= now <= end_time
        return now >= start_time or now <= end_time
    except Exception:
        return False


def get_quote(config_data: Dict[str, Any]) -> str:
    """Select a hydration reminder quote according to the configured quote style."""
    import random

    style = config_data.get("quote_style", "Unhinged")
    if style == "Polite":
        return random.choice(POLITE_QUOTES)
    if style == "Custom":
        return config_data.get("custom_quote", "Please drink some water.") or "Please drink some water."
    if style == "Mixed":
        return random.choice(UNHINGED_QUOTES + POLITE_QUOTES)
    return random.choice(UNHINGED_QUOTES)


def get_launcher_command() -> str:
    """Return the best command path for launching YetiAmbush from desktop/autostart files."""
    local_bin = Path.home() / ".local/bin/yetiambush"
    if local_bin.exists():
        return str(local_bin)
    return f"{sys.executable} {REPO_DIR / 'yetiambush.py'}"


def build_desktop_entry(minimized: bool = False) -> str:
    """Build a FreeDesktop .desktop entry string for launcher or autostart."""
    exec_cmd = get_launcher_command()
    if minimized:
        exec_cmd = f"{exec_cmd} --minimized"
    icon = resolve_icon_path()
    extra = "X-KDE-autostart-phase=2\nStartupNotify=false\n" if minimized else "StartupNotify=true\n"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=YetiAmbush\n"
        "GenericName=ADHD Hydration Reminder\n"
        "Comment=ADHD-friendly hydration reminder tray app and Yeti tracker\n"
        f"Exec={exec_cmd}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        f"{extra}"
        "StartupWMClass=YetiAmbush\n"
        "Keywords=water;hydration;reminder;adhd;yeti;ambush;health;\n"
    )


def is_autostart_enabled() -> bool:
    """Check whether ~/.config/autostart/yetiambush.desktop exists."""
    return AUTOSTART_FILE.exists()


def set_autostart_enabled(enabled: bool) -> bool:
    """Create or remove ~/.config/autostart/yetiambush.desktop."""
    try:
        if enabled:
            AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
            AUTOSTART_FILE.write_text(build_desktop_entry(minimized=True), encoding="utf-8")
        else:
            AUTOSTART_FILE.unlink(missing_ok=True)
        return True
    except Exception as exc:
        print(f"[{APP_NAME}] Failed updating autostart entry: {exc}", file=sys.stderr)
        return False
