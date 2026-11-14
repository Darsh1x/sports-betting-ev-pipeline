select *
from {{ ref('fct_ev_opportunities') }}
where commence_time <= fetched_at
