from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT = "/opt/airflow/project"
PYTHON = "/opt/airflow/pipeline-venv/bin/python"
DBT = "/opt/airflow/pipeline-venv/bin/dbt"

with DAG(
    dag_id="odds_pipeline",
    description="Odds API -> S3 -> Snowflake -> dbt build",
    # every 3 hours keeps the free Odds API tier (500 credits/month) under budget
    schedule="0 */3 * * *",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["odds"],
) as dag:
    fetch_odds = BashOperator(
        task_id="fetch_odds",
        bash_command=f"cd {PROJECT} && {PYTHON} ingestion/fetch_odds.py",
    )

    load_to_snowflake = BashOperator(
        task_id="load_to_snowflake",
        bash_command=f"cd {PROJECT} && {PYTHON} ingestion/load_to_snowflake.py",
    )

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"cd {PROJECT}/dbt && {DBT} deps",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {PROJECT}/dbt && {DBT} run",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {PROJECT}/dbt && {DBT} test",
    )

    fetch_odds >> load_to_snowflake >> dbt_deps >> dbt_run >> dbt_test
