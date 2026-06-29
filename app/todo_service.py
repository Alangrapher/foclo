"""Todo service — CRUD operations."""
from __future__ import annotations

from app.storage import get_conn


def get_todos() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT t.id, t.subject_id, COALESCE(s.name, t.subject) AS subject, t.description, t.status
            FROM todos t
            LEFT JOIN subjects s ON t.subject_id=s.id
            WHERE t.status != 'archived'
            ORDER BY CASE WHEN t.status='pending' THEN 0 ELSE 1 END, t.id DESC
            """
        ).fetchall()
        return [
            {
                "id": r["id"],
                "subject_id": r["subject_id"],
                "subject": r["subject"],
                "description": r["description"],
                "status": r["status"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def add_todo(subject: str, description: str, subject_id: int | None = None) -> dict:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO todos (subject, subject_id, description) VALUES (?, ?, ?)",
            (subject, subject_id, description),
        )
        conn.commit()
        return {"ok": True, "id": cur.lastrowid}
    finally:
        conn.close()


def toggle_todo(todo_id: int) -> dict:
    conn = get_conn()
    try:
        row = conn.execute("SELECT status FROM todos WHERE id=?", (todo_id,)).fetchone()
        if row:
            new_status = "done" if row["status"] == "pending" else "pending"
            conn.execute("UPDATE todos SET status=? WHERE id=?", (new_status, todo_id))
            conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def delete_todo(todo_id: int) -> dict:
    conn = get_conn()
    try:
        conn.execute("UPDATE todos SET status='archived' WHERE id=?", (todo_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
