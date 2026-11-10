# YetiAmbush 💧

> **A native PyQt6 Linux System Tray application and dark-themed dashboard built for CachyOS & KDE Plasma, designed to beat ADHD notification blindness.**

[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20CachyOS%20%7C%20Arch-blue.svg)](https://cachyos.org/)
[![Desktop](https://img.shields.io/badge/Desktop-KDE%20Plasma%206-brightgreen.svg)](https://kde.org/plasma-desktop/)
[![Framework](https://img.shields.io/badge/GUI-PyQt6-green.svg)](https://riverbankcomputing.com/software/pyqt/)

---

## 🧠 Why YetiAmbush?

Standard hydration apps fail ADHD brains due to **notification habituation**. When predictable reminders pop up quietly, hyperfocus filters them out immediately.

**YetiAmbush** solves this without needing terminal commands, cron jobs, or background shell scripts:
1. **Persistent System Tray Integration (SNI)**: Launches minimized into your KDE Plasma / FreeDesktop system tray. Left-click or double-click the Yeti icon to toggle the Dashboard; right-click for instant snooze, drink logging, stop/mute, or quit controls.
2. **Unpredictable Random Ambush Mode (or Fixed Interval)**: Configurable via synchronized sliders and spinboxes (5–180 mins), defaulting to randomized intervals to keep your brain from predicting alerts.
3. **Choice of Delivery Modes**:
   * **Native Desktop Notifications**: Uses `notify-send -u critical` (with FreeDesktop D-Bus fallback) on a non-blocking `QThread` so alerts stay pinned in KDE Plasma with inline `[Drank It 💧]`, `[5m ⏰]`, and `[15m ⏳]` action buttons.
   * **Visual Ambush Popup**: Dark-themed, always-on-top PyQt6 popup dialog centered on your screen with live progress bar and quick buttons.
4. **One-Click "Stop Notifications / I've Drunk Enough"**: Immediately halts reminder timers for the rest of the session from either the tray menu or the dashboard—zero UI freezing.
5. **Yeti Bottle Refill Tracking & Midnight Rollover**: Track progress toward your daily goal in ml and **Yeti Refills** (`1.39L`, `796 ml`, or `Custom`), with automatic midnight reset.

---

## ✨ Core Features

* **System Tray Menu**:
  * **Open Settings / Dashboard**
  * **Log Drink** (quick-log your configured drink volume)
  * **Pause / Snooze Notifications**: `30m`, `1h`, or `Rest of Day`
  * **Stop / Mute for Now** (and **Resume Notifications** when halted)
  * **Quit** (cleanly stops timers and background threads)
* **Modern Dark Dashboard UI (`PyQt6`)**:
  * Non-blocking `QTimer` + `QThread` notification architecture.
  * Closing the window (`X`) minimizes smoothly to the system tray instead of killing the app.
  * Mouse-wheel safe (`NoWheel`) sliders, spinboxes, combo boxes, and time pickers so scrolling never alters settings accidentally.
  * Custom audio cue picker (defaults to `drop.wav` via PipeWire `pw-play`, with `paplay`/`aplay`/`QSoundEffect` fallbacks) and mute toggle.
  * **Start with System** checkbox managing `~/.config/autostart/yetiambush.desktop`.
  * Persists all configuration atomically in `~/.config/yetiambush/config.json`.

---

## 📦 Project Structure

| File | Purpose |
|---|---|
| `yetiambush.py` | Unified single-instance application entry point (Tray + GUI + IPC). |
| `config.py` | JSON config persistence, midnight rollover, quote arrays, and autostart `.desktop` management. |
| `engine.py` | Non-blocking `QTimer` scheduler, pause/snooze/stop state machine, and intake tracking. |
| `notifier.py` | Asynchronous `QThread` `notify-send` / D-Bus worker, audio cue playback, and visual popup window. |
| `ui.py` | Modern dark-themed `SettingsWindow` and `YetiTrayController` (SNI). |
| `yetiambush.desktop` | FreeDesktop application launcher entry. |
| `requirements.txt` | Python dependencies (`PyQt6>=6.5.0`). |
| `drop.wav` / `icon.png` | Water drop sound effect and transparent 256×256 Yeti icon. |

---

## 🚀 Installation & Setup

### 1. Dependencies (CachyOS / Arch Linux)

```bash
# Notification & PipeWire audio tools
sudo pacman -S libnotify pipewire-audio

# Python dependencies
pip install --user -r requirements.txt
# Or via Arch package manager:
# sudo pacman -S python-pyqt6
```

### 2. Install Launcher & Assets

```bash
git clone https://github.com/beanzcraftz/YetiAmbush.git
cd YetiAmbush

chmod +x yetiambush.py
mkdir -p ~/.local/bin ~/.config/yetiambush ~/.local/share/applications ~/.local/share/icons/hicolor/256x256/apps

ln -sf "$(pwd)/yetiambush.py" ~/.local/bin/yetiambush
cp drop.wav icon.png ~/.config/yetiambush/
cp icon.png ~/.local/share/icons/yetiambush.png
cp icon.png ~/.local/share/icons/hicolor/256x256/apps/yetiambush.png

cp yetiambush.desktop ~/.local/share/applications/yetiambush.desktop
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
```

### 3. Launch

Open your KDE Application Launcher (or press `Alt + Space` for KRunner), search for **YetiAmbush**, and launch it!

* On first launch, YetiAmbush minimizes directly to your system tray.
* Left-click (or double-click) the Yeti icon to open the **Dashboard & Settings** window, or launch YetiAmbush again from your app menu to raise the window.
* Toggle **"Start with System"** inside Settings to automatically launch minimized at login.
