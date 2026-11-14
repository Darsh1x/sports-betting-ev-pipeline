import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))

from fetch_odds import build_envelope, build_key  # noqa: E402

FETCHED_AT = datetime(2026, 10, 14, 18, 30, 5, tzinfo=timezone.utc)


def test_build_key_partitions_by_sport_and_date():
    key = build_key("americanfootball_nfl", FETCHED_AT)
    assert key == "raw/odds/sport=americanfootball_nfl/dt=2026-10-14/20261014T183005Z.json"


def test_envelope_records_metadata_and_count():
    envelope = build_envelope([{"id": "a"}, {"id": "b"}], "americanfootball_nfl", "us", "h2h", FETCHED_AT)
    assert envelope["event_count"] == 2
    assert envelope["fetched_at"] == "2026-10-14T18:30:05+00:00"
    assert envelope["events"] == [{"id": "a"}, {"id": "b"}]
