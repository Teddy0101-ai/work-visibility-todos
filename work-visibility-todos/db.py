import streamlit as st
import sqlite3
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def _get_db_url() -> Optional[str]:
    return st.secrets.get("database_url", None)

def _connect():
    db_url = _get_db_url()
    if db_url:
        import psycopg2
        return psycopg2.connect(db_url)
    os.makedirs("data", exist_ok=True)
    return sqlite3.connect("data/app.db", check_same_thread=False)

def init_db():
    conn = _connect()
    cur = conn.cursor()
    is_pg = _get_db_url() is not None

    if is_pg:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            owner TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            due_date TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_by TEXT,
            updated_at TEXT NOT NULL
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS task_items (
            id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            is_done BOOLEAN NOT NULL DEFAULT FALSE,
            position INTEGER NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_by TEXT,
            updated_at TEXT NOT NULL
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS task_logs (
            id SERIAL PRIMARY KEY,
            task_id INTEGER NOT NULL,
            actor TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
    else:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            owner TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            due_date TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_by TEXT,
            updated_at TEXT NOT NULL
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS task_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            is_done INTEGER NOT NULL DEFAULT 0,
            position INTEGER NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_by TEXT,
            updated_at TEXT NOT NULL
        );
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS task_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            actor TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)

    conn.commit()
    conn.close()

def get_users() -> List[Dict[str, Any]]:
    cfg = st.secrets.get("auth", {})
    users = cfg.get("users", {})
    return [{"username": u} for u in sorted(users.keys())]

# -----------------------
# Tasks
# -----------------------
def create_task(title, description, tags, owner, priority, status, due_date, created_by) -> int:
    conn = _connect()
    cur = conn.cursor()
    now = _now()
    is_pg = _get_db_url() is not None

    if is_pg:
        cur.execute(
            """
            INSERT INTO tasks (title, description, tags, owner, priority, status, due_date, created_by, created_at, updated_by, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id;
            """,
            (title, description, tags, owner, priority, status, due_date, created_by, now, created_by, now),
        )
        tid = cur.fetchone()[0]
    else:
        cur.execute(
            """
            INSERT INTO tasks (title, description, tags, owner, priority, status, due_date, created_by, created_at, updated_by, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (title, description, tags, owner, priority, status, due_date, created_by, now, created_by, now),
        )
        tid = cur.lastrowid

    conn.commit()
    conn.close()
    return int(tid)

def list_tasks(owners: List[str], statuses: List[str], search: Optional[str]) -> List[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()
    is_pg = _get_db_url() is not None

    clauses, params = [], []

    if owners:
        placeholders = ",".join(["%s" if is_pg else "?" for _ in owners])
        clauses.append(f"owner IN ({placeholders})")
        params.extend(owners)

    if statuses:
        placeholders = ",".join(["%s" if is_pg else "?" for _ in statuses])
        clauses.append(f"status IN ({placeholders})")
        params.extend(statuses)

    if search:
        like = f"%{search}%"
        if is_pg:
            clauses.append("(title ILIKE %s OR description ILIKE %s OR tags ILIKE %s)")
            params.extend([like, like, like])
        else:
            clauses.append("(title LIKE ? OR description LIKE ? OR tags LIKE ?)")
            params.extend([like, like, like])

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    q = f"""
        SELECT id, title, description, tags, owner, priority, status, due_date, created_by, created_at, updated_by, updated_at
        FROM tasks
        {where}
        ORDER BY updated_at DESC;
    """
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()

    cols = ["id","title","description","tags","owner","priority","status","due_date","created_by","created_at","updated_by","updated_at"]
    return [dict(zip(cols, r)) for r in rows]

def update_task_meta(task_id: int, title: str, description: str, tags: str, owner: str, priority: str, status: str, due_date: Optional[str], updated_by: str):
    conn = _connect()
    cur = conn.cursor()
    now = _now()
    is_pg = _get_db_url() is not None

    if is_pg:
        cur.execute(
            """
            UPDATE tasks
            SET title=%s, description=%s, tags=%s, owner=%s, priority=%s, status=%s, due_date=%s, updated_by=%s, updated_at=%s
            WHERE id=%s
            """,
            (title, description, tags, owner, priority, status, due_date, updated_by, now, task_id),
        )
    else:
        cur.execute(
            """
            UPDATE tasks
            SET title=?, description=?, tags=?, owner=?, priority=?, status=?, due_date=?, updated_by=?, updated_at=?
            WHERE id=?
            """,
            (title, description, tags, owner, priority, status, due_date, updated_by, now, task_id),
        )

    conn.commit()
    conn.close()

def delete_task(task_id: int):
    conn = _connect()
    cur = conn.cursor()
    is_pg = _get_db_url() is not None

    if is_pg:
        cur.execute("DELETE FROM task_items WHERE task_id=%s", (task_id,))
        cur.execute("DELETE FROM task_logs WHERE task_id=%s", (task_id,))
        cur.execute("DELETE FROM tasks WHERE id=%s", (task_id,))
    else:
        cur.execute("DELETE FROM task_items WHERE task_id=?", (task_id,))
        cur.execute("DELETE FROM task_logs WHERE task_id=?", (task_id,))
        cur.execute("DELETE FROM tasks WHERE id=?", (task_id,))

    conn.commit()
    conn.close()

# -----------------------
# Items (list under task)
# -----------------------
def _next_position(cur, task_id: int, is_pg: bool) -> int:
    if is_pg:
        cur.execute("SELECT COALESCE(MAX(position), 0) FROM task_items WHERE task_id=%s", (task_id,))
    else:
        cur.execute("SELECT COALESCE(MAX(position), 0) FROM task_items WHERE task_id=?", (task_id,))
    return int(cur.fetchone()[0]) + 1

def add_item(task_id: int, text: str, created_by: str) -> int:
    conn = _connect()
    cur = conn.cursor()
    now = _now()
    is_pg = _get_db_url() is not None

    pos = _next_position(cur, task_id, is_pg)

    if is_pg:
        cur.execute(
            """
            INSERT INTO task_items (task_id, text, is_done, position, created_by, created_at, updated_by, updated_at)
            VALUES (%s,%s,FALSE,%s,%s,%s,%s,%s)
            RETURNING id;
            """,
            (task_id, text, pos, created_by, now, created_by, now),
        )
        iid = cur.fetchone()[0]
    else:
        cur.execute(
            """
            INSERT INTO task_items (task_id, text, is_done, position, created_by, created_at, updated_by, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (task_id, text, 0, pos, created_by, now, created_by, now),
        )
        iid = cur.lastrowid

    conn.commit()
    conn.close()
    return int(iid)

def list_items(task_id: int) -> List[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()
    is_pg = _get_db_url() is not None

    if is_pg:
        cur.execute(
            """
            SELECT id, task_id, text, is_done, position, created_by, created_at, updated_by, updated_at
            FROM task_items
            WHERE task_id=%s
            ORDER BY position ASC, id ASC
            """,
            (task_id,),
        )
    else:
        cur.execute(
            """
            SELECT id, task_id, text, is_done, position, created_by, created_at, updated_by, updated_at
            FROM task_items
            WHERE task_id=?
            ORDER BY position ASC, id ASC
            """,
            (task_id,),
        )
    rows = cur.fetchall()
    conn.close()

    cols = ["id","task_id","text","is_done","position","created_by","created_at","updated_by","updated_at"]
    out = [dict(zip(cols, r)) for r in rows]

    # Normalize is_done for sqlite (0/1) into bool
    for it in out:
        it["is_done"] = bool(it["is_done"])
    return out

def update_item(item_id: int, text: str, updated_by: str):
    conn = _connect()
    cur = conn.cursor()
    now = _now()
    is_pg = _get_db_url() is not None

    if is_pg:
        cur.execute(
            "UPDATE task_items SET text=%s, updated_by=%s, updated_at=%s WHERE id=%s",
            (text, updated_by, now, item_id),
        )
    else:
        cur.execute(
            "UPDATE task_items SET text=?, updated_by=?, updated_at=? WHERE id=?",
            (text, updated_by, now, item_id),
        )
    conn.commit()
    conn.close()

def toggle_item_done(item_id: int, is_done: bool, updated_by: str):
    conn = _connect()
    cur = conn.cursor()
    now = _now()
    is_pg = _get_db_url() is not None

    if is_pg:
        cur.execute(
            "UPDATE task_items SET is_done=%s, updated_by=%s, updated_at=%s WHERE id=%s",
            (is_done, updated_by, now, item_id),
        )
    else:
        cur.execute(
            "UPDATE task_items SET is_done=?, updated_by=?, updated_at=? WHERE id=?",
            (1 if is_done else 0, updated_by, now, item_id),
        )
    conn.commit()
    conn.close()

def delete_item(item_id: int):
    conn = _connect()
    cur = conn.cursor()
    is_pg = _get_db_url() is not None

    if is_pg:
        cur.execute("DELETE FROM task_items WHERE id=%s", (item_id,))
    else:
        cur.execute("DELETE FROM task_items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()

def move_item(item_id: int, direction: str):
    """
    Swap position with previous/next item inside the same task.
    """
    conn = _connect()
    cur = conn.cursor()
    is_pg = _get_db_url() is not None

    # find current item
    if is_pg:
        cur.execute("SELECT task_id, position FROM task_items WHERE id=%s", (item_id,))
    else:
        cur.execute("SELECT task_id, position FROM task_items WHERE id=?", (item_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return
    task_id, pos = int(row[0]), int(row[1])

    # find neighbor
    if direction == "up":
        if is_pg:
            cur.execute(
                "SELECT id, position FROM task_items WHERE task_id=%s AND position < %s ORDER BY position DESC LIMIT 1",
                (task_id, pos),
            )
        else:
            cur.execute(
                "SELECT id, position FROM task_items WHERE task_id=? AND position < ? ORDER BY position DESC LIMIT 1",
                (task_id, pos),
            )
    else:
        if is_pg:
            cur.execute(
                "SELECT id, position FROM task_items WHERE task_id=%s AND position > %s ORDER BY position ASC LIMIT 1",
                (task_id, pos),
            )
        else:
            cur.execute(
                "SELECT id, position FROM task_items WHERE task_id=? AND position > ? ORDER BY position ASC LIMIT 1",
                (task_id, pos),
            )

    nb = cur.fetchone()
    if not nb:
        conn.close()
        return

    nb_id, nb_pos = int(nb[0]), int(nb[1])

    # swap
    if is_pg:
        cur.execute("UPDATE task_items SET position=%s WHERE id=%s", (nb_pos, item_id))
        cur.execute("UPDATE task_items SET position=%s WHERE id=%s", (pos, nb_id))
    else:
        cur.execute("UPDATE task_items SET position=? WHERE id=?", (nb_pos, item_id))
        cur.execute("UPDATE task_items SET position=? WHERE id=?", (pos, nb_id))

    conn.commit()
    conn.close()

# -----------------------
# Logs
# -----------------------
def add_task_log(task_id: int, actor: str, message: str):
    conn = _connect()
    cur = conn.cursor()
    now = _now()
    is_pg = _get_db_url() is not None

    if is_pg:
        cur.execute(
            "INSERT INTO task_logs (task_id, actor, message, created_at) VALUES (%s,%s,%s,%s)",
            (task_id, actor, message, now),
        )
    else:
        cur.execute(
            "INSERT INTO task_logs (task_id, actor, message, created_at) VALUES (?,?,?,?)",
            (task_id, actor, message, now),
        )
    conn.commit()
    conn.close()

def get_task_logs(task_id: int) -> List[Dict[str, Any]]:
    conn = _connect()
    cur = conn.cursor()
    is_pg = _get_db_url() is not None

    if is_pg:
        cur.execute(
            "SELECT id, task_id, actor, message, created_at FROM task_logs WHERE task_id=%s ORDER BY id DESC",
            (task_id,),
        )
    else:
        cur.execute(
            "SELECT id, task_id, actor, message, created_at FROM task_logs WHERE task_id=? ORDER BY id DESC",
            (task_id,),
        )
    rows = cur.fetchall()
    conn.close()
    cols = ["id","task_id","actor","message","created_at"]
    return [dict(zip(cols, r)) for r in rows]
