import sqlite3

con = sqlite3.connect("payroll.db")

cursor = con.execute("""
SELECT *
FROM payslip_items
WHERE period = '2026-11'
""")

for row in cursor.fetchall():
    print(row)

con.close()