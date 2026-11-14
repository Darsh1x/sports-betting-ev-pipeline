select
    fetched_at,
    event_id,
    market_key,
    sum(consensus_fair_prob) as total_consensus_prob
from {{ ref('int_consensus_fair_prob') }}
group by 1, 2, 3
having abs(sum(consensus_fair_prob) - 1) > 0.0001
