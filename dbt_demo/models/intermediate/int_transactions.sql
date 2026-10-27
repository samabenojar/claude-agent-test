select event_id, customer_id, event_ts, amount
from {{ ref('stg_events') }}
where 0 < amount
