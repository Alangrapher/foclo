"""Record service — CRUD operations for time records."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.storage import get_conn


def get_records(filter: str = "today") -> list[dict]:
    conn = get_conn()
    try:
        sql = (
            "SELECT r.id, r.subject_id, s.name as subject_name, r.description, "
            "r.start_time, r.end_time, r.duration_s, r.created_at "
            "FROM records r LEFT JOIN subjects s ON r.subject_id=s.id "
        )
        today = datetime.now().strftime("%Y-%m-%d")
        params = []
        if filter == "today":
            sql += "WHERE date(r.start_time) = ? "
            params.append(today)
        elif filter == "week":
            sql += "WHERE r.start_time >= datetime('now', '-7 days') "
        elif filter == "month":
            sql += "WHERE r.start_time >= datetime('now', '-1 month') "
        sql += "ORDER BY r.created_at DESC"
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    def fmt_dur(sec: int) -> str:
        h = sec / 3600
        return f"{h:.1f}h"

    return [
        {
            "id": r["id"],
            "subject_id": r["subject_id"],
            "subject_name": r["subject_name"] or "—",
            "description": r["description"],
            "start": (r["start_time"] or "")[-8:-3] if r["start_time"] else "",
            "end": (r["end_time"] or "")[-8:-3] if r["end_time"] else "",
            "duration": fmt_dur(r["duration_s"]),
            "date": (r["start_time"] or r["created_at"] or "")[:10],
        }
        for r in rows
    ]


def _parse_dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromisoformat(f"{datetime.now().date()}T{value}:00")


def add_record(subject_id: int, description: str, start_time: str, end_time: str) -> dict:
    start_dt = _parse_dt(start_time)
    end_dt = _parse_dt(end_time)
    if end_dt < start_dt:
        end_dt = end_dt + timedelta(days=1)
    duration_s = max(0, int((end_dt - start_dt).total_seconds()))

    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO records (subject_id, description, start_time, end_time, duration_s) VALUES (?, ?, ?, ?, ?)",
            (subject_id, description, start_dt.isoformat(), end_dt.isoformat(), duration_s),
        )
        conn.commit()
        record_id = cur.lastrowid
    finally:
        conn.close()
    return {"ok": True, "id": record_id}


def update_record(record_id: int, **kwargs) -> dict:
    allowed = {"subject_id", "description", "start_time", "end_time"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return {"ok": False, "error": "No valid fields"}

    # BUG 5: if start_time or end_time changes, recompute duration_s
    if "start_time" in updates or "end_time" in updates:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT start_time, end_time FROM records WHERE id=?",
                (record_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return {"ok": False, "error": "Record not found"}

        final_start = updates.get("start_time", row["start_time"])
        final_end = updates.get("end_time", row["end_time"])
        start_dt = _parse_dt(final_start)
        end_dt = _parse_dt(final_end)
        if end_dt < start_dt:
            end_dt = end_dt + timedelta(days=1)
        duration_s = max(0, int((end_dt - start_dt).total_seconds()))
        updates["duration_s"] = duration_s

    conn = get_conn()
    try:
        set_clause = ", ".join(f"{k}=?" for k in updates)
        conn.execute(f"UPDATE records SET {set_clause} WHERE id=?", (*updates.values(), record_id))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}


def delete_record(record_id: int) -> dict:
    conn = get_conn()
    try:
        conn.execute("DELETE FROM records WHERE id=?", (record_id,))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True}
