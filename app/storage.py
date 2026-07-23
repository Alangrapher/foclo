"""Storage layer — SQLite database connection and settings helpers."""
from __future__ import annotations

import sqlite3
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from app.platform_adapter import app_data_dir

DB_PATH = app_data_dir() / "foclo.db"

_conn_gate = threading.Condition()
_active_connections = 0
_quiescing = False


class _TrackedConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._foclo_closed = False

    def close(self):
        global _active_connections
        try:
            return super().close()
        finally:
            with _conn_gate:
                if not self._foclo_closed:
                    self._foclo_closed = True
                    _active_connections -= 1
                    _conn_gate.notify_all()


def get_conn() -> sqlite3.Connection:
    global _active_connections
    with _conn_gate:
        while _quiescing:
            _conn_gate.wait()
        _active_connections += 1
    try:
        conn = sqlite3.connect(str(DB_PATH), factory=_TrackedConnection)
    except Exception:
        with _conn_gate:
            _active_connections -= 1
            _conn_gate.notify_all()
        raise
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=3000")  # 3s timeout to prevent "database locked"
        return conn
    except Exception:
        conn.close()
        raise


@contextmanager
def quiesce_connections(timeout: float = 5.0):
    """Block new app DB connections and wait for existing get_conn() users."""
    global _quiescing
    deadline = time.monotonic() + timeout
    with _conn_gate:
        _quiescing = True
        while _active_connections > 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _quiescing = False
                _conn_gate.notify_all()
                raise TimeoutError("Timed out waiting for database connections to close")
            _conn_gate.wait(remaining)
    try:
        yield
    finally:
        with _conn_gate:
            _quiescing = False
            _conn_gate.notify_all()


@contextmanager
def db_connection():
    """Context manager that guarantees connection close even on exception."""
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # One-time migration: move legacy DB from project dir to Application Support
    _legacy_path = Path(__file__).resolve().parent.parent / "data" / "foclo.db"
    if not DB_PATH.exists() and _legacy_path.exists():
        import shutil
        # Flush WAL to main DB file before copying — otherwise any
        # committed-but-not-checkpointed data in -wal/-shm is lost.
        try:
            _legacy_conn = sqlite3.connect(str(_legacy_path))
            _legacy_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            _legacy_conn.close()
        except Exception:
            pass  # skip checkpoint failures; copy what we can
        shutil.copy2(str(_legacy_path), str(DB_PATH))

    # v1.0 migration: move DB from old app data dir (Alangrapher → Foclo rename)
    if not DB_PATH.exists():
        import shutil as _shutil
        _old_app_dirs = []
        if sys.platform == "darwin":
            _old_app_dirs.append(Path.home() / "Library" / "Application Support" / "Alangrapher")
        elif sys.platform == "win32":
            _old_app_dirs.append(Path.home() / "AppData" / "Local" / "Alangrapher")
        else:
            _old_app_dirs.append(Path.home() / ".local" / "share" / "Alangrapher")
        # Also check project dir legacy
        _old_app_dirs.append(Path(__file__).resolve().parent.parent / "data")
        for _old_dir in _old_app_dirs:
            _old_db = _old_dir / "alangrapher.db"
            if _old_db.exists():
                DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                # Flush WAL before copy
                try:
                    _old_conn = sqlite3.connect(str(_old_db))
                    _old_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    _old_conn.close()
                except Exception:
                    pass
                _shutil.copy2(str(_old_db), str(DB_PATH))
                # Also copy WAL/SHM if present
                for _suffix in ("-wal", "-shm"):
                    _old_wal = Path(str(_old_db) + _suffix)
                    _new_wal = Path(str(DB_PATH) + _suffix)
                    if _old_wal.exists():
                        _shutil.copy2(str(_old_wal), str(_new_wal))
                break

    with db_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS subjects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                color       TEXT NOT NULL DEFAULT '#5E6AD2',
                archived    INTEGER NOT NULL DEFAULT 0,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS records (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id  INTEGER REFERENCES subjects(id),
                description TEXT DEFAULT '',
                start_time  TEXT NOT NULL,
                end_time    TEXT,
                duration_s  INTEGER NOT NULL DEFAULT 0,
                slot_index  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS todos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subject     TEXT DEFAULT '',
                subject_id  INTEGER REFERENCES subjects(id),
                description TEXT DEFAULT '',
                status      TEXT NOT NULL DEFAULT 'pending',
                sort_order  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS slot_state (
                slot_index  INTEGER PRIMARY KEY,
                status      TEXT NOT NULL DEFAULT 'idle',
                subject_id  INTEGER REFERENCES subjects(id),
                description TEXT DEFAULT '',
                elapsed_s   REAL NOT NULL DEFAULT 0,
                started_at  REAL
            );

            INSERT OR IGNORE INTO settings (key, value) VALUES
                ('default_slots', '3'),
                ('week_starts_on', 'Monday'),
                ('compact_by_default', '0'),
                ('auto_backup', '1'),
                ('backup_location', ''),
                ('minimize_to_tray', '1');

            INSERT OR IGNORE INTO subjects (id, name, color) VALUES
                (1, 'Code Review', '#5E6AD2'),
                (2, 'Writing', '#34C98B'),
                (3, 'Design', '#F0B73F');

            INSERT OR IGNORE INTO slot_state (slot_index) VALUES (0), (1), (2);
        """)
        # Migration: add started_at_real column for crash-safe archive accuracy
        try:
            conn.execute("ALTER TABLE slot_state ADD COLUMN started_at_real TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
        try:
            conn.execute("ALTER TABLE todos ADD COLUMN subject_id INTEGER REFERENCES subjects(id)")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
        conn.commit()


def get_setting(key: str, default: str = "") -> str:
    with db_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def update_setting(key: str, value: str):
    with db_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
