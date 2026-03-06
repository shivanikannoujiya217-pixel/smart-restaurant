import sqlite3

conn = sqlite3.connect("restaurant.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_no INTEGER,
    total_amount REAL,
    status TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    amount REAL,
    payment_method TEXT,
    payment_time DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
     items_items,
    bill_amount REAL,
    bill_time DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS sales_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    bill_id INTEGER,
    amount REAL,
    sale_date DATE DEFAULT CURRENT_DATE
)
""")

print("✅ All tables created successfully")

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()

print("Tables in DB:")
for t in tables:
    print("-", t[0])

print("\nOrders table columns:")
cur.execute("PRAGMA table_info(orders)")
for col in cur.fetchall():
    print(col)

conn.commit()
conn.close()
