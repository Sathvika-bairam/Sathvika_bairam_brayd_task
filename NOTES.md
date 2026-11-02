# Brayd Payroll Calculator — Round 1 Notes

## Run it
Use Python 3.10+ from this folder. Put `employees.csv` and `clock_events.csv`
beside `payroll.py`, then run:

```bash
python payroll.py load
python payroll.py run 2026-10
python payroll.py payslip E01 2026-10
python payroll.py lock 2026-10
python payroll.py late late_events.csv
```

Run tests with `python -m pip install pytest` and `python -m pytest -q`.

## Design
- SQLite is the only database. `employees`, `clock_events`, `payslips`,
  `payslip_items`, and `month_locks` hold the input and payroll results.
- `event_id` is the primary key, so re-uploading an event cannot add a second copy.
- ISO timestamps are parsed with their timezone offset and converted to IST before
  extracting the attendance date or comparing shift times. A timestamp without an
  offset is treated as IST.
- For each non-Sunday day after joining, the script selects the earliest IN and
  latest OUT. A missing side creates a `MISSING_PUNCH` flag. Work of 240 minutes
  or more is a full day; positive work below that is a half day.
- Sundays on or after joining are paid weekly offs. Overtime is the minutes above
  540, and late deductions are applied in blocks of three qualifying late days.
- Decimal arithmetic is used for money. Line items are rounded to paisa; net pay
  is rounded to the nearest rupee using half-up rounding.
- Payslips have a unique `(employee_id, period)` key and are upserted, so rerunning
  payroll updates the same record rather than inserting duplicates. Locking adds a
  month-lock record; later `run` commands refuse to alter that month.
- Late uploads are deduplicated by `event_id`. The script recomputes the affected
  employee's October result using all accepted events, compares it with the locked
  net pay, and upserts one November arrears line. It does not update October's
  locked payslip.

## SQL report interpretation
Run the two queries in `report.sql` using SQLite, for example:
`sqlite3 payroll.db < report.sql`.

The second query's returned employees must be checked against their attendance
flags and day counts. A result can be correct when the employee joined part-way
through October, had absences, missing punches, or accumulated late deductions.
It may indicate a bug if the underlying valid punches were missed, a timezone/day
boundary was handled incorrectly, or an eligible Sunday/workday was not counted.
Write the employee-specific explanation after running the supplied assessment data;
the CSVs are needed to identify the actual returned employees, so do not guess.

## Before the live round
Be ready to explain `parse_device_time`, `calculate_employee`, the unique keys,
the lock check, and the late-arrears upsert. Practise changing the shift grace
period or full-day threshold and rerunning the tests.
