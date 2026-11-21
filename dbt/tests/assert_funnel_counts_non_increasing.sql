select a.step
from {{ ref('mart_fulfilment_funnel') }} a
join {{ ref('mart_fulfilment_funnel') }} b on b.step = a.step + 1
where b.orders > a.orders
