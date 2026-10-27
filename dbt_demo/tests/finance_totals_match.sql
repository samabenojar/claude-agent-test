-- Aggregation must preserve the total of all eligible transactions.
with expected as (
    select coalesce(sum(amount), 0) as total
    from {{ ref('int_transactions') }}
), actual as (
    select coalesce(sum(daily_total), 0) as total
    from {{ ref('rpt_finance') }}
)
select expected.total as expected_total, actual.total as actual_total
from expected cross join actual
where expected.total <> actual.total
