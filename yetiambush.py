#!/usr/bin/env python3
"""YetiAmbush — Unified PyQt6 Hydration Tray App, Dashboard, and Background Reminder Engine."""

import argparse
import os
import signal
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from config import APP_NAME, resolve_icon_path
from engine import HydrationEngine
from ui import SettingsWindow, YetiTrayController, apply_dark_theme

IPC_SERVER_NAME = f"yetiambush-instance-{os.getuid()}"


def _notify_running_instance(command: str) -> bool:
    """If another YetiAmbush instance is running, send an IPC command and return True."""
    socket = QLocalSocket()
    socket.connectToServer(IPC_SERVER_NAME)
    if not socket.waitForConnected(400):
        return False
    socket.write(command.encode("utf-8"))
    socket.flush()
    socket.waitForBytesWritten(400)
    socket.disconnectFromServer()
    return True


def _start_ipc_server(tray_controller: YetiTrayController, engine: HydrationEngine) -> QLocalServer:
    """Listen for secondary launches so clicking the launcher opens the running Settings window."""
    QLocalServer.removeServer(IPC_SERVER_NAME)
    server = QLocalServer()
    server.listen(IPC_SERVER_NAME)

    def on_new_connection() -> None:
        client = server.nextPendingConnection()
        if not client:
            return
        client.readyRead.connect(lambda: _handle_ipc_message(client, tray_controller, engine))
        client.disconnected.connect(client.deleteLater)

    server.newConnection.connect(on_new_connection)
    return server


def _handle_ipc_message(
    client: QLocalSocket,
    tray_controller: YetiTrayController,
    engine: HydrationEngine,
) -> None:
    cmd = bytes(client.readAll()).decode("utf-8", errors="ignore").strip().upper()
    if cmd == "SHOW":
        tray_controller.show_settings()
    elif cmd == "TEST":
        engine.trigger_ambush(is_test=True)
    elif cmd == "QUIT":
        tray_controller.quit_application()


def main() -> int:
    parser = argparse.ArgumentParser(description="YetiAmbush Hydration Tray & GUI Application")
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Start silently minimized to the system tray (used for autostart).",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show the Settings / Dashboard window immediately on launch.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Trigger a test notification on the running instance.",
    )
    args = parser.parse_args()

    # Single-instance check: focus running window instead of spawning duplicate tray icons
    if args.test and _notify_running_instance("TEST"):
        return 0
    if not args.minimized and _notify_running_instance("SHOW"):
        return 0
    if args.minimized and _notify_running_instance("PING"):
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName("yetiambush")
    # Essential: closing the Settings window must minimize to tray, not kill the daemon
    app.setQuitOnLastWindowClosed(False)
    apply_dark_theme(app)

    engine = HydrationEngine()
    window = SettingsWindow(engine)
    tray_controller = YetiTrayController(app, engine, window)
    ipc_server = _start_ipc_server(tray_controller, engine)

    # Clean exit on POSIX signals (SIGINT / SIGTERM)
    signal.signal(signal.SIGINT, lambda *_: tray_controller.quit_application())
    signal.signal(signal.SIGTERM, lambda *_: tray_controller.quit_application())
    sig_pump = QTimer()
    sig_pump.setInterval(500)
    sig_pump.timeout.connect(lambda: None)
    sig_pump.start()

    engine.start()
    tray_controller.show()

    if args.show or not QSystemTrayIcon.isSystemTrayAvailable():
        window.show()
    else:
        # Minimize to system tray on launch per specification
        window.hide()
        if not args.minimized:
            tray_controller.tray.showMessage(
                "YetiAmbush 💧",
                "Running in your system tray. Left-click the Yeti icon to open Settings.",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    if args.test:
        QTimer.singleShot(300, lambda: engine.trigger_ambush(is_test=True))

    exit_code = app.exec()
    ipc_server.close()
    QLocalServer.removeServer(IPC_SERVER_NAME)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
