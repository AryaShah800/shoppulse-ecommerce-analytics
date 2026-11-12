-- =====================================================================
-- 04_delivery_test_datasets.sql  |  Inputs for the late-delivery tests (Days 4-6)
--
-- Two analysis tables, one per question:
--   mart_delivery_reviews : every delivered order with a review (order-level)   -> review-score test
--   mart_delivery_repeat  : each person's FIRST delivered order (person-level)   -> repeat-purchase test
--
-- Why two tables: a person with 3 orders must not count 3 times in a repeat-purchase test
-- (observations would not be independent). The repeat test uses one row per person.
--
-- Repeat outcome = placed another valid order within 180 days of the first purchase.
-- Right-censoring guard: only first orders placed on/before cutoff, so every person had a
-- full 180 days to come back inside the data. Without it, recent customers look like they never return.
-- Export both tables to results/ (BigQuery: Save results -> CSV), or the Python script reads them directly.
-- =====================================================================

DECLARE start_date DATE DEFAULT DATE '2017-01-01';
DECLARE end_date   DATE DEFAULT DATE '2018-08-31';
DECLARE follow_up_days INT64 DEFAULT 180;
DECLARE cohort_cutoff DATE DEFAULT DATE_SUB(DATE '2018-08-31', INTERVAL 180 DAY);   -- = 2018-03-04


CREATE OR REPLACE TABLE shoppulse.mart_delivery_reviews AS
SELECT
  order_id,
  customer_state,
  purchased_at,
  is_late,
  days_vs_estimate,
  review_score,
  review_score <= 2 AS is_low_review,
  item_value
FROM shoppulse.fct_orders
WHERE reached_delivered
  AND is_late IS NOT NULL
  AND review_score IS NOT NULL
  AND DATE(purchased_at) BETWEEN start_date AND end_date;


CREATE OR REPLACE TABLE shoppulse.mart_delivery_repeat AS
WITH valid AS (
  SELECT *
  FROM shoppulse.fct_orders
  WHERE order_status NOT IN ('canceled', 'unavailable')
    AND purchased_at IS NOT NULL
),
seq AS (
  SELECT *,
    ROW_NUMBER() OVER w                AS person_order_seq,
    LEAD(purchased_at) OVER w          AS next_purchased_at,
    LEAD(item_value)   OVER w          AS next_item_value
  FROM valid
  WINDOW w AS (PARTITION BY customer_unique_id ORDER BY purchased_at, order_id)
)
SELECT
  customer_unique_id,
  order_id,
  customer_state,
  purchased_at,
  is_late,
  days_vs_estimate,
  review_score,
  item_value                                   AS first_item_value,
  next_item_value                              AS repeat_item_value,
  next_purchased_at IS NOT NULL
    AND DATETIME_DIFF(next_purchased_at, purchased_at, DAY) <= follow_up_days AS repeat_180d
FROM seq
WHERE person_order_seq = 1
  AND reached_delivered
  AND is_late IS NOT NULL
  AND DATE(purchased_at) BETWEEN start_date AND cohort_cutoff;


-- Sanity checks (run and eyeball; these also go in the README "Data quality" section)
SELECT 'reviews table rows' AS check_name, CAST(COUNT(*) AS STRING) AS value FROM shoppulse.mart_delivery_reviews
UNION ALL SELECT 'repeat table rows (people)', CAST(COUNT(*) AS STRING) FROM shoppulse.mart_delivery_repeat
UNION ALL SELECT 'repeat table: duplicate people (must be 0)',
  CAST(COUNT(*) - COUNT(DISTINCT customer_unique_id) AS STRING) FROM shoppulse.mart_delivery_repeat
UNION ALL SELECT 'repeat table: late share (%)',
  CAST(ROUND(100 * COUNTIF(is_late) / COUNT(*), 2) AS STRING) FROM shoppulse.mart_delivery_repeat
UNION ALL SELECT 'repeat table: repeat share (%)',
  CAST(ROUND(100 * COUNTIF(repeat_180d) / COUNT(*), 2) AS STRING) FROM shoppulse.mart_delivery_repeat;
