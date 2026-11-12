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
-- Repeat outcome = placed another valid order AFTER the first order was delivered, within 180 days
-- of that delivery. Measuring from delivery matters: an order placed before the first one arrived
-- cannot be a reaction to the delivery experience, and a late delivery would otherwise lose days of
-- the window while the parcel was still in transit.
-- Right-censoring guard: only first orders delivered on/before cohort_cutoff (end_date - follow-up),
-- so every person had a full 180 days after delivery to come back inside the data.
-- Export both tables to results/ (BigQuery: Save results -> CSV), or the Python script reads them directly.
-- =====================================================================

DECLARE start_date DATE DEFAULT DATE '2017-01-01';
DECLARE end_date   DATE DEFAULT DATE '2018-08-31';
DECLARE follow_up_days INT64 DEFAULT 180;
DECLARE cohort_cutoff DATE DEFAULT DATE_SUB(end_date, INTERVAL follow_up_days DAY);   -- = 2018-03-04


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
cohort AS (          -- one row per person: their first valid order, if it was delivered
  SELECT *
  FROM valid
  WHERE TRUE
  QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_unique_id ORDER BY purchased_at, order_id) = 1
),
eligible AS (
  SELECT *
  FROM cohort
  WHERE reached_delivered
    AND is_late IS NOT NULL
    AND delivered_at IS NOT NULL
    AND DATE(purchased_at) BETWEEN start_date AND end_date
    AND DATE(delivered_at) <= cohort_cutoff
),
repeat_order AS (    -- earliest valid order placed after the first one arrived, within the window
  SELECT e.customer_unique_id, v.order_id AS repeat_order_id, v.item_value AS repeat_item_value
  FROM eligible AS e
  JOIN valid AS v
    ON v.customer_unique_id = e.customer_unique_id
   AND v.order_id != e.order_id
   AND v.purchased_at > e.delivered_at
   AND DATETIME_DIFF(v.purchased_at, e.delivered_at, DAY) <= follow_up_days
  WHERE TRUE
  QUALIFY ROW_NUMBER() OVER (PARTITION BY e.customer_unique_id ORDER BY v.purchased_at, v.order_id) = 1
)
SELECT
  e.customer_unique_id,
  e.order_id,
  e.customer_state,
  e.purchased_at,
  e.delivered_at,
  e.is_late,
  e.days_vs_estimate,
  e.review_score,
  e.item_value                                 AS first_item_value,
  r.repeat_item_value                          AS repeat_item_value,
  r.repeat_order_id IS NOT NULL                AS repeat_180d
FROM eligible AS e
LEFT JOIN repeat_order AS r USING (customer_unique_id);


-- Sanity checks (run and eyeball; these also go in the README "Data quality" section)
SELECT 'reviews table rows' AS check_name, CAST(COUNT(*) AS STRING) AS value FROM shoppulse.mart_delivery_reviews
UNION ALL SELECT 'repeat table rows (people)', CAST(COUNT(*) AS STRING) FROM shoppulse.mart_delivery_repeat
UNION ALL SELECT 'repeat table: duplicate people (must be 0)',
  CAST(COUNT(*) - COUNT(DISTINCT customer_unique_id) AS STRING) FROM shoppulse.mart_delivery_repeat
UNION ALL SELECT 'repeat table: late share (%)',
  CAST(ROUND(100 * COUNTIF(is_late) / COUNT(*), 2) AS STRING) FROM shoppulse.mart_delivery_repeat
UNION ALL SELECT 'repeat table: repeat share (%)',
  CAST(ROUND(100 * COUNTIF(repeat_180d) / COUNT(*), 2) AS STRING) FROM shoppulse.mart_delivery_repeat;
