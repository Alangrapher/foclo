"""System tray — native NSStatusBar item with template circle icon.

Uses PyObjC directly. Quit confirmation uses native NSAlert
(webview evaluate_js doesn't work when window is hidden).
"""
from __future__ import annotations

import os
import struct
import tempfile
import zlib

import AppKit
from Foundation import NSObject


def _make_icon_png() -> str:
    """Create an 18×18 filled-circle template PNG, return file path."""
    size = 18
    cx = 9.0
    cy = 9.0
    r2 = 5.0 * 5.0
    pixels = bytearray()
    for y in range(size):
        row = b""
        for x in range(size):
            dx = x + 0.5 - cx
            dy = y + 0.5 - cy
            if dx * dx + dy * dy <= r2:
                row += b"\x00\x00\x00\xff"
            else:
                row += b"\x00\x00\x00\x00"
        pixels.extend(row)

    def _chunk(ct: bytes, data: bytes) -> bytes:
        c = ct + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    filtered = b""
    for y in range(size):
        filtered += b"\x00" + bytes(pixels[y * size * 4 : (y + 1) * size * 4])
    idat = _chunk(b"IDAT", zlib.compress(filtered))
    iend = _chunk(b"IEND", b"")

    fd, path = tempfile.mkstemp(suffix=".png", prefix="alangrapher_tray_")
    with os.fdopen(fd, "wb") as f:
        f.write(sig + ihdr + idat + iend)
    return path


def _check_active() -> bool:
    """True if any timer slot is running or has elapsed time."""
    try:
        from app.storage import get_setting
        from timer_engine import TimerEngine
        default_slots = int(get_setting("default_slots", "3"))
        engine = TimerEngine(num_slots=default_slots)
        return any(s.elapsed_s > 0 or s.status == "running" for s in engine.slots)
    except Exception:
        return True  # fail-safe


def _pause_all():
    try:
        from app.storage import get_setting
        from timer_engine import TimerEngine
        default_slots = int(get_setting("default_slots", "3"))
        engine = TimerEngine(num_slots=default_slots)
        for i, s in enumerate(engine.slots):
            if s.status == "running":
                engine.pause(i)
    except Exception:
        pass


def _archive_all():
    try:
        from app.storage import get_setting
        from timer_engine import TimerEngine
        default_slots = int(get_setting("default_slots", "3"))
        engine = TimerEngine(num_slots=default_slots)
        for i, s in enumerate(engine.slots):
            if s.status in ("running", "paused"):
                engine.archive(i)
    except Exception:
        pass


class _TrayTarget(NSObject):
    """Receiver for status-bar menu actions."""

    def setWindow_(self, window):
        self._window = window

    def showWindow_(self, _sender):
        if self._window:
            self._window.show()

    def quitApp_(self, _sender):
        """Show native quit confirmation or exit directly."""
        if not self._window:
            return
        if _check_active():
            self._showQuitAlert()
        else:
            self._window.destroy()

    def _showQuitAlert(self):
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Quit Alangrapher")
        alert.setInformativeText_("Timers are active. What would you like to do?")
        alert.addButtonWithTitle_("Cancel")
        alert.addButtonWithTitle_("Archive")
        alert.addButtonWithTitle_("Pause")
        # Make Pause destructive-looking by setting alert style
        alert.setAlertStyle_(AppKit.NSAlertStyleWarning)

        response = alert.runModal()
        # Button indices: 1000 = first, 1001 = second, 1002 = third
        if response == AppKit.NSAlertFirstButtonReturn:   # Cancel
            return
        elif response == AppKit.NSAlertSecondButtonReturn:  # Archive
            _archive_all()
            self._window.destroy()
        elif response == AppKit.NSAlertThirdButtonReturn:   # Pause
            _pause_all()
            self._window.destroy()


class TrayIcon:
    """Menu bar status item for Alangrapher."""

    def __init__(self, window):
        self.window = window
        self._status_item = None

    def start(self):
        icon_path = _make_icon_png()
        image = AppKit.NSImage.alloc().initWithContentsOfFile_(icon_path)
        image.setTemplate_(True)

        bar = AppKit.NSStatusBar.systemStatusBar()
        self._status_item = bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)
        button = self._status_item.button()
        button.setImage_(image)

        target = _TrayTarget.alloc().init()
        target.setWindow_(self.window)
        self._target = target

        menu = AppKit.NSMenu.alloc().init()
        show_item = menu.addItemWithTitle_action_keyEquivalent_(
            "Show Window", "showWindow:", ""
        )
        show_item.setTarget_(target)
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        quit_item = menu.addItemWithTitle_action_keyEquivalent_(
            "Quit Alangrapher", "quitApp:", "q"
        )
        quit_item.setTarget_(target)
        self._status_item.setMenu_(menu)

    def hide(self):
        if self.window:
            self.window.hide()

    def show(self):
        if self.window:
            self.window.show()
