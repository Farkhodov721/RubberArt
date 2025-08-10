import sqlite3
from datetime import datetime

DB_NAME = "factory.db"


def connect():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = connect()
    cur = conn.cursor()

    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        name TEXT,
        is_admin INTEGER DEFAULT 0,
        blocked INTEGER DEFAULT 0,
        telegram_id INTEGER
    )
    """)

    # Productions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS productions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        production_type TEXT,
        quantity INTEGER,
        date TEXT
    )
    """)

    # --- Ensure new 'model' column exists ---
    cur.execute("PRAGMA table_info(productions)")
    existing_cols = [row[1] for row in cur.fetchall()]
    if "model" not in existing_cols:
        cur.execute("ALTER TABLE productions ADD COLUMN model TEXT")

    conn.commit()
    conn.close()


def get_user(username):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "username": row[0],
            "password": row[1],
            "name": row[2],
            "is_admin": bool(row[3]),
            "blocked": bool(row[4]),
            "telegram_id": row[5]
        }
    return None


def get_all_users():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users")
    rows = cur.fetchall()
    conn.close()
    users = {}
    for row in rows:
        users[row[0]] = {
            "password": row[1],
            "name": row[2],
            "is_admin": bool(row[3]),
            "blocked": bool(row[4]),
            "telegram_id": row[5]
        }
    return users


def add_user(username, password, name, is_admin=False):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (username, password, name, is_admin, blocked)
        VALUES (?, ?, ?, ?, 0)
    """, (username, password, name, int(is_admin)))
    conn.commit()
    conn.close()


def update_user(username, updates: dict):
    conn = connect()
    cur = conn.cursor()
    for key, value in updates.items():
        cur.execute(f"UPDATE users SET {key} = ? WHERE username = ?", (value, username))
    conn.commit()
    conn.close()


def save_production(data: dict):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO productions (name, production_type, quantity, date, model)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data["name"],
        data["production_type"],
        data["quantity"],
        data["date"],
        data.get("model")  # optional
    ))
    conn.commit()
    conn.close()


def get_productions():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM productions ORDER BY date DESC")
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "name": row[1],
            "production_type": row[2],
            "quantity": row[3],
            "date": row[4],
            "model": row[5] if len(row) > 5 else None
        }
        for row in rows
    ]


def update_production(entry_id, updates: dict):
    conn = connect()
    cur = conn.cursor()
    for key, value in updates.items():
        cur.execute(f"UPDATE productions SET {key} = ? WHERE id = ?", (value, entry_id))
    conn.commit()
    conn.close()


def delete_user(username):
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
