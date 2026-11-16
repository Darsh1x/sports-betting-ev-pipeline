import os
from pathlib import Path

import pandas as pd

SAMPLE_PATH = Path(__file__).parent / "sample" / "ev_opportunities.csv"
TIME_COLUMNS = ["fetched_at", "commence_time"]


def source_name():
    return os.environ.get("DATA_SOURCE", "sample")


def _from_sample():
    return pd.read_csv(SAMPLE_PATH, parse_dates=TIME_COLUMNS)


def _from_snowflake():
    import snowflake.connector

    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
    )
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ANALYTICS.FCT_EV_OPPORTUNITIES")
        columns = [c[0].lower() for c in cursor.description]
        df = pd.DataFrame(cursor.fetchall(), columns=columns)
    finally:
        conn.close()
    for col in TIME_COLUMNS:
        df[col] = pd.to_datetime(df[col], utc=True)
    for col in ["expected_value", "edge", "consensus_fair_prob", "implied_prob", "decimal_odds"]:
        df[col] = df[col].astype(float)
    return df


def load_opportunities():
    return _from_snowflake() if source_name() == "snowflake" else _from_sample()
