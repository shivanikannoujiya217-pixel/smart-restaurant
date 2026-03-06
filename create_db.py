import sqlite3

conn = sqlite3.connect("restaurant.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_no INTEGER,
    items TEXT,
    total INTEGER,
    status TEXT
)
""")

conn.commit()
conn.close()

print("Database & orders table created")
