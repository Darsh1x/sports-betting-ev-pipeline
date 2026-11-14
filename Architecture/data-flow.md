# Data flow walkthrough

Follows one odds snapshot through every stage, with numbers. The game and prices below are illustrative, but the math is exactly what the models compute.

See [architecture.md](architecture.md) for the big picture.

## The scenario

At 12:00 UTC on a Sunday morning, Airflow starts a run. The Odds API reports one upcoming game, Chiefs vs Bills, with these moneyline prices from 5 books:

| Book | Chiefs | Bills |
|---|---|---|
| DraftKings | -150 | +130 |
| FanDuel | -145 | +125 |
| BetMGM | -155 | +130 |
| Caesars | -150 | +125 |
| Bovada | -160 | +145 |

## Step 1: fetch (`fetch_odds.py`)

The script calls the API, wraps the response, and writes one file to S3:

```
s3://<bucket>/raw/odds/sport=americanfootball_nfl/dt=2026-11-15/20261115T120000Z.json
```

```json
{
  "fetched_at": "2026-11-15T12:00:00+00:00",
  "sport": "americanfootball_nfl",
  "event_count": 1,
  "events": [ { "id": "abc123", "home_team": "Kansas City Chiefs",
                "bookmakers": [ { "key": "draftkings", "markets": [ ... ] } ] } ]
}
```

One file holds the whole snapshot, nested: events contain bookmakers, which contain markets, which contain outcomes.

## Step 2: load (`load_to_snowflake.py`)

The new file is uploaded to the Snowflake stage and copied in. `RAW.ODDS_RAW` gains **1 row** (one per file), with the entire JSON in the `payload` column:

| payload (VARIANT) | source_file | loaded_at |
|---|---|---|
| `{ "fetched_at": ..., "events": [...] }` | `sport=.../20261115T120000Z.json` | 2026-11-15 12:00:07 |

## Step 3: `stg_odds` (flatten)

`lateral flatten` unpacks each nesting level, so the one row becomes **one row per outcome per book**. Here that is 5 books x 2 outcomes = **10 rows**:

| fetched_at | event_id | bookmaker_key | outcome_name | price_american |
|---|---|---|---|---|
| 12:00 | abc123 | draftkings | Kansas City Chiefs | -150 |
| 12:00 | abc123 | draftkings | Buffalo Bills | 130 |
| 12:00 | abc123 | fanduel | Kansas City Chiefs | -145 |
| ... | ... | ... | ... | ... |

Still 10 rows, now plain typed columns.

## Step 4: `int_odds_devigged` (remove the margin)

For each row, three calculations.

**Implied probability.** Negative odds: `|p| / (|p| + 100)`. Positive odds: `100 / (p + 100)`.

**Vig.** Add up the implied probabilities for one book's market. If a book were fair, they would total 1.00. They total more, and the excess is its margin.

**Fair probability.** Divide each implied probability by that total, so they sum to exactly 1.

Worked for DraftKings:

- Chiefs -150: 150 / 250 = 0.6000
- Bills +130: 100 / 230 = 0.4348
- Total = 1.0348, so vig = 3.48%
- Fair Chiefs = 0.6000 / 1.0348 = 0.5798
- Fair Bills = 0.4348 / 1.0348 = 0.4202

All five books:

| Book | Implied Chiefs | Implied Bills | Total | Vig | Fair Chiefs | Fair Bills |
|---|---|---|---|---|---|---|
| DraftKings | 0.6000 | 0.4348 | 1.0348 | 3.48% | 0.5798 | 0.4202 |
| FanDuel | 0.5918 | 0.4444 | 1.0363 | 3.63% | 0.5711 | 0.4289 |
| BetMGM | 0.6078 | 0.4348 | 1.0426 | 4.26% | 0.5830 | 0.4170 |
| Caesars | 0.6000 | 0.4444 | 1.0444 | 4.44% | 0.5745 | 0.4255 |
| Bovada | 0.6154 | 0.4082 | 1.0235 | 2.35% | 0.6012 | 0.3988 |

The model also converts to decimal odds (`1 + 100/|p|` for negative, `1 + p/100` for positive), which the next steps need. Still 10 rows. This is the test `assert_devigged_probs_sum_to_one` checks.

## Step 5: `int_consensus_fair_prob` (average the market)

Group by event, market, and outcome, and average the fair probabilities across books. The 10 rows collapse to **2 rows**:

| outcome | consensus_fair_prob | book_count |
|---|---|---|
| Kansas City Chiefs | 0.5819 | 5 |
| Buffalo Bills | 0.4181 | 5 |

The market as a whole believes the Chiefs win about 58.2% of the time. `book_count` matters because an average of 2 books is much weaker than an average of 5.

## Step 6: `fct_ev_opportunities` (find the edges)

Join each book's price back to the consensus and compute:

```
expected_value = consensus_fair_prob x decimal_odds - 1
```

Meaning: if the true probability is the consensus, how much do you win on average per $1 staked? Negative means the bet loses money long run.

| Book | Outcome | Decimal odds | EV |
|---|---|---|---|
| DraftKings | Chiefs | 1.667 | -3.0% |
| FanDuel | Chiefs | 1.690 | -1.7% |
| BetMGM | Chiefs | 1.645 | -4.3% |
| Caesars | Chiefs | 1.667 | -3.0% |
| Bovada | Chiefs | 1.625 | -5.4% |
| DraftKings | Bills | 2.300 | -3.8% |
| FanDuel | Bills | 2.250 | -5.9% |
| BetMGM | Bills | 2.300 | -3.8% |
| Caesars | Bills | 2.250 | -5.9% |
| **Bovada** | **Bills** | **2.450** | **+2.4%** |

Filters then apply: the game has not started, `book_count >= 5` (met), and `expected_value >= 0.02`. Only the Bovada row survives, so the mart gets **1 row**:

| Field | Value |
|---|---|
| bookmaker | Bovada |
| outcome | Buffalo Bills |
| price_american | +145 |
| consensus_fair_prob | 0.4181 |
| implied_prob | 0.4082 |
| edge | +0.99 percentage points |
| expected_value | +2.4% |
| is_best_price | true |
| is_latest_snapshot | true |

Why Bovada: it has the lowest vig and the highest Bills price, so its +145 pays more than the market's consensus says the outcome is worth. Most rows are negative because every book's margin works against the bettor, which is exactly why a +EV row is rare and worth surfacing.

## Step 7: tests

`dbt test` runs after `dbt run`. It would fail the DAG if, for example, a mart row were below the EV threshold, a game had already started, or probabilities did not sum to 1.

## Row counts at a glance

| Stage | Rows for this snapshot |
|---|---|
| S3 | 1 file |
| `ODDS_RAW` | 1 |
| `stg_odds` | 10 |
| `int_odds_devigged` | 10 |
| `int_consensus_fair_prob` | 2 |
| `fct_ev_opportunities` | 1 |

Real snapshots hold a full slate of games and 8 or more books, so these numbers scale up, but the shape of the funnel is the same: wide and raw at the start, small and meaningful at the end.
