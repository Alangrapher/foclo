"""Bridge — pywebview JS bridge API. Composes all service modules."""
from __future__ import annotations

from timer_engine import TimerEngine
from app.storage import get_setting
from app.subject_service import get_subjects, add_subject, update_subject, delete_subject
from app.record_service import get_records, add_record, update_record, delete_record
from app.todo_service import get_todos, add_todo, toggle_todo, delete_todo
from app.settings_service import get_settings, update_setting


class Api:
    """Exposed to JavaScript via window.pywebview.api."""

    def __init__(self, window=None):
        self.window = window
        default_slots = int(get_setting("default_slots", "3"))
        self.engine = TimerEngine(num_slots=default_slots)

    # ── Window ──────────────────────────────────────────

    def set_window(self, window):
        self.window = window

    def resize_window(self, width: int, height: int):
        if not self.window:
            return {"ok": False, "error": "Window is not available"}
        self.window.resize(int(width), int(height))
        return {"ok": True, "width": int(width), "height": int(height)}

    def quit_app(self):
        if self.window:
            self.window.destroy()
        return {"ok": True}

    def hide_window(self):
        if self.window:
            self.window.hide()
        return {"ok": True}

    def show_window(self):
        if self.window:
            self.window.show()
        return {"ok": True}

    # ── Slot batch ops ──────────────────────────────────

    def pause_all_slots(self):
        count = 0
        for i, s in enumerate(self.engine.slots):
            if s.status == "running":
                self.engine.pause(i)
                count += 1
        return {"ok": True, "paused": count}

    def archive_all_slots(self):
        count = 0
        for i, s in enumerate(self.engine.slots):
            if s.status in ("running", "paused"):
                self.engine.archive(i)
                count += 1
        return {"ok": True, "archived": count}

    def any_slot_active(self):
        """True if any slot has non-zero elapsed time (running or paused)."""
        for s in self.engine.slots:
            if s.elapsed_s > 0 or s.status == "running":
                return True
        return False

    def tick(self):
        pass

    # ── Timer ──────────────────────────────────────────

    def start_slot(self, index: int, subject_id: int | None = None):
        self.engine.start(index, subject_id)
        return {"ok": True, "slot": self.engine.get_slot(index).to_dict()}

    def pause_slot(self, index: int):
        self.engine.pause(index)
        return {"ok": True, "slot": self.engine.get_slot(index).to_dict()}

    def archive_slot(self, index: int, subject_id: int | None = None, description: str = ""):
        if description:
            self.engine.set_description(index, description)
        record_id = self.engine.archive(index)
        return {"ok": True, "record_id": record_id}

    def get_slot_state(self, index: int):
        return self.engine.get_slot(index).to_dict()

    def get_all_slots(self):
        return [s.to_dict() for s in self.engine.slots]

    def get_display_time(self, index: int):
        return self.engine.get_display_time(index)

    def add_slot(self):
        ok = self.engine.add_slot()
        return {"ok": ok, "count": self.engine.get_slot_count()}

    def remove_slot(self, index: int):
        ok = self.engine.remove_slot(index)
        return {"ok": ok, "count": self.engine.get_slot_count()}

    def set_description(self, index: int, description: str):
        self.engine.set_description(index, description)
        return {"ok": True}

    # ── Subjects ───────────────────────────────────────

    def get_subjects(self):
        return get_subjects()

    def add_subject(self, name: str, color: str = "#5E6AD2"):
        return add_subject(name, color)

    def update_subject(self, subject_id: int, name: str, color: str):
        return update_subject(subject_id, name, color)

    def delete_subject(self, subject_id: int):
        return delete_subject(subject_id)

    # ── Records ────────────────────────────────────────

    def get_records(self, filter: str = "today"):
        return get_records(filter)

    def add_record(self, subject_id: int, description: str, start_time: str, end_time: str):
        return add_record(subject_id, description, start_time, end_time)

    def update_record(self, record_id: int, **kwargs):
        return update_record(record_id, **kwargs)

    def delete_record(self, record_id: int):
        return delete_record(record_id)

    # ── Todos ──────────────────────────────────────────

    def get_todos(self):
        return get_todos()

    def add_todo(self, subject: str, description: str):
        return add_todo(subject, description)

    def toggle_todo(self, todo_id: int):
        return toggle_todo(todo_id)

    def delete_todo(self, todo_id: int):
        return delete_todo(todo_id)

    # ── Settings ───────────────────────────────────────

    def get_settings(self):
        return get_settings()

    def update_setting(self, key: str, value: str):
        return update_setting(key, value)
