-- Order pipeline funnel for orders placed in the analysis window (Jan 2017 to Aug 2018), as in sql/02.
with w as (
  select * from {{ ref('fct_orders') }}
  where purchased_at >= timestamp '2017-01-01' and purchased_at < timestamp '2018-09-01'
)
select 1 as step, 'Placed' as stage, count(*) as orders from w
union all select 2, 'Approved', count(*) from w where reached_approved
union all select 3, 'Handed to carrier', count(*) from w where reached_carrier
union all select 4, 'Delivered', count(*) from w where reached_delivered
