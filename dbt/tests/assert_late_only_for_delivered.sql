-- is_late and days_vs_estimate exist only for delivered orders, and the two must agree.
select * from {{ ref('fct_orders') }}
where (order_status != 'delivered' and (is_late is not null or days_vs_estimate is not null))
   or (is_late is not null and is_late != (days_vs_estimate > 0))
