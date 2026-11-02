#!/usr/bin/env python3
"""Brayd field-worker payroll calculator (Python 3.10+, SQLite only)."""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

DB_PATH = Path("payroll.db")
IST = timedelta(hours=5, minutes=30)


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(con: sqlite3.Connection) -> None:
    con.executescript("""
    CREATE TABLE IF NOT EXISTS employees (
        employee_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        site TEXT NOT NULL,
        monthly_gross_inr TEXT NOT NULL,
        join_date TEXT NOT NULL,
        shift_start_ist TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS clock_events (
        event_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL REFERENCES employees(employee_id),
        type TEXT NOT NULL CHECK(type IN ('IN','OUT')),
        device_time TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        source_file TEXT NOT NULL DEFAULT 'clock_events.csv'
    );
    CREATE INDEX IF NOT EXISTS idx_events_employee ON clock_events(employee_id);
    CREATE TABLE IF NOT EXISTS payslips (
        employee_id TEXT NOT NULL REFERENCES employees(employee_id),
        period TEXT NOT NULL,
        paid_days TEXT NOT NULL,
        late_days INTEGER NOT NULL,
        overtime_minutes INTEGER NOT NULL,
        gross_pay TEXT NOT NULL,
        overtime_pay TEXT NOT NULL,
        late_deduction TEXT NOT NULL,
        net_pay TEXT NOT NULL,
        flags TEXT NOT NULL DEFAULT '',
        locked INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(employee_id, period)
    );
    CREATE TABLE IF NOT EXISTS payslip_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT NOT NULL REFERENCES employees(employee_id),
        period TEXT NOT NULL,
        item_code TEXT NOT NULL,
        description TEXT NOT NULL,
        amount TEXT NOT NULL,
        UNIQUE(employee_id, period, item_code)
    );
    CREATE TABLE IF NOT EXISTS month_locks (
        period TEXT PRIMARY KEY,
        locked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)
    con.commit()


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def rupees(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def parse_device_time(value: str) -> datetime:
    """Parse ISO timestamps; Z and explicit offsets are supported. Naive values mean IST."""
    dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone_ist())
    return dt.astimezone(timezone_ist())


def timezone_ist():
    from datetime import timezone
    return timezone(IST)


def parse_clock(value: str) -> time:
    return time.fromisoformat(value.strip())


def load_csv(con: sqlite3.Connection, employees_file="employees.csv",
             events_file="clock_events.csv") -> None:
    init_db(con)
    with open(employees_file, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            con.execute("""
                INSERT INTO employees(employee_id,name,site,monthly_gross_inr,join_date,shift_start_ist)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(employee_id) DO UPDATE SET
                  name=excluded.name, site=excluded.site,
                  monthly_gross_inr=excluded.monthly_gross_inr,
                  join_date=excluded.join_date, shift_start_ist=excluded.shift_start_ist
            """, (r["employee_id"].strip(), r["name"].strip(), r["site"].strip(),
                  str(r["monthly_gross_inr"]).strip(), r["join_date"].strip(),
                  r["shift_start_ist"].strip()))
    with open(events_file, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            con.execute("""
                INSERT OR IGNORE INTO clock_events
                (event_id,employee_id,type,device_time,uploaded_at,source_file)
                VALUES(?,?,?,?,?,'clock_events.csv')
            """, (r["event_id"].strip(), r["employee_id"].strip(),
                  r["type"].strip().upper(), r["device_time"].strip(),
                  r["uploaded_at"].strip()))
    con.commit()


def month_bounds(period: str) -> tuple[date, date]:
    year, month = map(int, period.split("-"))
    first = date(year, month, 1)
    next_month = date(year + (month == 12), month % 12 + 1, 1)
    return first, next_month - timedelta(days=1)


def get_events(con: sqlite3.Connection, employee_id: str, start: date, end: date):
    rows = con.execute("""
        SELECT event_id, type, device_time FROM clock_events
        WHERE employee_id=? ORDER BY event_id
    """, (employee_id,)).fetchall()
    by_day = defaultdict(list)
    for row in rows:
        dt = parse_device_time(row["device_time"])
        d = dt.date()
        if start <= d <= end:
            by_day[d].append((row["type"], dt, row["event_id"]))
    return by_day


def calculate_employee(con: sqlite3.Connection, employee: sqlite3.Row,
                       period: str) -> dict:
    start, end = month_bounds(period)
    join_date = date.fromisoformat(employee["join_date"])
    gross_month = Decimal(employee["monthly_gross_inr"])
    daily_rate = gross_month / Decimal((end - start).days + 1)
    hourly_rate = daily_rate / Decimal(8)

    sundays = sum(1 for n in range((end-start).days + 1)
                  if (d := start + timedelta(days=n)) >= join_date and d.weekday() == 6)

    full_days = half_days = late_days = overtime_minutes = 0
    missing_days = []
    events_by_day = get_events(con, employee["employee_id"], start, end)
    shift_start = parse_clock(employee["shift_start_ist"])

    for day, events in events_by_day.items():
        if day < join_date or day.weekday() == 6:
            continue
        ins = [dt for typ, dt, _ in events if typ == "IN"]
        outs = [dt for typ, dt, _ in events if typ == "OUT"]
        if not ins and not outs:
            continue
        if not ins or not outs:
            missing_days.append(day.isoformat())
            continue
        earliest_in = min(ins)
        latest_out = max(outs)
        worked = max(0, int((latest_out - earliest_in).total_seconds() // 60))
        if worked >= 240:
            full_days += 1
        elif worked > 0:
            half_days += 1
        else:
            # Zero/negative duration is not a worked day.
            continue
        if earliest_in.time().replace(tzinfo=None) > (
            datetime.combine(day, shift_start) + timedelta(minutes=10)
        ).time():
            late_days += 1
        overtime_minutes += max(0, worked - 540)

    paid_days = Decimal(sundays + full_days) + Decimal(half_days) / Decimal(2)
    base_pay = money(daily_rate * paid_days)
    overtime_pay = money(Decimal(overtime_minutes) * hourly_rate * Decimal("1.5") / Decimal(60))
    late_deduction = money(daily_rate * Decimal(late_days // 3) / Decimal(2))
    net = rupees(base_pay + overtime_pay - late_deduction)
    flags = [f"MISSING_PUNCH:{d}" for d in sorted(missing_days)]
    return {
        "employee_id": employee["employee_id"], "period": period,
        "paid_days": str(paid_days), "late_days": late_days,
        "overtime_minutes": overtime_minutes, "gross_pay": str(base_pay),
        "overtime_pay": str(overtime_pay), "late_deduction": str(late_deduction),
        "net_pay": str(net), "flags": ", ".join(flags),
    }


def run_payroll(con: sqlite3.Connection, period: str) -> None:
    init_db(con)
    if con.execute("SELECT 1 FROM month_locks WHERE period=?", (period,)).fetchone():
        raise RuntimeError(f"{period} is locked; payroll cannot be changed.")
    employees = con.execute("SELECT * FROM employees ORDER BY employee_id").fetchall()
    for emp in employees:
        result = calculate_employee(con, emp, period)
        con.execute("""
          INSERT INTO payslips(employee_id,period,paid_days,late_days,overtime_minutes,
            gross_pay,overtime_pay,late_deduction,net_pay,flags,locked)
          VALUES(:employee_id,:period,:paid_days,:late_days,:overtime_minutes,
            :gross_pay,:overtime_pay,:late_deduction,:net_pay,:flags,0)
          ON CONFLICT(employee_id,period) DO UPDATE SET
            paid_days=excluded.paid_days, late_days=excluded.late_days,
            overtime_minutes=excluded.overtime_minutes, gross_pay=excluded.gross_pay,
            overtime_pay=excluded.overtime_pay, late_deduction=excluded.late_deduction,
            net_pay=excluded.net_pay, flags=excluded.flags
        """, result)
        for code, desc, amount in [
            ("BASE", "Base pay", result["gross_pay"]),
            ("OVERTIME", "Overtime pay", result["overtime_pay"]),
            ("LATE", "Late deduction", str(-Decimal(result["late_deduction"]))),
        ]:
            con.execute("""
              INSERT INTO payslip_items(employee_id,period,item_code,description,amount)
              VALUES(?,?,?,?,?)
              ON CONFLICT(employee_id,period,item_code) DO UPDATE SET
                description=excluded.description, amount=excluded.amount
            """, (result["employee_id"], period, code, desc, amount))
    con.commit()


def lock_month(con: sqlite3.Connection, period: str) -> None:
    if not con.execute("SELECT 1 FROM payslips WHERE period=? LIMIT 1", (period,)).fetchone():
        raise RuntimeError(f"No payslips exist for {period}; run payroll first.")
    con.execute("INSERT OR IGNORE INTO month_locks(period) VALUES(?)", (period,))
    con.execute("UPDATE payslips SET locked=1 WHERE period=?", (period,))
    con.commit()


def load_late_events(con: sqlite3.Connection, late_file: str) -> None:
    if not con.execute("SELECT 1 FROM month_locks WHERE period='2026-10'").fetchone():
        raise RuntimeError("October 2026 must be locked before late events are loaded.")
    with open(late_file, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            con.execute("""
              INSERT OR IGNORE INTO clock_events
              (event_id,employee_id,type,device_time,uploaded_at,source_file)
              VALUES(?,?,?,?,?,?)
            """, (r["event_id"].strip(), r["employee_id"].strip(),
                  r["type"].strip().upper(), r["device_time"].strip(),
                  r["uploaded_at"].strip(), Path(late_file).name))
    con.commit()

    # Recompute the whole month using original + newly accepted events.
    affected = con.execute("""
      SELECT DISTINCT employee_id FROM clock_events WHERE source_file=?
    """, (Path(late_file).name,)).fetchall()
    for row in affected:
        emp_id = row["employee_id"]
        emp = con.execute("SELECT * FROM employees WHERE employee_id=?", (emp_id,)).fetchone()
        if emp is None:
            raise RuntimeError(f"Unknown employee in late file: {emp_id}")
        revised = calculate_employee(con, emp, "2026-10")
        locked = con.execute(
            "SELECT net_pay FROM payslips WHERE employee_id=? AND period='2026-10'",
            (emp_id,)).fetchone()
        if locked is None:
            raise RuntimeError(f"No locked October payslip for {emp_id}")
        arrears = Decimal(revised["net_pay"]) - Decimal(locked["net_pay"])
        con.execute("""
          INSERT INTO payslip_items(employee_id,period,item_code,description,amount)
          VALUES(?,'2026-11','ARREARS_OCT_2026',?,?)
          ON CONFLICT(employee_id,period,item_code) DO UPDATE SET
            description=excluded.description, amount=excluded.amount
        """, (emp_id, "October 2026 late-upload arrears", str(money(arrears))))
    con.commit()


def print_payslip(con: sqlite3.Connection, employee_id: str, period: str) -> None:
    row = con.execute("""
      SELECT p.*, e.name, e.site, e.monthly_gross_inr
      FROM payslips p JOIN employees e USING(employee_id)
      WHERE p.employee_id=? AND p.period=?
    """, (employee_id, period)).fetchone()
    if row is None:
        raise RuntimeError("Payslip not found. Run payroll first.")
    print(f"PAYSLIP — {row['period']}")
    print(f"Employee: {row['employee_id']} | {row['name']} | Site: {row['site']}")
    print(f"Monthly gross: ₹{row['monthly_gross_inr']}")
    print(f"Paid days: {row['paid_days']} | Late days: {row['late_days']} | "
          f"Overtime: {row['overtime_minutes']} minutes")
    items = con.execute("""
      SELECT description, amount FROM payslip_items
      WHERE employee_id=? AND period=? ORDER BY item_id
    """, (employee_id, period)).fetchall()
    for item in items:
        print(f"{item['description']}: ₹{item['amount']}")
    print(f"Net pay: ₹{row['net_pay']}")
    print(f"Flags: {row['flags'] or 'None'}")
    if row["locked"]:
        print("Status: LOCKED")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Brayd field-worker payroll")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("load")
    run_p = sub.add_parser("run"); run_p.add_argument("period")
    slip_p = sub.add_parser("payslip"); slip_p.add_argument("employee_id"); slip_p.add_argument("period")
    lock_p = sub.add_parser("lock"); lock_p.add_argument("period")
    late_p = sub.add_parser("late"); late_p.add_argument("csv_file")
    args = parser.parse_args(argv)
    try:
        with connect() as con:
            init_db(con)
            if args.command == "load":
                load_csv(con)
                print("Employees and clock events loaded.")
            elif args.command == "run":
                run_payroll(con, args.period)
                print(f"Payroll saved for {args.period}.")
            elif args.command == "payslip":
                print_payslip(con, args.employee_id, args.period)
            elif args.command == "lock":
                lock_month(con, args.period)
                print(f"{args.period} locked.")
            elif args.command == "late":
                load_late_events(con, args.csv_file)
                print("Late events loaded; November arrears updated.")
        return 0
    except (OSError, sqlite3.Error, ValueError, KeyError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
