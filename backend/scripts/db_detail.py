"""Detailed DB inspection for E2E test."""
import sqlite3
conn = sqlite3.connect('gato_contable.db')
cur = conn.cursor()

print("=== SALE V-00002 (completada) ===")
cur.execute("SELECT * FROM sales WHERE status='completada' LIMIT 1")
sale = cur.fetchone()
print(f"  id={sale[0]}, number={sale[1]}, customer={sale[2]}, method={sale[3]}, total={sale[4]}, status={sale[5]}")

print("\n=== SALE ITEMS for sale_id=2 ===")
cur.execute("SELECT si.id, si.product_id, si.quantity, si.unit_price, p.name FROM sale_items si LEFT JOIN products p ON si.product_id = p.id WHERE si.sale_id = 2")
for row in cur.fetchall():
    print(f"  item_id={row[0]}, product={row[4]}, qty={row[2]}, unit_price={row[3]}, subtotal={row[2]*row[3]}")

print("\n=== COMPANY INFO ===")
cur.execute("SELECT company_name, nit, dv, address, municipality, department, country, email, regime, responsibilities, resolution_number, resolution_prefix, resolution_range_from, resolution_range_to, resolution_date, software_id, certificate_path FROM company_info LIMIT 1")
row = cur.fetchone()
if row:
    for i, val in enumerate(row):
        labels = ['company_name','nit','dv','address','municipality','department','country','email','regime','responsibilities','resolution_number','resolution_prefix','resolution_range_from','resolution_range_to','resolution_date','software_id','certificate_path']
        print(f"  {labels[i]}: {val}")

print("\n=== ALL SALES ===")
cur.execute("SELECT id, number, customer_name, status, total FROM sales ORDER BY id")
for r in cur.fetchall():
    print(f"  id={r[0]}, number={r[1]}, customer={r[2]}, status={r[3]}, total={r[4]}")

print("\n=== PRODUCTS (active) ===")
cur.execute("SELECT id, name, price, active FROM products WHERE active=1")
for r in cur.fetchall():
    print(f"  id={r[0]}, name={r[1]}, price={r[2]}")

conn.close()
