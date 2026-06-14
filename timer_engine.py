"""Timer engine — per DECISIONS.md state machine.

Multi-slot, mutually exclusive running. time.time() delta-based timing.
No threads. State persisted to slot_state table for crash recovery.
"""
from __future__ import annotations

import time
from app.storage import get_conn


class TimerSlot:
    def __init__(self, index: int):
        self.index = index
        self.status = "idle"  # idle | running | paused
        self.subject_id: int | None = None
        self.description = ""
        self.elapsed_s = 0.0
        self.started_at: float | None = None

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
        slot = self.slots[index]
        slot.status = "running"
        slot.subject_id = subject_id
        slot.started_at = time.time()
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
        """Archive current slot. Returns record ID."""
        slot = self.slots[index]
        from datetime import datetime
        total_s = slot.get_total_s()
        start = datetime.now().isoformat()
        end = datetime.now().isoformat()  # Simplified — real app would track actual start

        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO records (subject_id, description, start_time, end_time, duration_s, slot_index) VALUES (?, ?, ?, ?, ?, ?)",
            (slot.subject_id, slot.description, start, end, int(total_s), index),
        )
        record_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Reset slot
        slot.status = "idle"
        slot.subject_id = None
        slot.description = ""
        slot.elapsed_s = 0.0
        slot.started_at = None
        self._save_slot(slot)
        return record_id

    def set_description(self, index: int, description: str):
        self.slots[index].description = description
        self._save_slot(self.slots[index])

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
        # Reindex
        for i, s in enumerate(self.slots):
            s.index = i
        self._sync_slot_state_table()
        return True

    def _load_state(self):
        conn = get_conn()
        rows = conn.execute("SELECT * FROM slot_state ORDER BY slot_index").fetchall()
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
                # Crash recovery: if was running, pause it (safe)
                if s.status == "running":
                    if s.started_at:
                        s.elapsed_s += time.time() - s.started_at
                    s.started_at = None
                    s.status = "paused"

    def _save_slot(self, slot: TimerSlot):
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO slot_state (slot_index, status, subject_id, description, elapsed_s, started_at) VALUES (?, ?, ?, ?, ?, ?)",
            (slot.index, slot.status, slot.subject_id, slot.description, slot.elapsed_s, slot.started_at),
        )
        conn.commit()
        conn.close()

    def _sync_slot_state_table(self):
        conn = get_conn()
        conn.execute("DELETE FROM slot_state")
        for s in self.slots:
            conn.execute(
                "INSERT INTO slot_state (slot_index, status, subject_id, description, elapsed_s, started_at) VALUES (?, ?, ?, ?, ?, ?)",
                (s.index, s.status, s.subject_id, s.description, s.elapsed_s, s.started_at),
            )
        conn.commit()
        conn.close()
