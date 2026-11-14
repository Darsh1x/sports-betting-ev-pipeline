import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
import requests
from dotenv import load_dotenv

API_URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds"
LOCAL_DIR = Path("data/raw")


def fetch_odds(api_key, sport, regions, markets):
    response = requests.get(
        API_URL.format(sport=sport),
        params={
            "apiKey": api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": "american",
        },
        timeout=30,
    )
    if not response.ok:
        # response.raise_for_status() would put the apiKey in the error message
        raise RuntimeError(f"Odds API returned {response.status_code}: {response.text[:200]}")
    return response.json(), response.headers.get("x-requests-remaining")


def build_envelope(events, sport, regions, markets, fetched_at):
    return {
        "fetched_at": fetched_at.isoformat(),
        "sport": sport,
        "regions": regions,
        "markets": markets,
        "event_count": len(events),
        "events": events,
    }


def build_key(sport, fetched_at):
    return (
        f"raw/odds/sport={sport}/dt={fetched_at:%Y-%m-%d}/"
        f"{fetched_at:%Y%m%dT%H%M%SZ}.json"
    )


def write_s3(body, bucket, key):
    boto3.client("s3").put_object(
        Bucket=bucket, Key=key, Body=body, ContentType="application/json"
    )
    return f"s3://{bucket}/{key}"


def write_local(body, key):
    path = LOCAL_DIR / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return str(path)


def main():
    parser = argparse.ArgumentParser(description="Fetch odds and land raw JSON.")
    parser.add_argument("--sport", default="americanfootball_nfl")
    parser.add_argument("--regions", default="us")
    parser.add_argument("--markets", default="h2h")
    parser.add_argument("--local", action="store_true", help="write to data/raw instead of S3")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ["ODDS_API_KEY"]

    fetched_at = datetime.now(timezone.utc)
    events, remaining = fetch_odds(api_key, args.sport, args.regions, args.markets)

    envelope = build_envelope(events, args.sport, args.regions, args.markets, fetched_at)
    body = json.dumps(envelope).encode("utf-8")
    key = build_key(args.sport, fetched_at)

    if args.local:
        destination = write_local(body, key)
    else:
        destination = write_s3(body, os.environ["S3_BUCKET"], key)

    print(f"{len(events)} events -> {destination} (API credits remaining: {remaining})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
