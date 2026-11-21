-- Late vs on-time delivered orders and the share with a 1-2 star review (as in sql/04, review part).
select
  is_late,
  count(*) as orders,
  avg(case when review_score <= 2 then 1.0 else 0.0 end) as low_review_rate
from {{ ref('fct_orders') }}
where is_late is not null and review_score is not null
group by is_late
