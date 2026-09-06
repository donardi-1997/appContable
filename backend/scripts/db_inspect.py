"""Quick DB inspection."""
import sqlite3
conn = sqlite3.connect('gato_contable.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('All tables:', tables)
for t in tables:
    cur.execute(f"PRAGMA table_info({t})")
    cols = cur.fetchall()
    print(f'\n{t} columns:', [c[1] for c in cols])
    cur.execute(f"SELECT * FROM {t} LIMIT 2")
    rows = cur.fetchall()
    for r in rows:
        print(f'  {r}')
cur.execute("SELECT DISTINCT status FROM sales")
print('\nSale statuses:', [r[0] for r in cur.fetchall()])
cur.execute("SELECT COUNT(*) FROM sales")
print('Total sales:', cur.fetchone()[0])
conn.close()
