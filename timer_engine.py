"""Timer engine — per DECISIONS.md state machine.

Multi-slot, mutually exclusive running. time.time() delta-based timing.
No threads. State persisted to slot_state table for crash recovery.
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta
from app.storage import get_conn


class TimerSlot:
    def __init__(self, index: int):
        self.index = index
        self.status = "idle"  # idle | running | paused
        self.subject_id: int | None = None
        self.description = ""
        self.elapsed_s = 0.0
        self.started_at: float | None = None
        # BUG 3: track actual wall-clock start time for accurate record start_time
        self.started_at_real: str | None = None
        # Resume: if slot was filled from an existing record, store its ID
        # so archive() can UPDATE instead of INSERT — prevents duplicates
        self.resume_record_id: int | None = None

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
        if self.status == "running" and self.started_at:
            total += time.time() - self.started_at
        h = int(total // 3600)
        m = int((total % 3600) // 60)
        s = int(total % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def get_total_s(self) -> float:
        total = self.elapsed_s
        if self.status == "running" and self.started_at:
            total += time.time() - self.started_at
        return total


class TimerEngine:
    def __init__(self, num_slots: int = 3):
        self.slots = [TimerSlot(i) for i in range(num_slots)]
        self._load_state()

    def get_slot_count(self) -> int:
        return len(self.slots)

    def get_slot(self, index: int) -> TimerSlot:
        return self.slots[index]

    def get_display_time(self, index: int) -> str:
        return self.slots[index].get_display()

    def start(self, index: int, subject_id: int | None = None):
        # Pause any running slot (mutual exclusion)
        for s in self.slots:
            if s.status == "running":
                self._pause_slot(s)
                self._save_slot(s)
        slot = self.slots[index]
        slot.status = "running"
        slot.subject_id = subject_id
        slot.started_at = time.time()
        # Track real wall-clock start time ONLY on fresh starts (not resume)
        # so archive() gets the correct start_time.
        # On resume, started_at_real from the original start is preserved.
        if not slot.started_at_real:
            slot.started_at_real = datetime.now().isoformat()
        self._save_slot(slot)

    def pause(self, index: int):
        self._pause_slot(self.slots[index])
        self._save_slot(self.slots[index])

    def _pause_slot(self, slot: TimerSlot):
        if slot.status == "running" and slot.started_at:
            slot.elapsed_s += time.time() - slot.started_at
        slot.started_at = None
        slot.status = "paused"

    def archive(self, index: int) -> int:
        """Archive current slot. Returns record ID (0 if slot was idle).
        If slot had resume_record_id set, UPDATEs the existing record
        (accumulating time) instead of INSERTing a new one."""
        slot = self.slots[index]
        if slot.status == "idle":
            return 0
        total_s = slot.get_total_s()

        # BUG 3: use tracked started_at_real for start_time; fall back to now() - elapsed
        if slot.started_at_real:
            start = slot.started_at_real
        else:
            start = (datetime.now() - timedelta(seconds=total_s)).isoformat()
        end = datetime.now().isoformat()

        conn = get_conn()
        try:
            if slot.resume_record_id:
                # Resume mode: UPDATE the original record, accumulate time
                cur = conn.execute(
                    "UPDATE records SET end_time=?, duration_s=duration_s+? WHERE id=?",
                    (end, int(total_s), slot.resume_record_id),
                )
                if cur.rowcount == 0:
                    # Original record was deleted — fall back to INSERT
                    cur = conn.execute(
                        "INSERT INTO records (subject_id, description, start_time, end_time, duration_s, slot_index) VALUES (?, ?, ?, ?, ?, ?)",
                        (slot.subject_id, slot.description, start, end, int(total_s), index),
                    )
                    record_id = cur.lastrowid
                else:
                    record_id = slot.resume_record_id
            else:
                # Normal mode: INSERT new record
                cur = conn.execute(
                    "INSERT INTO records (subject_id, description, start_time, end_time, duration_s, slot_index) VALUES (?, ?, ?, ?, ?, ?)",
                    (slot.subject_id, slot.description, start, end, int(total_s), index),
                )
                record_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
        # Clear AFTER commit — otherwise _save_slot() inside clear()
        # opens a second connection that deadlocks against conn's write lock.
        self.clear(index)
        return record_id

    def clear(self, index: int):
        """Reset a slot without archiving it."""
        slot = self.slots[index]
        slot.status = "idle"
        slot.subject_id = None
        slot.description = ""
        slot.resume_record_id = None
        slot.elapsed_s = 0.0
        slot.started_at = None
        slot.started_at_real = None
        self._save_slot(slot)

    def set_description(self, index: int, description: str):
        self.slots[index].description = description
        self._save_slot(self.slots[index])

    def set_resume_record(self, index: int, record_id: int):
        """Mark this slot as resuming an existing record.
        When archived, the time will accumulate onto the original record."""
        self.slots[index].resume_record_id = record_id

    def add_slot(self) -> bool:
        if len(self.slots) >= 5:
            return False
        new_slot = TimerSlot(len(self.slots))
        self.slots.append(new_slot)
        self._save_slot(new_slot)
        self._sync_slot_state_table()
        return True

    def remove_slot(self, index: int) -> bool:
        if len(self.slots) <= 1:
            return False
        # Archive if running/paused
        slot = self.slots[index]
        if slot.status != "idle":
            self.archive(index)
        self.slots.pop(index)
        # Reindex live slots. Note: historical records' slot_index values
        # become stale after pop — they are best-effort references, not
        # guaranteed to match the current slot layout.
        for i, s in enumerate(self.slots):
            s.index = i
        self._sync_slot_state_table()
        return True

    def _load_state(self):
        conn = get_conn()
        try:
            rows = conn.execute("SELECT * FROM slot_state ORDER BY slot_index").fetchall()
        finally:
            conn.close()
        for row in rows:
            idx = row["slot_index"]
            if idx < len(self.slots):
                s = self.slots[idx]
                s.status = row["status"]
                s.subject_id = row["subject_id"]
                s.description = row["description"] or ""
                s.elapsed_s = row["elapsed_s"]
                s.started_at = row["started_at"]
                s.started_at_real = row["started_at_real"] if row["started_at_real"] else None
                # Crash recovery: if was running, pause it (safe)
                if s.status == "running":
                    if s.started_at:
                        s.elapsed_s += time.time() - s.started_at
                    s.started_at = None
                    s.status = "paused"
                    # BUG 4: persist crash-recovery modifications
                    self._save_slot(s)

    def _save_slot(self, slot: TimerSlot):
        """Persist slot state to DB with retry on transient locks.

        SQLite WAL mode allows only one writer at a time. The backup service
        (daemon thread) may hold a write lock briefly. Retry with exponential
        backoff instead of failing immediately.
        """
        import time as _time
        last_err = None
        for attempt in range(5):
            try:
                conn = get_conn()
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO slot_state (slot_index, status, subject_id, description, elapsed_s, started_at, started_at_real) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (slot.index, slot.status, slot.subject_id, slot.description, slot.elapsed_s, slot.started_at, slot.started_at_real),
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
        """Rewrite slot_state table. Retry on transient locks (backup daemon)."""
        import time as _time
        last_err = None
        for attempt in range(5):
            try:
                conn = get_conn()
                try:
                    conn.execute("DELETE FROM slot_state")
                    for s in self.slots:
                        conn.execute(
                            "INSERT INTO slot_state (slot_index, status, subject_id, description, elapsed_s, started_at, started_at_real) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (s.index, s.status, s.subject_id, s.description, s.elapsed_s, s.started_at, s.started_at_real),
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
