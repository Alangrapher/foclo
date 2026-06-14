"""macOS system tray — menu bar timer display, show/quit actions."""
from __future__ import annotations

try:
    import rumps
except ImportError:
    rumps = None


class Tray:
    def __init__(self, api):
        self.api = api
        self._app = None
        if rumps:
            self._app = rumps.App("Alangrapher", title="")
            self._app.menu = [
                rumps.MenuItem("Show", callback=self._show),
                None,
                rumps.MenuItem("Quit", callback=self._quit),
            ]

    def tick(self):
        if not self._app:
            return
        # Find running slot for title
        for s in self.api.engine.slots:
            if s.status == "running":
                self._app.title = s.get_display()
                return
        self._app.title = ""

    def run(self):
        if self._app:
            self._app.run()

    def _show(self, _):
        pass  # pywebview handles window visibility

    def _quit(self, _):
        import os
        os._exit(0)

    def remove(self):
        pass  # rumps cleans up on exit
