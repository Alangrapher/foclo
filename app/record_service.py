"""Record service — CRUD operations for time records."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.storage import get_conn


def get_records(filter: str = "today") -> list[dict]:
    conn = get_conn()
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
            "date": (r["start_time"] or r["created_at"] or "")[:10],
        }
        for r in rows
    ]


def add_record(subject_id: int, description: str, start_time: str, end_time: str) -> dict:
    def parse_dt(value: str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.fromisoformat(f"{datetime.now().date()}T{value}:00")

    start_dt = parse_dt(start_time)
    end_dt = parse_dt(end_time)
    if end_dt < start_dt:
        end_dt = end_dt + timedelta(days=1)
    duration_s = max(0, int((end_dt - start_dt).total_seconds()))
    
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO records (subject_id, description, start_time, end_time, duration_s) VALUES (?, ?, ?, ?, ?)",
        (subject_id, description, start_dt.isoformat(), end_dt.isoformat(), duration_s),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "id": cur.lastrowid}


def update_record(record_id: int, **kwargs) -> dict:
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


def delete_record(record_id: int) -> dict:
    conn = get_conn()
    conn.execute("DELETE FROM records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
