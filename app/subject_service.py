"""Subject service — CRUD operations for activity subjects."""
from __future__ import annotations

from app.storage import get_conn


def get_subjects() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, name, color FROM subjects WHERE archived=0 ORDER BY sort_order"
        ).fetchall()
        return [{"id": r["id"], "name": r["name"], "color": r["color"]} for r in rows]
    finally:
        conn.close()


def add_subject(name: str, color: str = "#5E6AD2") -> dict:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO subjects (name, color) VALUES (?, ?)", (name, color)
        )
        conn.commit()
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


def update_subject(subject_id: int, name: str, color: str) -> dict:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE subjects SET name=?, color=? WHERE id=?",
            (name, color, subject_id),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def delete_subject(subject_id: int) -> dict:
    conn = get_conn()
    try:
        conn.execute("UPDATE subjects SET archived=1 WHERE id=?", (subject_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
