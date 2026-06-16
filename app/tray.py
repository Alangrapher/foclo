"""System tray — native NSStatusBar with state-dependent SF Symbols.

Active (timers running): clock.badge.checkmark
Idle (no timers):      clock.badge.xmark

Uses PyObjC directly. Quit confirmation uses native NSAlert.
State checked via a callable injected from main.py — reads the live
TimerEngine instance, avoiding DB sync / session-recovery issues.
"""
from __future__ import annotations

import AppKit
from Foundation import NSObject


# ── State helpers ────────────────────────────────────────

def _check_active_standalone() -> bool:
    """True if any timer slot is running or has elapsed time.
    Read-only DB query — does NOT instantiate TimerEngine.
    """
    try:
        from app.storage import get_conn
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM slot_state WHERE status = 'running' LIMIT 1"
            ).fetchone()
            return row is not None
        finally:
            conn.close()
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


def _archive_all() -> list[int]:
    """Archive all active slots. Returns list of indices that failed."""
    failed = []
    try:
        from app.storage import get_setting
        from timer_engine import TimerEngine
        default_slots = int(get_setting("default_slots", "3"))
        engine = TimerEngine(num_slots=default_slots)
        for i, s in enumerate(engine.slots):
            if s.status in ("running", "paused"):
                try:
                    engine.archive(i)
                except Exception:
                    failed.append(i)
    except Exception:
        # If we can't even create the engine, everything failed
        return []
    return failed


# ── Target (menu action receiver) ────────────────────────

class _TrayTarget(NSObject):
    """Receiver for status-bar menu actions and timer refresh."""

    def setWindow_(self, window):
        self._window = window

    def setTray_(self, tray):
        self._tray = tray

    def showWindow_(self, _sender):
        if self._window:
            self._window.show()

    def quitApp_(self, _sender):
        """Show native quit confirmation or exit directly."""
        if not self._window:
            return
        if _check_active_standalone():
            self._showQuitAlert()
        else:
            AppKit.NSApp.terminate_(None)

    def refreshIcon_(self, _timer):
        """Called by NSTimer every 2s — swap icon based on timer state."""
        if self._tray:
            self._tray.refresh_icon()

    def _showQuitAlert(self):
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Quit Alangrapher")
        alert.setInformativeText_("Timers are active. What would you like to do?")
        alert.addButtonWithTitle_("Cancel")
        alert.addButtonWithTitle_("Archive")
        alert.addButtonWithTitle_("Pause")
        alert.setAlertStyle_(AppKit.NSAlertStyleWarning)

        response = alert.runModal()
        if response == AppKit.NSAlertFirstButtonReturn:   # Cancel
            return
        elif response == AppKit.NSAlertSecondButtonReturn:  # Archive
            failed = _archive_all()
            if failed:
                # BUG 8: show an alert if any slots failed to archive
                err_alert = AppKit.NSAlert.alloc().init()
                err_alert.setMessageText_("Archive Warning")
                err_alert.setInformativeText_(
                    f"Failed to archive slot(s): {failed}. Timer data for these slots may be lost."
                )
                err_alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
                err_alert.runModal()
            AppKit.NSApp.terminate_(None)
        elif response == AppKit.NSAlertThirdButtonReturn:   # Pause
            _pause_all()
            AppKit.NSApp.terminate_(None)


# ── TrayIcon ─────────────────────────────────────────────

class TrayIcon:
    """Menu bar status item for Alangrapher.

    Shows clock.badge.checkmark when timers are running,
    clock.badge.xmark when idle.

    check_fn: callable → bool, injected from main.py.
    Should read the live Api.engine, not create a new TimerEngine.
    """

    SF_ACTIVE = "clock.badge.checkmark"
    SF_IDLE   = "clock.badge.xmark"

    def __init__(self, window, check_fn: callable):
        self.window = window
        self._check_running = check_fn
        self._status_item = None
        self._active_image = None
        self._idle_image = None

    def _load_symbol(self, name: str) -> AppKit.NSImage:
        """Load an SF Symbol as a template image, scaled to fill menu bar."""
        image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            name, None
        )
        if image is None:
            raise RuntimeError(f"SF Symbol not found: {name}")
        # Scale up — default is too small in the menu bar
        config = AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_scale_(
            16.0,
            AppKit.NSFontWeightRegular,
            AppKit.NSImageSymbolScaleMedium,
        )
        sized = image.imageWithSymbolConfiguration_(config)
        sized.setTemplate_(True)
        return sized

    def start(self):
        # Pre-load both SF Symbols
        self._active_image = self._load_symbol(self.SF_ACTIVE)
        self._idle_image   = self._load_symbol(self.SF_IDLE)

        # Status bar item
        bar = AppKit.NSStatusBar.systemStatusBar()
        self._status_item = bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)

        # Set initial icon
        self.refresh_icon()

        # Target & menu
        target = _TrayTarget.alloc().init()
        target.setWindow_(self.window)
        target.setTray_(self)
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

        # Periodic refresh — every 2 seconds
        self._timer = AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            2.0, target, "refreshIcon:", None, True
        )

    def refresh_icon(self):
        """Swap icon to match current timer state."""
        if not self._status_item:
            return
        button = self._status_item.button()
        if self._check_running():
            button.setImage_(self._active_image)
        else:
            button.setImage_(self._idle_image)

    def hide(self):
        if self.window:
            self.window.hide()

    def show(self):
        if self.window:
            self.window.show()
