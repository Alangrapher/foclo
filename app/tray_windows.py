"""Windows system tray icon via pystray.

State-dependent icon:
  Active (timers running): green dot
  Idle:                   grey dot

Uses pystray + PIL. Run in a background thread.
Quit confirmation uses tkinter.messagebox (bundled with Python on Windows).
"""

from __future__ import annotations

import sys
import threading
import time
from io import BytesIO

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


def _show_quit_dialog(on_archive, on_pause, on_cancel):
    """Blocking native quit confirmation dialog (tkinter)."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        # No tkinter? Just quit.
        on_archive()
        return

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    answer = messagebox.askyesnocancel(
        "Quit Alangrapher",
        "Timers are active.\n\nYes = Archive all & quit\nNo = Pause all & quit\nCancel = stay",
    )
    root.destroy()

    if answer is True:        # Yes
        on_archive()
    elif answer is False:      # No
        on_pause()
    # else: None → Cancel → do nothing


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
        """Show quit confirmation or exit directly."""
        if not self.window:
            self._stop_tray()
            return

        # Check if any slots are active
        active = False
        try:
            active = self._check_running() if callable(self._check_running) else False
        except Exception:
            pass

        # Also check for paused/elapsed time
        from app.storage import get_setting
        from timer_engine import TimerEngine
        try:
            default_slots = int(get_setting("default_slots", "1"))
            engine = TimerEngine(num_slots=default_slots)
            has_elapsed = any(s.elapsed_s > 0 or s.status == "running" for s in engine.slots)
        except Exception:
            has_elapsed = False

        if active or has_elapsed:

            def _archive():
                self._stop_tray()
                from app.storage import update_setting

                def _do():
                    try:
                        from app.storage import get_setting as gs
                        from timer_engine import TimerEngine as TE
                        n = int(gs("default_slots", "1"))
                        eng = TE(num_slots=n)
                        for i, s in enumerate(eng.slots):
                            if s.status in ("running", "paused"):
                                try:
                                    eng.archive(i)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    import os
                    os._exit(0)

                threading.Thread(target=_do, daemon=True).start()

            def _pause():
                self._stop_tray()

                def _do():
                    try:
                        from app.storage import get_setting as gs
                        from timer_engine import TimerEngine as TE
                        n = int(gs("default_slots", "1"))
                        eng = TE(num_slots=n)
                        for i, s in enumerate(eng.slots):
                            if s.status == "running":
                                try:
                                    eng.pause(i)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    import os
                    os._exit(0)

                threading.Thread(target=_do, daemon=True).start()

            _show_quit_dialog(_archive, _pause, lambda: None)
        else:
            self._stop_tray()
            import os
            os._exit(0)

    def _stop_tray(self):
        """Signal the tray thread to stop."""
        self._running = False
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

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
