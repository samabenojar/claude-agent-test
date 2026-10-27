select
    customer_id,
    date_trunc('day', event_ts) as day,
    sum(amount) as total_amount,
    count(*) as txn_count
from {{ ref('int_transactions') }}
group by customer_id, date_trunc('day', event_ts)
