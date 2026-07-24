"""Timer engine — per DECISIONS.md state machine.

Multi-slot, mutually exclusive running. time.monotonic() delta-based timing
for live ticks; time.time() wall-clock for crash-recovery persistence.
No threads. State persisted to slot_state table for crash recovery.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timedelta
from app.storage import get_conn, get_setting

# Crash recovery: if a RUNNING slot's wall-clock age exceeds this, reset to idle.
_CRASH_RECOVERY_MAX_AGE_S = 24 * 3600


class TimerSlot:
    def __init__(self, index: int):
        self.index = index
        self.status = "idle"  # idle | running | paused
        self.subject_id: int | None = None
        self.description = ""
        self.elapsed_s = 0.0
        # Live tick base: monotonic clock (never restore across process restarts)
        self.started_at: float | None = None
        # Crash recovery: wall-clock start (time.time()), persisted as started_at column
        self.started_at_wall: float | None = None
        # BUG 3: track actual wall-clock start time for accurate record start_time
        self.started_at_real: str | None = None
        # Resume: if slot was filled from an existing record, store its ID
        # so archive() can UPDATE instead of INSERT — prevents duplicates
        self.resume_record_id: int | None = None
        # Seeded original record duration; archive adds only (total_s - base_duration_s)
        self.base_duration_s = 0.0

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "status": self.status,
            "subject_id": self.subject_id,
            "description": self.description,
            "display_time": self.get_display(),
        }

    def get_display(self) -> str:
        total = self.elapsed_s
        if self.status == "running" and self.started_at is not None:
            total += time.monotonic() - self.started_at
        h = int(total // 3600)
        m = int((total % 3600) // 60)
        s = int(total % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def get_total_s(self) -> float:
        total = self.elapsed_s
        if self.status == "running" and self.started_at is not None:
            total += time.monotonic() - self.started_at
        return total


class TimerEngine:
    def __init__(self, num_slots: int = 3):
        self._lock = threading.RLock()
        self.slots = [TimerSlot(i) for i in range(num_slots)]
        self._load_state()

    def get_slot_count(self) -> int:
        return len(self.slots)

    def get_slot(self, index: int) -> TimerSlot:
        return self.slots[index]

    def get_display_time(self, index: int) -> str:
        return self.slots[index].get_display()

    def start(self, index: int, subject_id: int | None = None):
        with self._lock:
            # Pause any running slot (mutual exclusion)
            for s in self.slots:
                if s.status == "running":
                    self._pause_slot(s)
            slot = self.slots[index]
            slot.status = "running"
            # Only update subject when explicitly provided (resume must keep subject)
            if subject_id is not None:
                slot.subject_id = subject_id
            slot.started_at = time.monotonic()
            slot.started_at_wall = time.time()
            # Track real wall-clock start time ONLY on fresh starts (not resume)
            # so archive() gets the correct start_time.
            # On resume, started_at_real from the original start is preserved.
            if not slot.started_at_real:
                slot.started_at_real = datetime.now().isoformat()
            snapshots = [self._slot_snapshot(s) for s in self.slots]
        for snapshot in snapshots:
            self._save_slot_snapshot(snapshot)

    def pause(self, index: int):
        with self._lock:
            self._pause_slot(self.slots[index])
            snapshot = self._slot_snapshot(self.slots[index])
        self._save_slot_snapshot(snapshot)

    def _pause_slot(self, slot: TimerSlot):
        # Only RUNNING → PAUSED is valid; no-op for idle/paused
        if slot.status != "running":
            return
        if slot.started_at is not None:
            slot.elapsed_s += time.monotonic() - slot.started_at
        slot.started_at = None
        slot.started_at_wall = None
        slot.status = "paused"

    def archive(self, index: int) -> int:
        """Archive current slot. Returns record ID (0 if slot was idle / zero duration).
        If slot had resume_record_id set, UPDATEs the existing record
        (accumulating only the new session time) instead of INSERTing a new one."""
        with self._lock:
            slot = self.slots[index]
            if slot.status == "idle":
                return 0
            previous = self._slot_snapshot(slot)
            total_s = slot.get_total_s()

            # Zero / sub-second sessions: clear without writing a record
            if total_s < 1:
                self._clear_slot(slot)
                cleared = self._slot_snapshot(slot)
                skip_write = True
            else:
                skip_write = False
                # BUG 3: use tracked started_at_real for start_time; fall back to now() - elapsed
                if slot.started_at_real:
                    start = slot.started_at_real
                else:
                    start = (datetime.now() - timedelta(seconds=total_s)).isoformat()
                subject_id = slot.subject_id
                description = slot.description
                resume_record_id = slot.resume_record_id
                # Only the session delta is added on resume archive (avoid double-count)
                base_duration_s = slot.base_duration_s
                session_s = max(0.0, total_s - base_duration_s)
                self._clear_slot(slot)
                cleared = self._slot_snapshot(slot)
        if skip_write:
            self._save_slot_snapshot(cleared)
            return 0
        end = datetime.now().isoformat()

        conn = get_conn()
        try:
            if resume_record_id:
                # Resume mode: UPDATE the original record, accumulate session only
                cur = conn.execute(
                    "UPDATE records SET end_time=?, duration_s=duration_s+?, description=? WHERE id=?",
                    (end, int(session_s), description, resume_record_id),
                )
                if cur.rowcount == 0:
                    # Original record was deleted — fall back to INSERT full total
                    cur = conn.execute(
                        "INSERT INTO records (subject_id, description, start_time, end_time, duration_s, slot_index) VALUES (?, ?, ?, ?, ?, ?)",
                        (subject_id, description, start, end, int(total_s), index),
                    )
                    record_id = cur.lastrowid
                else:
                    record_id = resume_record_id
            else:
                # Normal mode: INSERT new record
                cur = conn.execute(
                    "INSERT INTO records (subject_id, description, start_time, end_time, duration_s, slot_index) VALUES (?, ?, ?, ?, ?, ?)",
                    (subject_id, description, start, end, int(total_s), index),
                )
                record_id = cur.lastrowid
            conn.commit()
        except Exception:
            with self._lock:
                self._apply_slot_snapshot(self.slots[index], previous)
            self._save_slot_snapshot(previous)
            raise
        finally:
            conn.close()
        self._save_slot_snapshot(cleared)
        return record_id

    def clear(self, index: int):
        """Reset a slot without archiving it."""
        with self._lock:
            slot = self.slots[index]
            self._clear_slot(slot)
            snapshot = self._slot_snapshot(slot)
        self._save_slot_snapshot(snapshot)

    def _clear_slot(self, slot: TimerSlot):
        slot.status = "idle"
        slot.subject_id = None
        slot.description = ""
        slot.resume_record_id = None
        slot.base_duration_s = 0.0
        slot.elapsed_s = 0.0
        slot.started_at = None
        slot.started_at_wall = None
        slot.started_at_real = None

    def set_description(self, index: int, description: str):
        with self._lock:
            self.slots[index].description = description
            snapshot = self._slot_snapshot(self.slots[index])
        self._save_slot_snapshot(snapshot)

    def set_resume_record(self, index: int, record_id: int):
        """Mark this slot as resuming an existing record.
        When archived, only the new session time is added onto the original record.
        Also loads the record's duration_s into elapsed_s (and base_duration_s)
        so the timer display shows accumulated time from the original record."""
        with self._lock:
            slot = self.slots[index]
            slot.resume_record_id = record_id
            # Load original duration and set as elapsed base (tracked separately)
            conn = get_conn()
            try:
                row = conn.execute(
                    "SELECT duration_s FROM records WHERE id=?", (record_id,)
                ).fetchone()
                if row and row["duration_s"]:
                    base = float(row["duration_s"])
                    slot.elapsed_s = base
                    slot.base_duration_s = base
                else:
                    slot.base_duration_s = 0.0
            finally:
                conn.close()
            snapshot = self._slot_snapshot(slot)
        self._save_slot_snapshot(snapshot)

    def update_slot_metadata(
        self,
        index: int,
        subject_id: int | None = None,
        description: str | None = None,
    ):
        with self._lock:
            if subject_id is not None:
                self.slots[index].subject_id = subject_id
            if description is not None:
                self.slots[index].description = description
            snapshot = self._slot_snapshot(self.slots[index])
        self._save_slot_snapshot(snapshot)

    def add_slot(self) -> bool:
        with self._lock:
            if len(self.slots) >= 5:
                return False
            new_slot = TimerSlot(len(self.slots))
            self.slots.append(new_slot)
            snapshots = [self._slot_snapshot(s) for s in self.slots]
        self._sync_slot_state_snapshots(snapshots)
        return True

    def remove_slot(self, index: int) -> bool:
        with self._lock:
            if len(self.slots) <= 1:
                return False
            should_archive = self.slots[index].status != "idle"
        if should_archive:
            self.archive(index)
        with self._lock:
            self.slots.pop(index)
            # Reindex live slots. Note: historical records' slot_index values
            # become stale after pop — they are best-effort references, not
            # guaranteed to match the current slot layout.
            for i, s in enumerate(self.slots):
                s.index = i
            snapshots = [self._slot_snapshot(s) for s in self.slots]
        self._sync_slot_state_snapshots(snapshots)
        return True

    def _load_state(self):
        conn = get_conn()
        try:
            rows = conn.execute("SELECT * FROM slot_state ORDER BY slot_index").fetchall()
        finally:
            conn.close()
        now_wall = time.time()
        for row in rows:
            idx = row["slot_index"]
            if idx < len(self.slots):
                s = self.slots[idx]
                s.status = row["status"]
                s.subject_id = row["subject_id"]
                s.description = row["description"] or ""
                s.elapsed_s = row["elapsed_s"] or 0.0
                # started_at column holds wall-clock start for crash recovery
                wall = row["started_at"]
                s.started_at_wall = float(wall) if wall is not None else None
                s.started_at = None  # never restore monotonic across restarts
                s.started_at_real = row["started_at_real"] if row["started_at_real"] else None
                # resume_record_id (may be missing on old DBs before migration)
                try:
                    rid = row["resume_record_id"]
                except (KeyError, IndexError):
                    rid = None
                s.resume_record_id = int(rid) if rid is not None else None
                # base_duration_s: prefer persisted; else re-seed from record
                try:
                    base = row["base_duration_s"]
                except (KeyError, IndexError):
                    base = None
                if base is not None:
                    s.base_duration_s = float(base)
                elif s.resume_record_id is not None:
                    s.base_duration_s = self._fetch_record_duration(s.resume_record_id)
                else:
                    s.base_duration_s = 0.0
                # Crash recovery for RUNNING slots
                if s.status == "running":
                    if (
                        s.started_at_wall is not None
                        and 0 <= (now_wall - s.started_at_wall) < _CRASH_RECOVERY_MAX_AGE_S
                    ):
                        s.elapsed_s += now_wall - s.started_at_wall
                        s.started_at_wall = None
                        s.status = "paused"
                        self._save_slot(s)
                    else:
                        # Stale or missing wall clock: reset to idle (no phantom time)
                        self._clear_slot(s)
                        self._save_slot(s)

    def _fetch_record_duration(self, record_id: int) -> float:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT duration_s FROM records WHERE id=?", (record_id,)
            ).fetchone()
            if row and row["duration_s"]:
                return float(row["duration_s"])
            return 0.0
        finally:
            conn.close()

    def reload_state(self):
        with self._lock:
            try:
                count = int(get_setting("default_slots", str(len(self.slots))))
            except (TypeError, ValueError):
                count = len(self.slots)
            self.slots = [TimerSlot(i) for i in range(count)]
            self._load_state()

    def _slot_snapshot(self, slot: TimerSlot) -> tuple:
        return (
            slot.index,
            slot.status,
            slot.subject_id,
            slot.description,
            slot.resume_record_id,
            slot.elapsed_s,
            slot.started_at,       # monotonic (in-memory restore only)
            slot.started_at_wall,  # wall-clock (persisted as started_at)
            slot.started_at_real,
            slot.base_duration_s,
        )

    def _apply_slot_snapshot(self, slot: TimerSlot, snapshot: tuple):
        (
            slot.index,
            slot.status,
            slot.subject_id,
            slot.description,
            slot.resume_record_id,
            slot.elapsed_s,
            slot.started_at,
            slot.started_at_wall,
            slot.started_at_real,
            slot.base_duration_s,
        ) = snapshot

    def _save_slot(self, slot: TimerSlot):
        self._save_slot_snapshot(self._slot_snapshot(slot))

    def _save_slot_snapshot(self, snapshot: tuple):
        """Persist slot state to DB with retry on transient locks.

        SQLite WAL mode allows only one writer at a time. The backup service
        (daemon thread) may hold a write lock briefly. Retry with exponential
        backoff instead of failing immediately.

        started_at column stores wall-clock time.time() for crash recovery,
        never the in-process monotonic clock.
        """
        import time as _time
        last_err = None
        (
            index,
            status,
            subject_id,
            description,
            resume_record_id,
            elapsed_s,
            _started_at_mono,
            started_at_wall,
            started_at_real,
            base_duration_s,
        ) = snapshot
        for attempt in range(5):
            try:
                conn = get_conn()
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO slot_state "
                        "(slot_index, status, subject_id, description, elapsed_s, "
                        "started_at, started_at_real, resume_record_id, base_duration_s) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            index,
                            status,
                            subject_id,
                            description,
                            elapsed_s,
                            started_at_wall,
                            started_at_real,
                            resume_record_id,
                            base_duration_s,
                        ),
                    )
                    conn.commit()
                    return
                finally:
                    conn.close()
            except sqlite3.OperationalError as e:
                last_err = e
                if "locked" not in str(e) or attempt >= 4:
                    raise
                _time.sleep(0.2 * (2 ** attempt))  # 0.2, 0.4, 0.8, 1.6 s
        raise last_err

    def _sync_slot_state_table(self):
        self._sync_slot_state_snapshots([self._slot_snapshot(s) for s in self.slots])

    def _sync_slot_state_snapshots(self, snapshots: list[tuple]):
        """Rewrite slot_state for current slots; delete orphan high-index rows.

        Retry on transient locks (backup daemon).
        """
        import time as _time
        last_err = None
        n = len(snapshots)
        for attempt in range(5):
            try:
                conn = get_conn()
                try:
                    for snapshot in snapshots:
                        (
                            index,
                            status,
                            subject_id,
                            description,
                            resume_record_id,
                            elapsed_s,
                            _started_at_mono,
                            started_at_wall,
                            started_at_real,
                            base_duration_s,
                        ) = snapshot
                        conn.execute(
                            "INSERT OR REPLACE INTO slot_state "
                            "(slot_index, status, subject_id, description, elapsed_s, "
                            "started_at, started_at_real, resume_record_id, base_duration_s) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                index,
                                status,
                                subject_id,
                                description,
                                elapsed_s,
                                started_at_wall,
                                started_at_real,
                                resume_record_id,
                                base_duration_s,
                            ),
                        )
                    # Remove orphan rows left after remove_slot reindexing
                    conn.execute(
                        "DELETE FROM slot_state WHERE slot_index >= ?",
                        (n,),
                    )
                    conn.commit()
                    return
                finally:
                    conn.close()
            except sqlite3.OperationalError as e:
                last_err = e
                if "locked" not in str(e) or attempt >= 4:
                    raise
                _time.sleep(0.2 * (2 ** attempt))
        raise last_err
