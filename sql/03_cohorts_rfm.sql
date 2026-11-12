-- =====================================================================
-- 03_cohorts_rfm.sql  |  Monthly cohort retention + RFM segments (Day 3)
--
-- "Valid order" = not canceled / unavailable (those never became a purchase).
-- Customer = customer_unique_id (a person), never customer_id.
-- Window: orders up to end_date; cohorts start at start_date (same months as the funnel, see 02).
-- 2016 orders are kept so a 2016 first-time buyer is not mislabelled as a new 2017 customer.
--
-- Builds: shoppulse.mart_cohort_retention, shoppulse.mart_rfm
-- Also returns 3 result sets to save:
--   Q1 repeat-buyer rate                    -> results/03a_repeat_rate.csv
--   Q2 retention triangle (long format)     -> results/03b_cohort_retention.csv
--   Q3 RFM segment summary                  -> results/03c_rfm_segments.csv
-- =====================================================================

DECLARE start_date DATE DEFAULT DATE '2017-01-01';
DECLARE end_date   DATE DEFAULT DATE '2018-08-31';

CREATE OR REPLACE TEMP TABLE valid_orders AS
SELECT customer_unique_id, order_id, purchased_at, DATE(purchased_at) AS purchase_date,
       purchase_month, item_value
FROM shoppulse.fct_orders
WHERE order_status NOT IN ('canceled', 'unavailable')
  AND purchased_at IS NOT NULL
  AND DATE(purchased_at) <= end_date;   -- no lower bound: a person's FIRST order may be in 2016


-- Q1. How many people ever bought twice?  (the headline retention fact)
WITH per_customer AS (
  SELECT customer_unique_id, COUNT(*) AS n_orders
  FROM valid_orders GROUP BY customer_unique_id
)
SELECT
  COUNT(*)                                             AS customers,
  COUNTIF(n_orders >= 2)                               AS repeat_customers,
  ROUND(100 * COUNTIF(n_orders >= 2) / COUNT(*), 2)    AS repeat_customer_pct,
  ROUND(AVG(n_orders), 3)                              AS avg_orders_per_customer,
  MAX(n_orders)                                        AS max_orders
FROM per_customer;


-- Q2. Cohort retention: cohort = month of a person's first valid order.
--     retained(k) = people from that cohort who ordered again in month cohort+k (k >= 1),
--     month 0 is the first order itself (100% by definition).
CREATE OR REPLACE TABLE shoppulse.mart_cohort_retention AS
WITH first_order AS (
  SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
  FROM valid_orders GROUP BY customer_unique_id
),
activity AS (
  SELECT DISTINCT o.customer_unique_id, f.cohort_month,
         DATE_DIFF(o.purchase_month, f.cohort_month, MONTH) AS month_offset
  FROM valid_orders AS o
  JOIN first_order AS f USING (customer_unique_id)
),
sizes AS (
  SELECT cohort_month, COUNT(*) AS cohort_size FROM first_order
  WHERE cohort_month >= DATE_TRUNC(start_date, MONTH)
  GROUP BY cohort_month
)
-- Full grid: every cohort x every offset that fits inside the window, so a month in which
-- nobody came back shows as 0% instead of a missing row. Offsets beyond the window are
-- not generated (they are unobservable, not zero).
SELECT
  s.cohort_month,
  s.cohort_size,
  k AS month_offset,
  COUNTIF(a.customer_unique_id IS NOT NULL)          AS retained_customers,
  ROUND(100 * COUNTIF(a.customer_unique_id IS NOT NULL) / s.cohort_size, 2) AS retention_pct
FROM sizes AS s,
     UNNEST(GENERATE_ARRAY(0, DATE_DIFF(DATE_TRUNC(end_date, MONTH), s.cohort_month, MONTH))) AS k
LEFT JOIN activity AS a
  ON a.cohort_month = s.cohort_month AND a.month_offset = k
GROUP BY s.cohort_month, s.cohort_size, k
ORDER BY s.cohort_month, k;

SELECT * FROM shoppulse.mart_cohort_retention ORDER BY cohort_month, month_offset;


-- Q3. RFM. Frequency is almost always 1 in Olist, so quintiles on frequency would be
--     meaningless: F is a rule (1 / 2 / 3+). R and M use quintiles (5 = best).
--     Snapshot date = day after the last order in the window.
CREATE OR REPLACE TABLE shoppulse.mart_rfm AS
WITH snapshot AS (SELECT DATE_ADD(MAX(purchase_date), INTERVAL 1 DAY) AS d FROM valid_orders),
cust AS (
  SELECT
    o.customer_unique_id,
    DATE_DIFF((SELECT d FROM snapshot), MAX(o.purchase_date), DAY) AS recency_days,
    COUNT(*)                                                       AS frequency,
    COALESCE(SUM(o.item_value), 0)                                 AS monetary_brl
  FROM valid_orders AS o
  GROUP BY o.customer_unique_id
),
-- Tie-break note: NTILE splits ties by customer_unique_id (arbitrary but deterministic), so two customers with
-- identical recency or spend can land in neighbouring quintiles. Segment sizes are reproducible but are partly a
-- product of this tie-break, which matters most for recency (whole days) and for repeated spend values.
scored AS (
  SELECT *,
    6 - NTILE(5) OVER (ORDER BY recency_days ASC, customer_unique_id)  AS r_score,   -- low recency_days = recent = 5
    LEAST(frequency, 3)                                                AS f_score,
    NTILE(5) OVER (ORDER BY monetary_brl ASC, customer_unique_id)      AS m_score
  FROM cust
)
SELECT *,
  CASE
    WHEN f_score >= 2 AND r_score >= 4 THEN 'Active repeat buyers'
    WHEN f_score >= 2                  THEN 'Lapsing repeat buyers'
    WHEN r_score >= 4 AND m_score >= 4 THEN 'Recent high spenders'
    WHEN r_score >= 4                  THEN 'New customers'
    WHEN r_score <= 2 AND m_score >= 4 THEN 'Lost high spenders'
    WHEN r_score <= 2                  THEN 'Lost one-timers'
    ELSE                                    'One-time, cooling'
  END AS segment
FROM scored;

SELECT
  segment,
  COUNT(*)                                              AS customers,
  ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)      AS pct_customers,
  ROUND(SUM(monetary_brl), 0)                           AS revenue_brl,
  ROUND(100 * SUM(monetary_brl) / SUM(SUM(monetary_brl)) OVER (), 2) AS pct_revenue,
  ROUND(AVG(monetary_brl), 2)                           AS avg_spend_brl,
  ROUND(AVG(recency_days), 0)                           AS avg_recency_days
FROM shoppulse.mart_rfm
GROUP BY segment
ORDER BY revenue_brl DESC;
