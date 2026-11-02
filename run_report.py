import sqlite3

con = sqlite3.connect("payroll.db")

with open("report.sql", "r") as file:
    sql = file.read()

statements = sql.split(";")

for statement in statements:
    statement = statement.strip()

    if statement:
        cursor = con.execute(statement)

        if cursor.description:
            print("\nREPORT")
            print("-" * 60)
            print([column[0] for column in cursor.description])

            for row in cursor.fetchall():
                print(row)

con.close()