import sqlite3

conn = sqlite3.connect("restaurant.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_no INTEGER,
    items TEXT,
    total REAL,
    status TEXT
)
""")

conn.commit()
conn.close()

print("✅ orders table created")
