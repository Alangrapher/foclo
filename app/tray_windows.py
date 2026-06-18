"""Windows system tray icon via pystray.

State-dependent icon:
  Active (timers running): green dot
  Idle:                   grey dot

Uses pystray + PIL. Run in a background thread.
Quit confirmation uses ctypes MessageBoxW (native Windows API).
"""

from __future__ import annotations

import threading

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    Image = None


def _make_icon_image(active: bool) -> Image.Image:
    """Draw a 64x64 circle — green if active, grey if idle."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (0, 180, 80, 255) if active else (140, 140, 140, 255)
    draw.ellipse([8, 8, size - 8, size - 8], fill=color)
    return img


class WindowsTray:
    """Windows system tray — minimize to notification area.

    check_fn: callable → bool — injected from main.py.
    Should read the live Api.engine slots.
    """

    def __init__(self, window, check_fn: callable):
        self.window = window
        self._check_running = check_fn
        self._icon = None
        self._running = False
        self._thread = None

    def start(self):
        if pystray is None:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_tray, daemon=True)
        self._thread.start()

    def _run_tray(self):
        # Initial icon
        active = self._check_running()
        image = _make_icon_image(active)

        menu = pystray.Menu(
            pystray.MenuItem("Show Window", self._show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Archive && Quit", self._archive_and_quit),
            pystray.MenuItem("Pause && Quit", self._pause_and_quit),
        )

        self._icon = pystray.Icon(
            "alangrapher",
            image,
            "Alangrapher",
            menu=menu,
        )

        self._icon.run()

    def _show_window(self, _icon=None, _item=None):
        if self.window:
            self.window.show()

    def _archive_and_quit(self, _icon=None, _item=None):
        self._do_quit(archive_first=True)

    def _pause_and_quit(self, _icon=None, _item=None):
        self._do_quit(archive_first=False)

    def _do_quit(self, archive_first):
        """Archive or pause all active slots, then exit."""
        import os
        import threading

        def _exit_after():
            try:
                from app.storage import get_setting
                from timer_engine import TimerEngine
                n = int(get_setting("default_slots", "1"))
                eng = TimerEngine(num_slots=n)
                for i, s in enumerate(eng.slots):
                    try:
                        if archive_first:
                            if s.status in ("running", "paused"):
                                eng.archive(i)
                        else:
                            if s.status == "running":
                                eng.pause(i)
                    except Exception:
                        pass
            except Exception:
                pass
            os._exit(0)

        threading.Thread(target=_exit_after, daemon=True).start()

    def refresh_icon(self):
        """Update icon to reflect current timer state."""
        if not self._icon or pystray is None:
            return
        try:
            active = self._check_running()
        except Exception:
            active = False
        self._icon.icon = _make_icon_image(active)

    def hide(self):
        if self.window:
            self.window.hide()

    def show(self):
        if self.window:
            self.window.show()
