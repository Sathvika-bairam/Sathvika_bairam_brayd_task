# Brayd Field-Worker Payroll Calculator

-  A small command-line payroll calculator built with Python 3.10+ and SQLite.
-  It reads employee and attendance CSV files, calculates monthly payroll, prints
  payslips, locks finalized months, and carries late attendance corrections into
  the following month's arrears.

## Features

-   CSV ingestion for employee master data, regular clock events, and
    late-arriving events.
-   SQLite database creation and persistence.
-   Attendance processing using Indian Standard Time (IST).
-   Duplicate event handling and validation.
-   Full-day, half-day, absent-day, weekly-off, late-arrival, and
    overtime calculations.
-   Monthly payroll calculation and employee payslip generation.
-   Payroll period locking to protect finalized payroll.
-   Late-event reconciliation with adjustments posted to November 2026
    instead of modifying locked October payroll.
-   SQL reports for site-level payroll totals and employees whose net
    pay is below 75% of monthly gross.
-   Automated tests using `pytest`.

## Project structure

``` text
brayd-payroll/
├── payroll.py
├── run_report.py
├── report.sql
├── README.md
├── NOTES.md
├── .gitignore
├── data/
│   ├── employees.csv
│   ├── clock_events.csv
│   └── late_events.csv
└── tests/
    └── test_payroll.py
```

`payroll.db` is generated locally by the application and must not be
committed to version control.

## Requirements

-  Python 3.10 or newer
- `pytest` for running tests
- SQLite is included in Python's standard library (`sqlite3`); no separate
  SQLite installation is needed.


## Setup

### Windows Command Prompt

``` bat
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install pytest
```

### Windows PowerShell

``` powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install pytest
```

## Run the application

Run commands from the project root directory.

### 1. Initialize the database

``` bash
python payroll.py init
```

Creates the SQLite database and required tables.

### 2. Load input data

``` bash
python payroll.py load
```

Loads employee master records and regular clock events from the CSV
files in `data/`. Re-running the command should not create duplicate
records.

### 3. Review October attendance

``` bash
python payroll.py attendance 2026-10
```

Displays the attendance summary for October 2026.

### 4. Calculate October payroll

``` bash
python payroll.py run 2026-10
```

Calculates and saves October payroll for the employees, then displays
the payslips.

### 5. Generate an individual payslip

``` bash
python payroll.py payslip E01 2026-10
```

Replace `E01` with another employee ID to display a different employee's
payslip. Use `ALL` to display all available payslips:

``` bash
python payroll.py payslip ALL 2026-10
```

### 6. Lock October payroll

``` bash
python payroll.py lock 2026-10
```

Locks the finalized October payroll period. A locked period cannot be
recalculated.

### 7. Import late-arriving events and calculate arrears

``` bash
python payroll.py late data/late_events.csv
```

Imports late events after October has been locked. The system calculates
the difference against the locked October payroll and posts the
adjustment to November 2026. It does not overwrite the October payslips.

### 8. View November payslips

``` bash
python payroll.py payslip ALL 2026-11
```

Displays November payslips for employees with arrears adjustments. If
November payroll has already been calculated, the adjustment is added to
its existing net pay.

## October 2026 employee payslips

The following are the successful outputs of the requested CLI command:

``` bash
python payroll.py payslip <employee_id> 2026-10
```

### E01 --- Ravi Kumar

``` text
================================================
Employee: E01 - Ravi Kumar
Site: Kokapet
Payroll month: 2026-10
Monthly gross: ₹24,000
Paid days: 28.5
Base pay: ₹22,064.52
Overtime pay: ₹70.16
Late deduction: ₹0.00
Arrears: ₹0.00
Net pay: ₹22,135
================================================
```

### E02 --- Lakshmi Devi

``` text
================================================
Employee: E02 - Lakshmi Devi
Site: Kokapet
Payroll month: 2026-10
Monthly gross: ₹21,500
Paid days: 29.0
Base pay: ₹20,112.90
Overtime pay: ₹0.00
Late deduction: ₹346.77
Arrears: ₹0.00
Net pay: ₹19,766
================================================
```

### E03 --- Arjun Reddy

``` text
================================================
Employee: E03 - Arjun Reddy
Site: Gachibowli
Payroll month: 2026-10
Monthly gross: ₹27,900
Paid days: 19.0
Base pay: ₹17,100.00
Overtime pay: ₹22.50
Late deduction: ₹0.00
Arrears: ₹0.00
Net pay: ₹17,123
================================================
```

### E04 --- Fatima Begum

``` text
================================================
Employee: E04 - Fatima Begum
Site: Gachibowli
Payroll month: 2026-10
Monthly gross: ₹18,600
Paid days: 15.5
Base pay: ₹9,300.00
Overtime pay: ₹0.00
Late deduction: ₹0.00
Arrears: ₹0.00
Net pay: ₹9,300
================================================
```

### E05 --- Suresh Naidu

``` text
================================================
Employee: E05 - Suresh Naidu
Site: Kokapet
Payroll month: 2026-10
Monthly gross: ₹31,000
Paid days: 31.0
Base pay: ₹31,000.00
Overtime pay: ₹3,809.38
Late deduction: ₹1,000.00
Arrears: ₹0.00
Net pay: ₹33,809
================================================
```

### October payroll summary

  Employee ID   Employee       Site                 Net pay
  ------------- -------------- ------------ ---------------
  E01           Ravi Kumar     Kokapet              ₹22,135
  E02           Lakshmi Devi   Kokapet              ₹19,766
  E03           Arjun Reddy    Gachibowli           ₹17,123
  E04           Fatima Begum   Gachibowli            ₹9,300
  E05           Suresh Naidu   Kokapet              ₹33,809
                **Total**                     **₹1,02,133**

## SQL reports

The SQL queries are maintained in `report.sql`.

Run the report script after October payroll has been calculated and
locked:

``` bash
python run_sql.py
```

The two reports are:

1.  **Total net pay per site** --- aggregates October 2026 net payroll
    by site.
2.  **Employees below 75% of monthly gross** --- identifies employees
    whose October net pay is less than 75% of their monthly gross and
    calculates their net-pay percentage.

Verified output for Report 1:

``` text
site        | total_net_pay_inr
Kokapet     | 75710
Gachibowli  | 26423
```

The site totals reconcile to the October payroll total of ₹1,02,133.

## Automated tests

Run the test suite from the project root:

``` bash
python -m pytest -q
```

The test suite validates payroll behavior and important processing
rules. The recorded test run completed with **5 tests passing**.

## Implementation notes

-   Naive device timestamps are interpreted as IST.
-   Attendance is grouped by the IST calendar date of each event.
-   Sundays on or after an employee's joining date are treated as paid
    weekly offs.
-   An event day requires at least one `IN` and one `OUT` event.
    Otherwise, the day is treated as absent and flagged as a missing
    punch.
-   For a valid day, the earliest `IN` and latest `OUT` are used.
-   A negative punch interval is treated as an invalid punch sequence.
-   Payroll calculations use Python's `Decimal` for monetary precision
    and explicit rounding.
-   October payroll is locked after finalization. Late-arriving events
    are reconciled through November arrears, preserving the original
    October payslips.
-   See `NOTES.md` for the detailed assumptions and implementation
    decisions.

## Git and generated files

The repository should contain source code, input CSV files, tests, and
documentation. Do not commit generated databases, virtual environments,
or Python cache files.

Recommended `.gitignore` entries:

``` gitignore
# Generated SQLite databases
*.db
*.sqlite
*.sqlite3

# Virtual environments
.venv/
venv/

# Python cache
__pycache__/
*.py[cod]
.pytest_cache/

# Local environment files
.env
```
