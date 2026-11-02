-- 1) Total locked October 2026 net pay by site, highest first.
SELECT e.site, SUM(CAST(p.net_pay AS REAL)) AS total_net_pay_inr
FROM payslips AS p
JOIN employees AS e ON e.employee_id = p.employee_id
JOIN month_locks AS ml ON ml.period = p.period
WHERE p.period = '2026-10' AND p.locked = 1
GROUP BY e.site
ORDER BY total_net_pay_inr DESC;

-- 2) Employees whose locked October net is below 75% of monthly gross.
SELECT e.employee_id, e.name, e.site,
       CAST(e.monthly_gross_inr AS REAL) AS gross_inr,
       CAST(p.net_pay AS REAL) AS net_inr,
       ROUND(100.0 * CAST(p.net_pay AS REAL) /
             NULLIF(CAST(e.monthly_gross_inr AS REAL), 0), 2) AS net_percent_of_gross
FROM payslips AS p
JOIN employees AS e ON e.employee_id = p.employee_id
JOIN month_locks AS ml ON ml.period = p.period
WHERE p.period = '2026-10'
  AND p.locked = 1
  AND CAST(p.net_pay AS REAL) < 0.75 * CAST(e.monthly_gross_inr AS REAL)
ORDER BY net_percent_of_gross ASC, e.employee_id;
