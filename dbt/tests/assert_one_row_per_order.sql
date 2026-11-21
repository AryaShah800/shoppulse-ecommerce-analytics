-- Joins to items, payments and reviews must not fan out the order grain.
select 1 as mismatch
where (select count(*) from {{ ref('stg_orders') }}) != (select count(*) from {{ ref('fct_orders') }})
