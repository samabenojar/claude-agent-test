select customer_id, day, count(*) as rows_per_key
from {{ ref('fct_transactions') }}
group by customer_id, day
having count(*) > 1
