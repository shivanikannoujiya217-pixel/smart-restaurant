import sqlite3
conn=sqlite3.connect('restaurant.db')
cur=conn.cursor()
print('TABLES:')
for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(row[0])
print('\norders schema:')
for row in cur.execute("PRAGMA table_info(orders)"):
    print(row)
conn.close()
