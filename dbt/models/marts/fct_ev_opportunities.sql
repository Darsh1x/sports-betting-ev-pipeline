with priced as (
    select
        d.fetched_at,
        d.event_id,
        d.sport_key,
        d.commence_time,
        d.home_team,
        d.away_team,
        d.bookmaker_key,
        d.bookmaker_title,
        d.market_key,
        d.outcome_name,
        d.price_american,
        d.decimal_odds,
        d.implied_prob,
        c.consensus_fair_prob,
        c.book_count,
        c.consensus_fair_prob * d.decimal_odds - 1 as expected_value
    from {{ ref('int_odds_devigged') }} as d
    inner join {{ ref('int_consensus_fair_prob') }} as c
        on d.fetched_at = c.fetched_at
        and d.event_id = c.event_id
        and d.market_key = c.market_key
        and d.outcome_name = c.outcome_name
    where d.commence_time > d.fetched_at
        and c.book_count >= {{ var('min_books') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by fetched_at, event_id, market_key, outcome_name
            order by decimal_odds desc
        ) as price_rank,
        fetched_at = max(fetched_at) over (partition by sport_key) as is_latest_snapshot
    from priced
)

select
    fetched_at,
    event_id,
    sport_key,
    commence_time,
    home_team,
    away_team,
    bookmaker_key,
    bookmaker_title,
    market_key,
    outcome_name,
    price_american,
    decimal_odds,
    implied_prob,
    consensus_fair_prob,
    consensus_fair_prob - implied_prob as edge,
    expected_value,
    book_count,
    price_rank = 1 as is_best_price,
    is_latest_snapshot
from ranked
where expected_value >= {{ var('ev_threshold') }}
