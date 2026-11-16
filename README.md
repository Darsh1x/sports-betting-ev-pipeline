# Sports Betting +EV Detection Pipeline

A data pipeline that ingests live sports betting odds from multiple sportsbooks,
calculates fair (no-vig) probabilities by comparing books against each other,
and surfaces positive expected value (+EV) betting opportunities on a dashboard.

This is not a gambling tool — the deliverable is the pipeline and probability
math, not betting advice.

## Status

🚧 Under active development.

## Architecture

Ingestion (Python) → S3 (raw landing) → Snowflake (warehouse) → dbt (transforms)
→ Airflow (orchestration) → Streamlit (dashboard), all containerized with Docker Compose.

More details to come as each piece is built.

## Running the pipeline

Fill in `.env` (see `.env.example`), then:

```
docker compose up -d --build
```

Airflow UI is at http://localhost:8080 (admin / admin, local only). Unpause the
`odds_pipeline` DAG; it runs every 3 hours: fetch odds, load to Snowflake, then
`dbt deps`, `dbt run`, `dbt test`.

## Dashboard

The Streamlit dashboard runs with the rest of the stack at http://localhost:8501.
It defaults to generated sample data (`dashboard/sample/`). Set
`DATA_SOURCE=snowflake` in `.env` to read `ANALYTICS.FCT_EV_OPPORTUNITIES` live.

## Project structure

```
.
├── ingestion/    # fetches odds data from The Odds API
├── dbt/          # dbt project: staging, intermediate, mart models
├── airflow/      # Airflow DAGs
├── dashboard/    # Streamlit app
└── docker-compose.yml
```
