"""Storage layer — SQLite database connection and settings helpers."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "alangrapher.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


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
        conn.commit()


def get_setting(key: str, default: str = "") -> str:
    with db_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def update_setting(key: str, value: str):
    with db_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
