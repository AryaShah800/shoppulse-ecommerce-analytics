-- =====================================================================
-- 00_staging.sql  |  Typed, cleaned views over the raw STRING tables
-- Run as one script in the BigQuery console (default project = yours).
-- Sandbox-safe: only CREATE OR REPLACE VIEW / TABLE (no INSERT/UPDATE).
-- Olist timestamps carry no time zone, so they are typed as DATETIME.
-- =====================================================================

CREATE OR REPLACE VIEW shoppulse.stg_customers AS
SELECT
  customer_id,                          -- one per ORDER (changes every purchase)
  customer_unique_id,                   -- one per PERSON  -> use for repeat/cohort work
  customer_zip_code_prefix AS zip_prefix,
  customer_city            AS city,
  customer_state           AS state
FROM olist_raw.customers;


CREATE OR REPLACE VIEW shoppulse.stg_orders AS
SELECT
  order_id,
  customer_id,
  order_status,
  SAFE_CAST(order_purchase_timestamp      AS DATETIME) AS purchased_at,
  SAFE_CAST(order_approved_at             AS DATETIME) AS approved_at,
  SAFE_CAST(order_delivered_carrier_date  AS DATETIME) AS shipped_at,
  SAFE_CAST(order_delivered_customer_date AS DATETIME) AS delivered_at,
  SAFE_CAST(order_estimated_delivery_date AS DATETIME) AS estimated_delivery_at
FROM olist_raw.orders;


CREATE OR REPLACE VIEW shoppulse.stg_order_items AS
SELECT
  order_id,
  SAFE_CAST(order_item_id AS INT64)   AS order_item_id,
  product_id,
  seller_id,
  SAFE_CAST(shipping_limit_date AS DATETIME) AS shipping_limit_at,
  SAFE_CAST(price         AS NUMERIC) AS price,           -- BRL (R$)
  SAFE_CAST(freight_value AS NUMERIC) AS freight_value    -- BRL (R$)
FROM olist_raw.order_items;


CREATE OR REPLACE VIEW shoppulse.stg_payments AS
SELECT
  order_id,
  SAFE_CAST(payment_sequential   AS INT64)   AS payment_sequential,
  payment_type,
  SAFE_CAST(payment_installments AS INT64)   AS payment_installments,
  SAFE_CAST(payment_value        AS NUMERIC) AS payment_value   -- BRL (R$)
FROM olist_raw.payments;


-- Some orders have more than one review row. Keep ONE per order: the most recent.
CREATE OR REPLACE VIEW shoppulse.stg_reviews AS
SELECT
  review_id,
  order_id,
  SAFE_CAST(review_score AS INT64)              AS review_score,
  SAFE_CAST(review_creation_date    AS DATETIME) AS review_created_at,
  SAFE_CAST(review_answer_timestamp AS DATETIME) AS review_answered_at
FROM olist_raw.reviews
WHERE TRUE
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY order_id
  ORDER BY SAFE_CAST(review_creation_date AS DATETIME) DESC,
           SAFE_CAST(review_answer_timestamp AS DATETIME) DESC,
           review_id
) = 1;


CREATE OR REPLACE VIEW shoppulse.stg_products AS
SELECT
  p.product_id,
  COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
  SAFE_CAST(p.product_weight_g AS INT64) AS weight_g
FROM olist_raw.products AS p
LEFT JOIN olist_raw.category_translation AS t
  ON p.product_category_name = t.product_category_name;


-- =====================================================================
-- fct_orders: ONE ROW PER ORDER. Every later analysis (funnel, cohorts,
-- RFM, delivery-impact test, Power BI) reads from this table.
-- =====================================================================
CREATE OR REPLACE TABLE shoppulse.fct_orders AS
WITH items AS (
  SELECT order_id,
         COUNT(*)           AS n_items,
         SUM(price)         AS item_value,
         SUM(freight_value) AS freight_value
  FROM shoppulse.stg_order_items
  GROUP BY order_id
),
pay AS (
  SELECT order_id, SUM(payment_value) AS payment_value
  FROM shoppulse.stg_payments
  GROUP BY order_id
),
joined AS (
  SELECT
    o.*,
    c.customer_unique_id,
    c.state AS customer_state,
    COALESCE(i.n_items, 0) AS n_items,
    i.item_value,
    i.freight_value,
    p.payment_value,
    r.review_score
  FROM shoppulse.stg_orders    AS o
  JOIN shoppulse.stg_customers AS c USING (customer_id)
  LEFT JOIN items              AS i USING (order_id)
  LEFT JOIN pay                AS p USING (order_id)
  LEFT JOIN shoppulse.stg_reviews AS r USING (order_id)
)
SELECT
  order_id,
  customer_id,
  customer_unique_id,
  customer_state,
  order_status,
  purchased_at,
  approved_at,
  shipped_at,
  delivered_at,
  estimated_delivery_at,
  DATE_TRUNC(DATE(purchased_at), MONTH) AS purchase_month,

  -- 1 = customer's first VALID order, 2 = their second, ...  (by PERSON, not by customer_id).
  -- Valid = not canceled/unavailable and has a purchase time, the same rule as 03 and 04.
  -- NULL for invalid orders, so a canceled first attempt does not make a later real purchase "order 2".
  IF(order_status NOT IN ('canceled', 'unavailable') AND purchased_at IS NOT NULL,
     ROW_NUMBER() OVER (
       PARTITION BY customer_unique_id,
                    (order_status NOT IN ('canceled', 'unavailable') AND purchased_at IS NOT NULL)
       ORDER BY purchased_at, order_id),
     NULL) AS customer_order_seq,

  n_items, item_value, freight_value, payment_value, review_score,

  -- Funnel flags. Built cumulatively so each stage is a subset of the one before it
  -- (a few orders skip a timestamp but still reach a later stage).
  (approved_at IS NOT NULL OR shipped_at IS NOT NULL OR delivered_at IS NOT NULL
     OR order_status = 'delivered')                                         AS reached_approved,
  (shipped_at IS NOT NULL OR delivered_at IS NOT NULL
     OR order_status = 'delivered')                                         AS reached_carrier,
  (order_status = 'delivered')                                              AS reached_delivered,

  -- Stage durations in hours. Negative values are timestamp errors -> NULL (counted in 01_data_checks).
  IF(DATETIME_DIFF(approved_at,  purchased_at, MINUTE) < 0, NULL,
     DATETIME_DIFF(approved_at,  purchased_at, MINUTE) / 60.0)              AS hrs_purchase_to_approval,
  IF(DATETIME_DIFF(shipped_at,   approved_at,  MINUTE) < 0, NULL,
     DATETIME_DIFF(shipped_at,   approved_at,  MINUTE) / 60.0)              AS hrs_approval_to_carrier,
  IF(DATETIME_DIFF(delivered_at, shipped_at,   MINUTE) < 0, NULL,
     DATETIME_DIFF(delivered_at, shipped_at,   MINUTE) / 60.0)              AS hrs_carrier_to_customer,
  IF(DATETIME_DIFF(delivered_at, purchased_at, MINUTE) < 0, NULL,
     DATETIME_DIFF(delivered_at, purchased_at, MINUTE) / 60.0)              AS hrs_purchase_to_delivery,

  -- Late = delivered on a LATER CALENDAR DAY than promised. The estimate is stored as a date at
  -- 00:00:00, so comparing full datetimes would wrongly flag every same-day delivery as late.
  CASE
    WHEN order_status != 'delivered' OR delivered_at IS NULL OR estimated_delivery_at IS NULL THEN NULL
    ELSE DATE(delivered_at) > DATE(estimated_delivery_at)
  END AS is_late,
  CASE
    WHEN order_status != 'delivered' OR delivered_at IS NULL OR estimated_delivery_at IS NULL THEN NULL
    ELSE DATE_DIFF(DATE(delivered_at), DATE(estimated_delivery_at), DAY)
  END AS days_vs_estimate          -- positive = days late, negative = days early
FROM joined;
