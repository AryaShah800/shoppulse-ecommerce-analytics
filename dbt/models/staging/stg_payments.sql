select
  order_id,
  try_cast(payment_sequential as integer)   as payment_sequential,
  payment_type,
  try_cast(payment_value as decimal(12, 2)) as payment_value   -- BRL
from {{ ref('raw_payments') }}
