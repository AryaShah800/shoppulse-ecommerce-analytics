select
  customer_id,            -- one per ORDER
  customer_unique_id,     -- one per PERSON: use this for repeat and cohort work
  customer_state as state
from {{ ref('raw_customers') }}
