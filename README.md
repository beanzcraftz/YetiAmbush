# YetiAmbush 💧

> **A native Linux background hydration daemon and PyQt6 configuration suite tailored for CachyOS and KDE Plasma, architected to eliminate ADHD notification habituation.**

[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20CachyOS%20%7C%20Arch-blue.svg)](https://cachyos.org/)
[![Desktop](https://img.shields.io/badge/Desktop-KDE%20Plasma%206-brightgreen.svg)](https://kde.org/plasma-desktop/)
[![Framework](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🧠 Why YetiAmbush? (The ADHD Hydration Problem)

Standard hydration reminder apps fail individuals with ADHD due to **notification blindness**. When alerts fire at predictable times with gentle, easily dismissable chimes, the hyperfocused brain rapidly filters them out as ambient background noise.

**YetiAmbush** combats this with psychological "ambush" mechanics:
1. **Unpredictable Timing (Random Ambush)**: Rather than firing on a predictable schedule, alerts hit you at randomized intervals within a configurable min/max range (e.g. anywhere between 30 and 90 minutes). Your brain cannot predict or habituate to the pattern.
2. **Aggressive Persistence (`-u critical`)**: Alerts are dispatched with freedesktop critical urgency. In KDE Plasma, critical notifications ignore standard auto-dismiss timeouts and remain pinned to your screen until explicitly acknowledged.
3. **Auditory Cue Dual-Trigger**: Concurrently plays a droplet audio cue (`drop.wav`) directly through PipeWire (`pw-play`) to break hyperfocus tunnels.
4. **Unhinged Psychological Prompts**: A randomized array of sarcastic, funny, and unhinged reminders that demand attention (*"You are basically a complicated houseplant with anxiety. Water yourself."*).

---

## ✨ Core Features

* **Native KDE Plasma 6 & CachyOS Architecture**: 100% native Linux implementation using standard D-Bus notification protocols via `/usr/bin/notify-send`. Zero electron or heavy browser wrappers.
* **Interactive Plasma Action Buttons**: Critical alerts feature inline buttons rendered directly in KDE Plasma's notification widget:
  * `[Drank It 💧]` — Logs intake, evaluates your daily target, and resets the ambush timer.
  * `[5m ⏰]` — Quick 5-minute snooze.
  * `[15m ⏳]` — 15-minute snooze.
* **Yeti Bottle Refill Tracking**: Tracks daily hydration in terms of actual **Yeti Refills** rather than abstract cups or milliliters:
  * Presets for **1.39L (1390 ml)** and **796 ml** tumblers, plus **Custom** volumes.
  * Dynamically calculates how many Yeti refills remain to hit your daily goal (e.g., *1.4 Yeti Refills per day*).
* **Automated Midnight Rollover**: Background daemon continuously evaluates date boundaries. As soon as the clock strikes midnight, your daily intake automatically resets to `0 ml`, preventing yesterday's tally from polluting the next day.
* **Quiet Hours Scheduling**: Define sleep/silence periods (e.g., `22:00` to `08:00`). Handles overnight spans crossing midnight seamlessly.
* **PyQt6 Configuration GUI**: Clean, native KDE Breeze theme settings window equipped with `NoWheel` scroll-safe widgets to prevent mouse-wheel accidents while scrolling.
* **systemd User Daemon**: Runs silently in the background via `systemctl --user`, starting automatically upon login.
* **UNIX Signals & CLI Controls**: Support for `SIGHUP` (hot reload), `SIGUSR1` (test ambush), and `SIGUSR2` (log drink) for KDE shortcut integration.

---

## 📦 File Layout

| Path | Purpose |
|---|---|
| `yetiambush_daemon.py` | Background daemon service handling timers, signals, and notifications. |
| `yetiambush_gui.py` | Native PyQt6 configuration manager and status monitor. |
| `yetiambush.service` | systemd user service unit definition. |
| `yetiambush-config.desktop` | Desktop application entry for KDE Application Launcher / KRunner. |
| `drop.wav` | Water droplet audio cue played via PipeWire. |
| `icon.png` | Transparent 256x256 high-resolution Yeti icon. |

---

## 🚀 Installation & Quick Start

### 1. Prerequisites (Arch Linux / CachyOS)

Ensure the native notification tools, PipeWire utilities, and PyQt6 are installed:

```bash
# Core notification and audio dependencies
sudo pacman -S libnotify pipewire-audio

# Python PyQt6 GUI framework (via pacman or pip)
sudo pacman -S python-pyqt6
# Or via user pip:
# pip install --user PyQt6
```

### 2. Install Executables & Assets

Clone the repository and set up user paths:

```bash
git clone https://github.com/beanzcraftz/YetiAmbush.git
cd YetiAmbush

# Make scripts executable
chmod +x yetiambush_daemon.py yetiambush_gui.py

# Symlink binaries to ~/.local/bin (ensure ~/.local/bin is in your $PATH)
mkdir -p ~/.local/bin
ln -sf $(pwd)/yetiambush_daemon.py ~/.local/bin/yetiambush-daemon
ln -sf $(pwd)/yetiambush_gui.py ~/.local/bin/yetiambush-gui

# Install persistent configuration directory and assets
mkdir -p ~/.config/yetiambush
cp drop.wav ~/.config/yetiambush/
cp icon.png ~/.config/yetiambush/

# Install application icon for KDE Plasma
mkdir -p ~/.local/share/icons/hicolor/256x256/apps
cp icon.png ~/.local/share/icons/yetiambush.png
cp icon.png ~/.local/share/icons/hicolor/256x256/apps/yetiambush.png

# Install KDE desktop launcher
mkdir -p ~/.local/share/applications
cp yetiambush-config.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
```

### 3. Enable Background Service (`systemd`)

Install and start the background daemon as a systemd user unit:

```bash
mkdir -p ~/.config/systemd/user
cp yetiambush.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now yetiambush.service
```

Verify that the service is active and running:

```bash
systemctl --user status yetiambush.service
```

---

## 🎛️ Usage & Management

### Launching the Configuration GUI
Press `Meta` (Super/Windows key) and type **YetiAmbush**, or launch from terminal:
```bash
yetiambush-gui
```

### CLI Commands
The daemon utility also functions as an interactive command-line interface:

```bash
# Check live countdown timer, daemon PID, and Yeti intake metrics
yetiambush-daemon --status

# Fire an immediate test alert to preview quotes and audio
yetiambush-daemon --test

# Log a drink manually (drank early) and reset the timer
yetiambush-daemon --drink        # logs default amount (e.g. 250 ml)
yetiambush-daemon --drink 500    # logs 500 ml

# Snooze alerts (e.g. Meeting Mode for 60 minutes)
yetiambush-daemon --snooze 60

# Hot-reload configuration without restarting the service
yetiambush-daemon --reload

# Inspect configuration JSON
yetiambush-daemon --config
```

---

## ⚡ Optional: KDE Global Keyboard Shortcut

To log a drink instantly whenever you finish your Yeti without opening a window:

1. Open **KDE System Settings** $\rightarrow$ **Keyboard** $\rightarrow$ **Shortcuts** (or **Custom Commands**).
2. Click **Add New** $\rightarrow$ **Command**.
3. Name it **"YetiAmbush: Log Drink"**.
4. Set Command to: `yetiambush-daemon --drink`
5. Assign a shortcut (e.g. `Meta + W` or `Meta + Alt + H`).

Whenever you hydrate early, tap your shortcut—it logs your intake and reschedules the next ambush automatically!

---

## 📜 License

MIT License. Designed and crafted for ADHD hydration mastery.
