-- =====================================================================
-- 02_fulfilment_funnel.sql  |  Order fulfilment funnel (Day 2)
-- Olist has no web-session data, so the funnel is the order pipeline:
--   Placed -> Approved -> Handed to carrier -> Delivered
--
-- Analysis window: full months only. Orders placed near the end of the
-- data had not been delivered yet when the snapshot was taken, which
-- would make the last months look like a collapsing funnel.
-- Check the window against check 6 in 01_data_checks and adjust.
--
-- Run the whole file as one script. It returns 3 result sets
-- (open each one under "Execution details / Results") and builds
-- shoppulse.mart_funnel_monthly for Power BI.
-- =====================================================================

DECLARE start_date DATE DEFAULT DATE '2017-01-01';
DECLARE end_date   DATE DEFAULT DATE '2018-08-31';


-- ---------------------------------------------------------------------
-- Q1. Overall funnel: orders reaching each stage, % of placed, step conversion
--     -> save as results/02a_funnel_overall.csv
-- ---------------------------------------------------------------------
WITH base AS (
  SELECT * FROM shoppulse.fct_orders
  WHERE DATE(purchased_at) BETWEEN start_date AND end_date
),
stages AS (
  SELECT 1 AS step, 'Placed' AS stage, COUNT(*) AS orders FROM base
  UNION ALL SELECT 2, 'Approved',          COUNTIF(reached_approved)  FROM base
  UNION ALL SELECT 3, 'Handed to carrier', COUNTIF(reached_carrier)   FROM base
  UNION ALL SELECT 4, 'Delivered',         COUNTIF(reached_delivered) FROM base
)
SELECT
  step,
  stage,
  orders,
  ROUND(100 * orders / FIRST_VALUE(orders) OVER (ORDER BY step), 2)         AS pct_of_placed,
  ROUND(100 * SAFE_DIVIDE(orders, LAG(orders) OVER (ORDER BY step)), 2)     AS pct_of_previous_step,
  LAG(orders) OVER (ORDER BY step) - orders                                 AS lost_at_this_step
FROM stages
ORDER BY step;


-- ---------------------------------------------------------------------
-- Q2. Time spent in each stage (delivered orders): median and p90
--     Median = typical order; p90 = the slow tail customers complain about.
--     -> save as results/02b_stage_durations.csv
-- ---------------------------------------------------------------------
WITH d AS (
  SELECT * FROM shoppulse.fct_orders
  WHERE DATE(purchased_at) BETWEEN start_date AND end_date
    AND reached_delivered
)
SELECT 1 AS step, 'Purchase -> approval (hours)' AS stage,
       ROUND(APPROX_QUANTILES(hrs_purchase_to_approval, 100 IGNORE NULLS)[OFFSET(50)], 1) AS median,
       ROUND(APPROX_QUANTILES(hrs_purchase_to_approval, 100 IGNORE NULLS)[OFFSET(90)], 1) AS p90
FROM d
UNION ALL
SELECT 2, 'Approval -> carrier (days)',
       ROUND(APPROX_QUANTILES(hrs_approval_to_carrier, 100 IGNORE NULLS)[OFFSET(50)] / 24, 1),
       ROUND(APPROX_QUANTILES(hrs_approval_to_carrier, 100 IGNORE NULLS)[OFFSET(90)] / 24, 1)
FROM d
UNION ALL
SELECT 3, 'Carrier -> customer (days)',
       ROUND(APPROX_QUANTILES(hrs_carrier_to_customer, 100 IGNORE NULLS)[OFFSET(50)] / 24, 1),
       ROUND(APPROX_QUANTILES(hrs_carrier_to_customer, 100 IGNORE NULLS)[OFFSET(90)] / 24, 1)
FROM d
UNION ALL
SELECT 4, 'Purchase -> delivery, total (days)',
       ROUND(APPROX_QUANTILES(hrs_purchase_to_delivery, 100 IGNORE NULLS)[OFFSET(50)] / 24, 1),
       ROUND(APPROX_QUANTILES(hrs_purchase_to_delivery, 100 IGNORE NULLS)[OFFSET(90)] / 24, 1)
FROM d
ORDER BY step;


-- ---------------------------------------------------------------------
-- Q3. Monthly funnel + on-time rate (mart table for the Power BI trend page)
--     -> also export the table as results/02c_funnel_monthly.csv
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE shoppulse.mart_funnel_monthly AS
SELECT
  purchase_month,
  COUNT(*)                                                         AS placed,
  COUNTIF(reached_approved)                                        AS approved,
  COUNTIF(reached_carrier)                                         AS handed_to_carrier,
  COUNTIF(reached_delivered)                                       AS delivered,
  ROUND(100 * COUNTIF(reached_delivered) / COUNT(*), 2)            AS delivered_pct_of_placed,
  COUNTIF(order_status = 'canceled')                               AS canceled,
  ROUND(100 * COUNTIF(is_late = FALSE)
        / NULLIF(COUNTIF(is_late IS NOT NULL), 0), 2)              AS on_time_pct,
  ROUND(AVG(IF(reached_delivered, hrs_purchase_to_delivery, NULL)) / 24, 1) AS avg_delivery_days,
  ROUND(SUM(IF(reached_delivered, item_value, 0)), 2)              AS delivered_item_value_brl
FROM shoppulse.fct_orders
WHERE DATE(purchased_at) BETWEEN start_date AND end_date
GROUP BY purchase_month
ORDER BY purchase_month;

SELECT * FROM shoppulse.mart_funnel_monthly ORDER BY purchase_month;
