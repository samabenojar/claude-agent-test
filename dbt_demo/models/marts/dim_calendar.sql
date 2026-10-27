select dateadd('day', row_number() over (order by seq4()) - 1,
               '2026-01-01'::date)::date as day
from table(generator(rowcount => 365))
