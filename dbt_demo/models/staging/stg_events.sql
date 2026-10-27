select event_id, customer_id, event_ts, amount
from {{ source('staging', 'events') }}
