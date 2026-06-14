"""Backup service — periodic SQLite backup with pruning."""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from app.storage import get_setting, DB_PATH


DEFAULT_BACKUP_DIR = os.path.expanduser("~/Documents/Alangrapher/backups")
DEFAULT_INTERVAL_MIN = 60
MAX_BACKUPS = 24


class BackupService:
    """Hourly database backup with configurable location and retention."""

    def __init__(self, interval_minutes: int = DEFAULT_INTERVAL_MIN):
        self._interval = interval_minutes * 60
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    # ── lifecycle ──────────────────────────────────────────

    def start(self):
        self._schedule_next()

    def stop(self):
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None

    # ── schedule ───────────────────────────────────────────

    def _schedule_next(self):
        self._timer = threading.Timer(self._interval, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self):
        try:
            self._do_backup()
        except Exception:
            pass  # silent — backup failure should not crash the app
        finally:
            with self._lock:
                self._schedule_next()

    # ── core backup ────────────────────────────────────────

    def backup_now(self) -> tuple[bool, str]:
        """Manual backup trigger. Returns (ok, path|error)."""
        try:
            path = self._do_backup()
            if path:
                return True, path
            return False, "Auto-backup is disabled"
        except Exception as e:
            return False, str(e)

    def _do_backup(self) -> str | None:
        # Re-read setting every tick so toggles take effect without restart
        if get_setting("auto_backup", "1") != "1":
            return None

        backup_dir = get_setting("backup_location", "") or DEFAULT_BACKUP_DIR
        os.makedirs(backup_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y-%m-%d_%H%M")
        filename = f"alangrapher_{ts}.db"
        dest = os.path.join(backup_dir, filename)

        # Use sqlite3 backup API — safe with WAL mode
        src = sqlite3.connect(str(DB_PATH))
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        self._prune(backup_dir)
        return dest

    # ── file picker ────────────────────────────────────────

    @staticmethod
    def choose_folder(start_dir: str = "") -> str | None:
        """Open native macOS folder picker via PyObjC."""
        try:
            from Foundation import NSURL
            from AppKit import NSOpenPanel
        except ImportError:
            return None

        panel = NSOpenPanel.alloc().init()
        panel.setCanChooseDirectories_(True)
        panel.setCanChooseFiles_(False)
        panel.setCanCreateDirectories_(True)
        panel.setTitle_("Choose Backup Location")
        panel.setMessage_("Select the folder where backups will be saved.")
        panel.setPrompt_("Select")

        if start_dir:
            url = NSURL.fileURLWithPath_(start_dir)
            panel.setDirectoryURL_(url)

        if panel.runModal():
            return str(panel.URL().path())
        return None

    @staticmethod
    def choose_backup_file(start_dir: str = "") -> str | None:
        """Open native macOS file picker for .db backup files."""
        try:
            from Foundation import NSURL
            from AppKit import NSOpenPanel
        except ImportError:
            return None

        panel = NSOpenPanel.alloc().init()
        panel.setCanChooseDirectories_(False)
        panel.setCanChooseFiles_(True)
        panel.setAllowedFileTypes_(["db"])
        panel.setTitle_("Choose Backup to Restore")
        panel.setMessage_("Select an Alangrapher backup file (.db).")
        panel.setPrompt_("Select")

        if start_dir and os.path.isdir(start_dir):
            panel.setDirectoryURL_(NSURL.fileURLWithPath_(start_dir))
        elif start_dir:
            panel.setDirectoryURL_(NSURL.fileURLWithPath_(os.path.dirname(start_dir)))

        if panel.runModal():
            return str(panel.URL().path())
        return None

    @staticmethod
    def restore_backup(backup_path: str) -> tuple[bool, str]:
        """Validate and restore a backup file. Returns (ok, detail)."""
        if not os.path.isfile(backup_path):
            return False, f"File not found: {backup_path}"

        # Validate it looks like an Alangrapher DB
        try:
            conn = sqlite3.connect(backup_path)
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            conn.close()
            required = {"subjects", "records", "todos", "settings", "slot_state"}
            missing = required - tables
            if missing:
                return False, f"Not a valid Alangrapher backup: missing tables {missing}"
        except sqlite3.Error as e:
            return False, f"Invalid database file: {e}"

        # Copy backup over the live DB
        import shutil
        try:
            shutil.copy2(backup_path, str(DB_PATH))
        except OSError as e:
            return False, f"Failed to write database: {e}"

        return True, backup_path

    # ── pruning ────────────────────────────────────────────

    def _prune(self, backup_dir: str):
        """Keep only the most recent MAX_BACKUPS."""
        try:
            files = sorted(
                [f for f in os.listdir(backup_dir) if f.endswith(".db")],
                reverse=True,
            )
            for old in files[MAX_BACKUPS:]:
                os.remove(os.path.join(backup_dir, old))
        except OSError:
            pass
