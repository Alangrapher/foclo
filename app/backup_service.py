"""Backup service — periodic SQLite backup with pruning."""
from __future__ import annotations

import os
import sqlite3
import threading
import traceback
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
        self._stopped = False               # BUG 1: guard against scheduling after stop
        self._consecutive_failures = 0       # BUG 9: track silent backup failures
        self._last_backup_time: str | None = None  # ISO timestamp of last successful backup

    # ── lifecycle ──────────────────────────────────────────

    def start(self):
        with self._lock:                     # BUG 12: hold lock, consistent with _tick
            self._schedule_next()

    def stop(self):
        with self._lock:
            self._stopped = True             # BUG 1
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
            self._consecutive_failures = 0   # BUG 9: reset on success
            self._last_backup_time = datetime.now().isoformat()
        except Exception:
            # BUG 9: at minimum print the exception and track failures
            self._consecutive_failures += 1
            traceback.print_exc()
            print(f"[BackupService] backup failed ({self._consecutive_failures} consecutive failures)")
        finally:
            with self._lock:
                if not self._stopped:        # BUG 1: don't reschedule after stop()
                    self._schedule_next()

    # ── core backup ────────────────────────────────────────

    def get_status(self) -> dict:
        """Return backup health: consecutive failures, last backup time."""
        return {
            "consecutive_failures": self._consecutive_failures,
            "last_backup": self._last_backup_time,
        }

    def backup_now(self) -> tuple[bool, str]:
        """Manual backup trigger. Returns (ok, path|error)."""
        try:
            path = self._do_backup(force=True)  # BUG 7: bypass auto_backup check
            if path:
                return True, path
            return False, "Backup failed — check backup location"
        except Exception as e:
            return False, str(e)

    def _do_backup(self, force: bool = False) -> str | None:
        # Re-read setting every tick so toggles take effect without restart
        # BUG 7: force=True bypasses the check (manual trigger)
        if not force and get_setting("auto_backup", "1") != "1":
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

    def restore_backup(self, backup_path: str, engine=None) -> tuple[bool, str]:
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

        # Stop the backup timer and pause all slots so no writes hit the DB
        self.stop()
        if engine is not None:
            for slot in engine.slots:
                if slot.status in ("running", "paused"):
                    engine.pause(slot.slot_index)

        # Checkpoint WAL and close any live connections before overwriting
        live_conn = sqlite3.connect(str(DB_PATH))
        try:
            live_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            live_conn.close()

        # Copy backup over the live DB
        import shutil
        try:
            shutil.copy2(backup_path, str(DB_PATH))
        except OSError as e:
            return False, f"Failed to write database: {e}"

        # BUG 2: delete stale WAL / SHM files left over after copy
        db_str = str(DB_PATH)
        for suffix in ("-wal", "-shm"):
            stale = db_str + suffix
            if os.path.isfile(stale):
                try:
                    os.remove(stale)
                except OSError:
                    pass

        return True, backup_path

    # ── pruning ────────────────────────────────────────────

    def _prune(self, backup_dir: str):
        """Keep only the most recent MAX_BACKUPS."""
        try:
            # BUG 6: filter to alangrapher_*.db so foreign .db files don't displace real backups
            files = sorted(
                [f for f in os.listdir(backup_dir)
                 if f.startswith("alangrapher_") and f.endswith(".db")],
                reverse=True,
            )
            for old in files[MAX_BACKUPS:]:
                os.remove(os.path.join(backup_dir, old))
        except OSError:
            pass
