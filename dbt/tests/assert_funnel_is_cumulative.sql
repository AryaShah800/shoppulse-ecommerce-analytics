-- Each funnel stage must be a subset of the previous one.
select * from {{ ref('fct_orders') }}
where (reached_delivered and not reached_carrier) or (reached_carrier and not reached_approved)
