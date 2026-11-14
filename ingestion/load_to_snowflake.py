import os
import sys
import tempfile
from pathlib import Path

import boto3
import snowflake.connector
from dotenv import load_dotenv

SQL_DIR = Path(__file__).resolve().parents[1] / "snowflake"
S3_PREFIX = "raw/odds/"
STAGE = "@BETTING_DB.RAW.ODDS_STAGE"


def connect():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
    )


def run_setup(cursor):
    sql = (SQL_DIR / "setup.sql").read_text()
    for statement in filter(None, (s.strip() for s in sql.split(";"))):
        cursor.execute(statement)


def list_s3_keys(bucket):
    paginator = boto3.client("s3").get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=S3_PREFIX):
        for obj in page.get("Contents", []):
            yield obj["Key"]


def staged_files(cursor):
    cursor.execute(f"LIST {STAGE}")
    # LIST prefixes every name with the stage name, e.g. odds_stage/sport=.../x.json
    return {row[0].split("/", 1)[1] for row in cursor.fetchall()}


def upload_missing(cursor, bucket):
    s3 = boto3.client("s3")
    already_staged = staged_files(cursor)
    uploaded = 0
    with tempfile.TemporaryDirectory() as tmp:
        for key in list_s3_keys(bucket):
            relative = key[len(S3_PREFIX):]
            if not relative.endswith(".json") or relative in already_staged:
                continue
            local = Path(tmp) / Path(relative).name
            s3.download_file(bucket, key, str(local))
            cursor.execute(
                f"PUT file://{local} {STAGE}/{Path(relative).parent} AUTO_COMPRESS=FALSE"
            )
            local.unlink()
            uploaded += 1
    return uploaded


def copy_into_table(cursor):
    cursor.execute((SQL_DIR / "load_odds.sql").read_text())
    return cursor.fetchall()


def main():
    load_dotenv()
    conn = connect()
    try:
        cursor = conn.cursor()
        run_setup(cursor)
        uploaded = upload_missing(cursor, os.environ["S3_BUCKET"])
        results = copy_into_table(cursor)
        cursor.execute("SELECT COUNT(*) FROM BETTING_DB.RAW.ODDS_RAW")
        total = cursor.fetchone()[0]
    finally:
        conn.close()

    loaded = [row for row in results if len(row) > 1 and row[1] == "LOADED"]
    print(
        f"{uploaded} file(s) staged, {len(loaded)} loaded; "
        f"ODDS_RAW now has {total} row(s)"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
