import csv
from decimal import Decimal
import pytest

from payroll import connect, init_db, load_csv, run_payroll, lock_month, load_late_events


def write_csv(path, headers, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def setup(tmp_path):
    db = tmp_path / "test.db"
    emp = tmp_path / "employees.csv"
    events = tmp_path / "clock_events.csv"
    write_csv(emp, ["employee_id","name","site","monthly_gross_inr","join_date","shift_start_ist"], [
        dict(employee_id="E01", name="Asha", site="North", monthly_gross_inr="31000",
             join_date="2026-10-01", shift_start_ist="09:00"),
    ])
    # Duplicate event_id is deliberately repeated; Z timestamp is 14:00 IST.
    write_csv(events, ["event_id","employee_id","type","device_time","uploaded_at"], [
        dict(event_id="a", employee_id="E01", type="IN", device_time="2026-10-05T03:30:00Z", uploaded_at="2026-10-05T10:00:00+05:30"),
        dict(event_id="a", employee_id="E01", type="IN", device_time="2026-10-05T03:30:00Z", uploaded_at="2026-10-05T10:01:00+05:30"),
        dict(event_id="b", employee_id="E01", type="OUT", device_time="2026-10-05T18:30:00+05:30", uploaded_at="2026-10-05T18:31:00+05:30"),
    ])
    con = connect(db); init_db(con); load_csv(con, emp, events)
    yield con, tmp_path
    con.close()


def test_load_deduplicates_event_ids(setup):
    con, _ = setup
    assert con.execute("SELECT COUNT(*) FROM clock_events").fetchone()[0] == 2


def test_payroll_twice_does_not_duplicate_payslips(setup):
    con, _ = setup
    run_payroll(con, "2026-10")
    first = con.execute("SELECT COUNT(*) FROM payslips").fetchone()[0]
    run_payroll(con, "2026-10")
    second = con.execute("SELECT COUNT(*) FROM payslips").fetchone()[0]
    assert first == second == 1


def test_utc_conversion_and_overtime(setup):
    con, _ = setup
    run_payroll(con, "2026-10")
    row = con.execute("SELECT overtime_minutes, paid_days FROM payslips WHERE employee_id='E01'").fetchone()
    # 09:00 to 18:30 IST = 570 minutes; 30 minutes overtime.
    assert row["overtime_minutes"] == 30
    assert Decimal(row["paid_days"]) == Decimal("5")  # 4 Sundays in October + one full workday


def test_lock_blocks_recalculation(setup):
    con, _ = setup
    run_payroll(con, "2026-10")
    lock_month(con, "2026-10")
    with pytest.raises(RuntimeError):
        run_payroll(con, "2026-10")


def test_late_upload_arrears_is_idempotent(setup):
    con, tmp = setup
    run_payroll(con, "2026-10")
    lock_month(con, "2026-10")
    late = tmp / "late_events.csv"
    write_csv(late, ["event_id","employee_id","type","device_time","uploaded_at"], [
        dict(event_id="c", employee_id="E01", type="IN", device_time="2026-10-06T03:30:00Z", uploaded_at="2026-11-02T10:00:00+05:30"),
        dict(event_id="d", employee_id="E01", type="OUT", device_time="2026-10-06T18:30:00+05:30", uploaded_at="2026-11-02T10:01:00+05:30"),
    ])
    load_late_events(con, str(late))
    first = con.execute("SELECT amount FROM payslip_items WHERE employee_id='E01' AND period='2026-11' AND item_code='ARREARS_OCT_2026'").fetchone()[0]
    load_late_events(con, str(late))
    second = con.execute("SELECT amount FROM payslip_items WHERE employee_id='E01' AND period='2026-11' AND item_code='ARREARS_OCT_2026'").fetchone()[0]
    assert first == second
    assert con.execute("SELECT locked FROM payslips WHERE employee_id='E01' AND period='2026-10'").fetchone()[0] == 1
