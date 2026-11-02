# Brayd Payroll

Small local payroll calculator using Python 3.10+ and SQLite.

1. Copy `employees.csv` and `clock_events.csv` from the assessment ZIP into this folder.
2. Run `python payroll.py load`.
3. Run `python payroll.py run 2026-10`.
4. View a payslip: `python payroll.py payslip E01 2026-10`.
5. After payroll is paid, run `python payroll.py lock 2026-10`.
6. Put `late_events.csv` here and run `python payroll.py late late_events.csv`.

Install test dependency: `python -m pip install pytest`; run `python -m pytest -q`.
See `NOTES.md` for design and explanation. SQL reports are in `report.sql`.
