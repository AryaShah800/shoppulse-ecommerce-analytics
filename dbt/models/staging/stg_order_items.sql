select
  order_id,
  try_cast(order_item_id as integer)        as order_item_id,
  product_id,
  seller_id,
  try_cast(price as decimal(12, 2))         as price,          -- BRL
  try_cast(freight_value as decimal(12, 2)) as freight_value   -- BRL
from {{ ref('raw_order_items') }}
