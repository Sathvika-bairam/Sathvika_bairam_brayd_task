# Brayd Payroll Calculator — Implementation Notes

## 1. Assumptions and edge cases

- ISO-8601 timestamps with an explicit timezone offset are converted to IST (UTC+05:30). Timestamps without an offset are assumed to be IST.
- Attendance events are grouped by their IST calendar date. For each non-Sunday, the earliest IN and latest OUT are selected.
- If either IN or OUT is missing, the day is treated as absent and marked with `MISSING_PUNCH`. Days with no events are also treated as absent.
- A valid pair of punches with at least 240 worked minutes counts as a full day. Positive work below 240 minutes counts as a half-day. A negative duration is clamped to zero.
- Sundays on or after the joining date are paid weekly offs, and Sunday clock events are ignored. Dates before joining are excluded.
- October daily pay is calculated using 31 days. Other months use their actual calendar-day count.
- An employee is late when the earliest IN is strictly more than 10 minutes after shift start. A half-day salary deduction is applied for every complete group of three late days.
- Overtime is calculated for minutes beyond 540 worked minutes per day and paid at 1.5 times the hourly rate.
- I use `Decimal` for monetary calculations, round line items to paise, and round final net pay to the nearest rupee using half-up rounding.

## 2. SQL report interpretation

The second SQL report returned these employees with net pay below 75% of gross:

- **E04 — Fatima Begum:** Gross ₹18,600; net ₹2,400; 12.90% of gross.
- **E03 — Arjun Reddy:** Gross ₹27,900; net ₹17,123; 61.37% of gross.

Both employees meet the report condition. The SQL result identifies the difference but does not by itself explain the reason. I would review their payslips, paid days, attendance flags, and deductions before identifying the cause. I have not assumed a reason without verifying the attendance records.

## 3. Duplicate prevention and payroll locking

- I use `event_id` as the primary key for clock events to prevent duplicate attendance records.
- A unique constraint on `(employee_id, period)` prevents duplicate payslips for the same employee and month.
- I use an upsert so that rerunning an unlocked payroll updates the existing payslip instead of creating another one.
- Once a month is locked, the payroll run command refuses to recalculate that month.
- Late attendance is processed after the October lock. The difference between the corrected October calculation and the locked October result is stored as a November arrears line.
- The arrears entry is upserted, so uploading the same late events again does not duplicate the adjustment. The original October payslip remains unchanged.

## 4. Bug encountered and validation

During validation, I found that a command was executing an old unconditional main block and printing October payroll even when I requested a November payslip. I corrected the CLI flow so that only the requested subcommand runs, then tested the payslip command again.

I also checked the attendance calculation for a negative same-date interval and made it follow the under-240-minute rule by clamping the duration to zero.

## 5. What I would improve with one more day

I would add more integration tests for employees joining during a month, missing punches, multiple IN/OUT events, and timestamps close to midnight. I would also improve validation messages for malformed CSV records and add a reconciliation report to make attendance corrections and arrears easier to audit.
