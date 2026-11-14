select
    fetched_at,
    event_id,
    sport_key,
    commence_time,
    home_team,
    away_team,
    market_key,
    outcome_name,
    avg(fair_prob) as consensus_fair_prob,
    count(distinct bookmaker_key) as book_count
from {{ ref('int_odds_devigged') }}
group by
    fetched_at,
    event_id,
    sport_key,
    commence_time,
    home_team,
    away_team,
    market_key,
    outcome_name
