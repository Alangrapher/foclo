"""Todo service — CRUD operations."""
from __future__ import annotations

from app.storage import get_conn


def get_todos() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, subject, description, status FROM todos WHERE status != 'archived' ORDER BY sort_order"
        ).fetchall()
        return [
            {"id": r["id"], "subject": r["subject"], "description": r["description"], "status": r["status"]}
            for r in rows
        ]
    finally:
        conn.close()


def add_todo(subject: str, description: str) -> dict:
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO todos (subject, description) VALUES (?, ?)", (subject, description)
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
