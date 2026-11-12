-- =====================================================================
-- 01_data_checks.sql  |  Data-quality report (one result table)
-- Run after 00_staging.sql. Save the output as results/01_data_checks.csv
-- These numbers go into the README's "Data" and "Data quality" sections.
-- =====================================================================

WITH raw_reviews AS (
  SELECT order_id, COUNT(*) AS n FROM olist_raw.reviews GROUP BY order_id
),
order_items_check AS (
  SELECT o.order_id, o.order_status
  FROM shoppulse.stg_orders AS o
  LEFT JOIN (SELECT DISTINCT order_id FROM shoppulse.stg_order_items) AS i USING (order_id)
  WHERE i.order_id IS NULL
),
f AS (SELECT * FROM shoppulse.fct_orders)

SELECT 1 AS id, 'Orders (rows)' AS check_name,
       CAST(COUNT(*) AS STRING) AS value, 'Expect 99,441' AS note
FROM shoppulse.stg_orders

UNION ALL SELECT 2, 'Duplicate order_id',
       CAST(COUNT(*) - COUNT(DISTINCT order_id) AS STRING), 'Must be 0'
FROM shoppulse.stg_orders

UNION ALL SELECT 3, 'Distinct customer_id',
       CAST(COUNT(DISTINCT customer_id) AS STRING), 'One per order'
FROM shoppulse.stg_customers

UNION ALL SELECT 4, 'Distinct customer_unique_id (real people)',
       CAST(COUNT(DISTINCT customer_unique_id) AS STRING), 'Lower than check 3 -> some people ordered again'
FROM shoppulse.stg_customers

UNION ALL SELECT 5, 'fct_orders rows (join kept every order?)',
       CAST(COUNT(*) AS STRING), 'Must equal check 1'
FROM f

UNION ALL SELECT 6, 'Purchase date range',
       CONCAT(CAST(MIN(DATE(purchased_at)) AS STRING), ' to ', CAST(MAX(DATE(purchased_at)) AS STRING)),
       'Sparse months at both ends -> analysis window in 02'
FROM f

UNION ALL SELECT 7, 'Orders by status',
       STRING_AGG(CONCAT(order_status, '=', CAST(n AS STRING)), ', ' ORDER BY n DESC), 'Funnel input'
FROM (SELECT order_status, COUNT(*) AS n FROM f GROUP BY order_status)

UNION ALL SELECT 8, 'Orders with no items',
       CAST(COUNT(*) AS STRING), 'Mostly unavailable/canceled; excluded from revenue'
FROM order_items_check

UNION ALL SELECT 9, 'Delivered status but no delivered date',
       CAST(COUNTIF(order_status = 'delivered' AND delivered_at IS NULL) AS STRING), 'Excluded from is_late'
FROM f

UNION ALL SELECT 10, 'Negative stage durations (timestamp errors)',
       CAST(COUNTIF(DATETIME_DIFF(approved_at, purchased_at, MINUTE) < 0
                 OR DATETIME_DIFF(shipped_at, approved_at, MINUTE) < 0
                 OR DATETIME_DIFF(delivered_at, shipped_at, MINUTE) < 0) AS STRING),
       'Set to NULL in fct_orders'
FROM f

UNION ALL SELECT 11, 'Orders with >1 review row (raw)',
       CAST(COUNTIF(n > 1) AS STRING), 'Deduplicated in stg_reviews'
FROM raw_reviews

UNION ALL SELECT 12, 'Delivered orders with no review',
       CAST(COUNTIF(order_status = 'delivered' AND review_score IS NULL) AS STRING), 'Excluded from review tests'
FROM f

UNION ALL SELECT 13, 'Payment vs items+freight gap > R$1',
       CAST(COUNTIF(ABS(payment_value - (item_value + freight_value)) > 1) AS STRING),
       'Instalment interest/vouchers; use item_value for revenue'
FROM f
WHERE item_value IS NOT NULL AND payment_value IS NOT NULL

UNION ALL SELECT 14, 'Late share of delivered orders (%)',
       CAST(ROUND(100 * COUNTIF(is_late) / COUNTIF(is_late IS NOT NULL), 2) AS STRING),
       'Headline for Day 4-5'
FROM f

UNION ALL SELECT 15, 'People with 2+ orders (%)',
       CAST(ROUND(100 * COUNTIF(n_orders >= 2) / COUNT(*), 2) AS STRING),
       'Expect very low -> repeat buyers are rare'
FROM (SELECT customer_unique_id, COUNT(*) AS n_orders FROM f GROUP BY customer_unique_id)

ORDER BY id;
