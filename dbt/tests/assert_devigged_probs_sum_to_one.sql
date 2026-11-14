select
    fetched_at,
    event_id,
    bookmaker_key,
    market_key,
    sum(fair_prob) as total_fair_prob
from {{ ref('int_odds_devigged') }}
group by 1, 2, 3, 4
having abs(sum(fair_prob) - 1) > 0.0001
