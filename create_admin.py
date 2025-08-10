import sqlite3

DB_NAME = "factory.db"

# Connect to database
conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

# Create tables if they don't exist (for safety)
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT NOT NULL,
    name TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    blocked INTEGER NOT NULL DEFAULT 0,
    telegram_id INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS productions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    production_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    date TEXT NOT NULL
)
""")

# Add one admin user
admin_data = ("admin", "admin123", "Admin Boss", 1, 0, None)
cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?)", admin_data)

conn.commit()
conn.close()

print("✅ Admin and Worker users created:")
print("- Admin → username: admin, password: admin123")
