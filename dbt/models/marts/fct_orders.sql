-- One row per order. Same business rules as sql/00_staging.sql (BigQuery), ported to DuckDB.
with items as (
  select order_id, count(*) as n_items, sum(price) as item_value, sum(freight_value) as freight_value
  from {{ ref('stg_order_items') }} group by order_id
),
pay as (
  select order_id, sum(payment_value) as payment_value from {{ ref('stg_payments') }} group by order_id
),
joined as (
  select o.*, c.customer_unique_id, c.state as customer_state,
         coalesce(i.n_items, 0) as n_items, i.item_value, i.freight_value, p.payment_value, r.review_score
  from {{ ref('stg_orders') }} o
  join {{ ref('stg_customers') }} c using (customer_id)
  left join items i using (order_id)
  left join pay p using (order_id)
  left join {{ ref('stg_reviews') }} r using (order_id)
)
select
  order_id, customer_id, customer_unique_id, customer_state, order_status,
  purchased_at, approved_at, shipped_at, delivered_at, estimated_delivery_at,
  cast(date_trunc('month', purchased_at) as date) as purchase_month,
  n_items, item_value, freight_value, payment_value, review_score,
  -- Funnel flags are cumulative: each stage is a subset of the one before it.
  (approved_at is not null or shipped_at is not null or delivered_at is not null or order_status = 'delivered') as reached_approved,
  (shipped_at is not null or delivered_at is not null or order_status = 'delivered') as reached_carrier,
  (order_status = 'delivered') as reached_delivered,
  -- Late = delivered on a LATER CALENDAR DAY than promised (the estimate is stored at 00:00:00).
  case when order_status != 'delivered' or delivered_at is null or estimated_delivery_at is null then null
       else cast(delivered_at as date) > cast(estimated_delivery_at as date) end as is_late,
  case when order_status != 'delivered' or delivered_at is null or estimated_delivery_at is null then null
       else date_diff('day', cast(estimated_delivery_at as date), cast(delivered_at as date)) end as days_vs_estimate
from joined
