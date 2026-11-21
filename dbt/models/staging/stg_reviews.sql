-- Some orders have more than one review row. Keep ONE per order: the most recent.
select
  review_id,
  order_id,
  try_cast(review_score as integer)           as review_score,
  try_cast(review_creation_date as timestamp) as review_created_at
from {{ ref('raw_reviews') }}
qualify row_number() over (
  partition by order_id
  order by try_cast(review_creation_date as timestamp) desc,
           try_cast(review_answer_timestamp as timestamp) desc,
           review_id) = 1
