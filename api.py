"""JS bridge API — exposed to WebView JavaScript via window.pywebview.api."""
from __future__ import annotations

from database import get_conn, get_setting, update_setting
from timer_engine import TimerEngine


class Api:
    def __init__(self):
        default_slots = int(get_setting("default_slots", "3"))
        self.engine = TimerEngine(num_slots=default_slots)

    def tick(self):
        """Called ~200ms. Returns nothing — JS polls via get_all_slots()."""
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
        conn = get_conn()
        rows = conn.execute(
            "SELECT id, name, color FROM subjects WHERE archived=0 ORDER BY sort_order"
        ).fetchall()
        conn.close()
        return [{"id": r["id"], "name": r["name"], "color": r["color"]} for r in rows]

    def add_subject(self, name: str, color: str = "#5E6AD2"):
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO subjects (name, color) VALUES (?, ?)", (name, color)
        )
        conn.commit()
        conn.close()
        return {"ok": True, "id": cur.lastrowid}

    def update_subject(self, subject_id: int, name: str, color: str):
        conn = get_conn()
        conn.execute(
            "UPDATE subjects SET name=?, color=? WHERE id=?",
            (name, color, subject_id),
        )
        conn.commit()
        conn.close()
        return {"ok": True}

    def delete_subject(self, subject_id: int):
        conn = get_conn()
        conn.execute("UPDATE subjects SET archived=1 WHERE id=?", (subject_id,))
        conn.commit()
        conn.close()
        return {"ok": True}

    # ── Records ────────────────────────────────────────

    def get_records(self, filter: str = "today"):
        conn = get_conn()
        sql = (
            "SELECT r.id, r.subject_id, s.name as subject_name, r.description, "
            "r.start_time, r.end_time, r.duration_s, r.created_at "
            "FROM records r LEFT JOIN subjects s ON r.subject_id=s.id "
        )
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        if filter == "today":
            sql += f"WHERE date(r.created_at) = '{today}' "
        elif filter == "week":
            sql += f"WHERE r.created_at >= datetime('now', '-7 days') "
        sql += "ORDER BY r.created_at DESC"
        rows = conn.execute(sql).fetchall()
        conn.close()

        def fmt_dur(sec: int) -> str:
            h, m = divmod(sec, 3600)
            m, s = divmod(m, 60)
            if h:
                return f"{h}h {m}m"
            return f"{m}m"

        return [
            {
                "id": r["id"],
                "subject_id": r["subject_id"],
                "subject_name": r["subject_name"] or "—",
                "description": r["description"],
                "start": (r["start_time"] or "")[-8:-3] if r["start_time"] else "",
                "end": (r["end_time"] or "")[-8:-3] if r["end_time"] else "",
                "duration": fmt_dur(r["duration_s"]),
                "date": (r["created_at"] or "")[:10],
            }
            for r in rows
        ]

    def add_record(self, subject_id: int, description: str, start_time: str, end_time: str):
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO records (subject_id, description, start_time, end_time) VALUES (?, ?, ?, ?)",
            (subject_id, description, start_time, end_time),
        )
        conn.commit()
        conn.close()
        return {"ok": True, "id": cur.lastrowid}

    def update_record(self, record_id: int, **kwargs):
        allowed = {"subject_id", "description", "start_time", "end_time"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return {"ok": False, "error": "No valid fields"}
        conn = get_conn()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE records SET {set_clause} WHERE id=?", (*updates.values(), record_id))
        conn.commit()
        conn.close()
        return {"ok": True}

    def delete_record(self, record_id: int):
        conn = get_conn()
        conn.execute("DELETE FROM records WHERE id=?", (record_id,))
        conn.commit()
        conn.close()
        return {"ok": True}

    # ── Todos ──────────────────────────────────────────

    def get_todos(self):
        conn = get_conn()
        rows = conn.execute(
            "SELECT id, subject, description, status FROM todos WHERE status != 'archived' ORDER BY sort_order"
        ).fetchall()
        conn.close()
        return [
            {"id": r["id"], "subject": r["subject"], "description": r["description"], "status": r["status"]}
            for r in rows
        ]

    def add_todo(self, subject: str, description: str):
        conn = get_conn()
        cur = conn.execute(
            "INSERT INTO todos (subject, description) VALUES (?, ?)", (subject, description)
        )
        conn.commit()
        conn.close()
        return {"ok": True, "id": cur.lastrowid}

    def toggle_todo(self, todo_id: int):
        conn = get_conn()
        row = conn.execute("SELECT status FROM todos WHERE id=?", (todo_id,)).fetchone()
        if row:
            new_status = "done" if row["status"] == "pending" else "pending"
            conn.execute("UPDATE todos SET status=? WHERE id=?", (new_status, todo_id))
            conn.commit()
        conn.close()
        return {"ok": True}

    def delete_todo(self, todo_id: int):
        conn = get_conn()
        conn.execute("UPDATE todos SET status='archived' WHERE id=?", (todo_id,))
        conn.commit()
        conn.close()
        return {"ok": True}

    # ── Settings ───────────────────────────────────────


    def resize_window(self, width: int, height: int):
        """Called from JS compact mode to resize the native window."""
        import webview
        if webview.windows:
            webview.windows[0].resize(width, height)


    def get_settings(self):
        return {
            "default_slots": get_setting("default_slots", "3"),
            "week_starts_on": get_setting("week_starts_on", "Monday"),
            "compact_by_default": get_setting("compact_by_default", "0"),
            "auto_backup": get_setting("auto_backup", "1"),
            "backup_location": get_setting("backup_location", ""),
            "minimize_to_tray": get_setting("minimize_to_tray", "1"),
        }

    def update_setting(self, key: str, value: str):
        update_setting(key, value)
        return {"ok": True}
