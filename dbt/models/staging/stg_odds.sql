with snapshots as (
    select
        payload:fetched_at::timestamp_tz as fetched_at,
        payload:events as events,
        source_file
    from {{ source('raw', 'odds_raw') }}
),

events as (
    select
        s.fetched_at,
        s.source_file,
        e.value as event
    from snapshots as s,
        lateral flatten(input => s.events) as e
),

bookmakers as (
    select
        fetched_at,
        source_file,
        event,
        b.value as bookmaker
    from events,
        lateral flatten(input => event:bookmakers) as b
),

markets as (
    select
        fetched_at,
        source_file,
        event,
        bookmaker,
        m.value as market
    from bookmakers,
        lateral flatten(input => bookmaker:markets) as m
),

outcomes as (
    select
        fetched_at,
        source_file,
        event,
        bookmaker,
        market,
        o.value as outcome
    from markets,
        lateral flatten(input => market:outcomes) as o
)

select
    fetched_at,
    source_file,
    event:id::string as event_id,
    event:sport_key::string as sport_key,
    event:commence_time::timestamp_tz as commence_time,
    event:home_team::string as home_team,
    event:away_team::string as away_team,
    bookmaker:key::string as bookmaker_key,
    bookmaker:title::string as bookmaker_title,
    market:key::string as market_key,
    market:last_update::timestamp_tz as market_last_update,
    outcome:name::string as outcome_name,
    outcome:price::int as price_american
from outcomes
