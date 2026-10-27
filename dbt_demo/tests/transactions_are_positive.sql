select event_id, amount
from {{ ref('int_transactions') }}
where amount is null or amount <= 0
