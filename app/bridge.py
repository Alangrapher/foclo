"""Bridge — pywebview JS bridge API. Composes all service modules."""
from __future__ import annotations

import os

from timer_engine import TimerEngine
from app.storage import get_setting
from app.subject_service import get_subjects, add_subject, update_subject, delete_subject
from app.record_service import get_records, add_record, update_record, delete_record
from app.todo_service import get_todos, add_todo, toggle_todo, delete_todo
from app.settings_service import get_settings, update_setting
from app.backup_service import BackupService


class Api:
    """Exposed to JavaScript via window.pywebview.api."""

    def __init__(self, window=None, backup_service: BackupService | None = None):
        self.window = window
        self._backup = backup_service
        default_slots = int(get_setting("default_slots", "3"))
        self.engine = TimerEngine(num_slots=default_slots)

    # ── Window ──────────────────────────────────────────

    def set_window(self, window):
        self.window = window

    def set_tray(self, tray):
        self._tray = tray

    def _refresh_tray(self):
        if hasattr(self, "_tray") and self._tray:
            self._tray.refresh_icon()

    def resize_window(self, width: int, height: int):
        if not self.window:
            return {"ok": False, "error": "Window is not available"}
        self.window.resize(int(width), int(height))
        return {"ok": True, "width": int(width), "height": int(height)}

    def quit_app(self):
        # Archive all active slots, then stop backup before exiting.
        # Defer process exit to background thread so the JS bridge
        # call can return first — calling Cocoa/AppKit from inside
        # a JS→Py bridge callback risks deadlock.
        try:
            self.archive_all_slots()
        except Exception:
            pass
        if self._backup:
            try:
                self._backup.stop()
            except Exception:
                pass
        import os, threading
        threading.Timer(0.05, lambda: os._exit(0)).start()
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

    def _validate_slot(self, index: int) -> dict | None:
        if 0 <= index < len(self.engine.slots):
            return None
        return {"ok": False, "error": f"Invalid slot index: {index}"}

    def start_slot(self, index: int, subject_id: int | None = None):
        if err := self._validate_slot(index):
            return err
        self.engine.start(index, subject_id)
        self._refresh_tray()
        return {"ok": True, "slot": self.engine.get_slot(index).to_dict()}

    def pause_slot(self, index: int):
        if err := self._validate_slot(index):
            return err
        self.engine.pause(index)
        self._refresh_tray()
        return {"ok": True, "slot": self.engine.get_slot(index).to_dict()}

    def archive_slot(self, index: int, subject_id: int | None = None, description: str = ""):
        if err := self._validate_slot(index):
            return err
        if subject_id is not None:
            self.engine.slots[index].subject_id = subject_id
        if description:
            self.engine.set_description(index, description)
        record_id = self.engine.archive(index)
        self._refresh_tray()
        return {"ok": True, "record_id": record_id}

    def clear_slot(self, index: int):
        if err := self._validate_slot(index):
            return err
        self.engine.clear(index)
        self._refresh_tray()
        return {"ok": True, "slot": self.engine.get_slot(index).to_dict()}

    def get_slot_state(self, index: int):
        if err := self._validate_slot(index):
            return err
        return self.engine.get_slot(index).to_dict()

    def get_all_slots(self):
        return [s.to_dict() for s in self.engine.slots]

    def get_display_time(self, index: int):
        if err := self._validate_slot(index):
            return "00:00:00"
        return self.engine.get_display_time(index)

    def add_slot(self):
        ok = self.engine.add_slot()
        return {"ok": ok, "count": self.engine.get_slot_count()}

    def remove_slot(self, index: int):
        if err := self._validate_slot(index):
            return err
        ok = self.engine.remove_slot(index)
        return {"ok": ok, "count": self.engine.get_slot_count()}

    def set_description(self, index: int, description: str):
        if err := self._validate_slot(index):
            return err
        self.engine.set_description(index, description)
        return {"ok": True}

    def set_resume_record(self, index: int, record_id: int):
        """Mark a slot as resuming from an existing record.
        When archived, time accumulates onto the original record."""
        if err := self._validate_slot(index):
            return err
        self.engine.set_resume_record(index, record_id)
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

    def get_records(self, filter: str = "today", week_start: str = "mon"):
        return get_records(filter, week_start)

    def add_record(self, subject_id: int, description: str, start_time: str, end_time: str):
        return add_record(subject_id, description, start_time, end_time)

    def update_record(self, record_id: int, data: dict = None, **kwargs):
        if data is not None:
            kwargs = data
        return update_record(record_id, **kwargs)

    def delete_record(self, record_id: int):
        return delete_record(record_id)

    # ── Todos ──────────────────────────────────────────

    def get_todos(self):
        return get_todos()

    def add_todo(self, subject: str, description: str, subject_id: int | None = None):
        return add_todo(subject, description, subject_id)

    def toggle_todo(self, todo_id: int):
        return toggle_todo(todo_id)

    def delete_todo(self, todo_id: int):
        return delete_todo(todo_id)

    # ── Settings ───────────────────────────────────────

    def get_settings(self):
        return get_settings()

    def update_setting(self, key: str, value: str):
        return update_setting(key, value)

    # ── Export ──────────────────────────────────────────

    def export_timesheet(self, start: str = "", end: str = "", format: str = "xlsx", folder: str = ""):
        try:
            from datetime import date
            from app.export_service import export_xlsx, export_markdown, export_json

            today = date.today().isoformat()
            s_str = start or today
            e_str = end or today
            sd = date.fromisoformat(s_str) if s_str else None
            ed = date.fromisoformat(e_str) if e_str else None

            ext_map = {"xlsx": ".xlsx", "md": ".md", "json": ".json"}
            ext = ext_map.get(format, ".xlsx")

            if folder and os.path.isdir(folder):
                path = os.path.join(folder, f"alangrapher_export_{s_str}_{e_str}{ext}")
            else:
                import tempfile
                path = f"{tempfile.gettempdir()}/alangrapher_export_{s_str}_{e_str}{ext}"

            if format == "md":
                result = export_markdown(path, start_date=sd, end_date=ed)
            elif format == "json":
                result = export_json(path, start_date=sd, end_date=ed)
            else:
                result = export_xlsx(path, start_date=sd, end_date=ed)
                if result is None:
                    return {"ok": False, "error": "openpyxl is not installed — install with: pip install openpyxl"}
            return {"ok": True, "path": result}
        except ValueError as e:
            return {"ok": False, "error": str(e)}

    def choose_export_folder(self, start_dir: str = ""):
        """Open native folder picker for export destination. macOS: PyObjC. Fallback: tkinter."""
        from app.backup_service import BackupService
        path = BackupService.choose_folder(start_dir or os.path.expanduser("~/Desktop"))
        return {"ok": True, "path": path} if path else {"ok": False, "path": None}

    # ── Backup ──────────────────────────────────────────

    def trigger_backup(self):
        """Run a manual backup now."""
        if not self._backup:
            return {"ok": False, "error": "Backup service not available"}
        ok, detail = self._backup.backup_now()
        return {"ok": ok, "path": detail} if ok else {"ok": False, "error": detail}

    def get_backup_status(self):
        """Return backup health stats."""
        if not self._backup:
            return {"ok": False, "error": "Backup service not available"}
        status = self._backup.get_status()
        return {"ok": True, **status}

    def choose_backup_folder(self, start_dir: str = ""):
        """Open native folder picker for backup location."""
        folder = BackupService.choose_folder(start_dir)
        if folder:
            update_setting("backup_location", folder)
            return {"ok": True, "path": folder}
        return {"ok": False, "error": "Cancelled"}

    def choose_backup_file(self, start_dir: str = ""):
        """Open native file picker for .db backup files."""
        path = BackupService.choose_backup_file(start_dir)
        if path:
            return {"ok": True, "path": path}
        return {"ok": False, "error": "Cancelled"}

    def restore_backup(self, backup_path: str):
        """Restore from backup file, then quit the app."""
        ok, detail = self._backup.restore_backup(backup_path, self.engine)
        if ok and self.window:
            self.window.destroy()
        return {"ok": ok, "path": detail} if ok else {"ok": False, "error": detail}

    def reset_all_data(self):
        """Delete all user data: records, todos, subjects, settings, slot_state."""
        from app.storage import get_conn
        # Archive/clear active slots so in-memory state doesn't leak
        # into the fresh DB after deletion
        for i, s in enumerate(self.engine.slots):
            if s.status != "idle":
                try:
                    self.engine.archive(i)
                except Exception:
                    self.engine.clear(i)
        conn = get_conn()
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM records")
            conn.execute("DELETE FROM todos")
            conn.execute("DELETE FROM subjects")
            conn.execute("DELETE FROM settings")
            conn.execute("DELETE FROM slot_state")
            conn.commit()
            return {"ok": True}
        except Exception as e:
            conn.execute("ROLLBACK")
            return {"ok": False, "error": str(e)}
        finally:
            conn.close()
