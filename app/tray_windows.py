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
            pystray.MenuItem("Quit Alangrapher", self._quit_app),
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

    def _quit_app(self, _icon=None, _item=None):
        """Quit from tray: exit if idle, otherwise show window."""
        if not self.window:
            import os
            os._exit(0)
            return

        # Check if any slots are running or have elapsed time
        try:
            if self._check_running and self._check_running():
                self.window.show()
                return
        except Exception:
            pass
        try:
            from app.storage import get_setting
            from timer_engine import TimerEngine
            n = int(get_setting("default_slots", "1"))
            eng = TimerEngine(num_slots=n)
            if any(s.elapsed_s > 0 for s in eng.slots):
                self.window.show()
                return
        except Exception:
            pass

        # No active timers — exit directly
        import os
        os._exit(0)

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
