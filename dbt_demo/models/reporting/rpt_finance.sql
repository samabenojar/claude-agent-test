select day, sum(total_amount) as daily_total
from {{ ref('fct_transactions') }}
group by day
