with priced as (
    select
        *,
        case
            when price_american < 0 then -price_american / (-price_american + 100.0)
            else 100.0 / (price_american + 100.0)
        end as implied_prob,
        case
            when price_american < 0 then 1 + 100.0 / -price_american
            else 1 + price_american / 100.0
        end as decimal_odds
    from {{ ref('stg_odds') }}
),

with_book_total as (
    select
        *,
        sum(implied_prob) over (
            partition by fetched_at, event_id, bookmaker_key, market_key
        ) as book_implied_total
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
    book_implied_total - 1 as vig,
    implied_prob / book_implied_total as fair_prob
from with_book_total
