import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

SEED = 7
BOOKS = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
    "bovada": "Bovada",
    "betrivers": "BetRivers",
    "pointsbetus": "PointsBet",
}
GAMES = [
    ("Kansas City Chiefs", "Buffalo Bills", 0.57),
    ("Philadelphia Eagles", "Dallas Cowboys", 0.66),
    ("San Francisco 49ers", "Seattle Seahawks", 0.70),
    ("Baltimore Ravens", "Cincinnati Bengals", 0.61),
    ("Detroit Lions", "Green Bay Packers", 0.55),
    ("Miami Dolphins", "New York Jets", 0.64),
]
EV_THRESHOLD = 0.02
MIN_BOOKS = 5


def to_american(prob):
    if prob >= 0.5:
        return round(-100 * prob / (1 - prob) / 5) * 5
    return round(100 * (1 - prob) / prob / 5) * 5


def implied(price):
    return -price / (-price + 100) if price < 0 else 100 / (price + 100)


def decimal(price):
    return 1 + 100 / -price if price < 0 else 1 + price / 100


def build():
    rng = random.Random(SEED)
    end = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)
    snapshots = [end - timedelta(hours=6 * i) for i in range(19, -1, -1)]
    kickoffs = {g: end + timedelta(hours=18 + 20 * i) for i, g in enumerate(GAMES)}
    rows = []
    for fetched_at in snapshots:
        for game, kickoff in kickoffs.items():
            home, away, home_prob = game
            drift = rng.gauss(0, 0.01)
            quotes = []
            for key, title in BOOKS.items():
                if rng.random() < 0.1:
                    continue
                vig = rng.uniform(0.02, 0.05)
                noise = rng.gauss(0, 0.02)
                p_home = min(max(home_prob + drift + noise, 0.05), 0.95)
                total = 1 + vig
                prices = (to_american(p_home * total), to_american((1 - p_home) * total))
                quotes.append((key, title, prices))
            fair = {home: [], away: []}
            for _, _, (ph, pa) in quotes:
                ih, ia = implied(ph), implied(pa)
                fair[home].append(ih / (ih + ia))
                fair[away].append(ia / (ih + ia))
            consensus = {k: sum(v) / len(v) for k, v in fair.items()}
            for key, title, prices in quotes:
                for outcome, price in zip((home, away), prices):
                    ev = consensus[outcome] * decimal(price) - 1
                    if ev < EV_THRESHOLD or len(quotes) < MIN_BOOKS:
                        continue
                    rows.append({
                        "fetched_at": fetched_at,
                        "event_id": f"{home[:3]}{away[:3]}".lower().replace(" ", ""),
                        "sport_key": "americanfootball_nfl",
                        "commence_time": kickoff,
                        "home_team": home,
                        "away_team": away,
                        "bookmaker_key": key,
                        "bookmaker_title": title,
                        "market_key": "h2h",
                        "outcome_name": outcome,
                        "price_american": price,
                        "decimal_odds": round(decimal(price), 4),
                        "implied_prob": round(implied(price), 4),
                        "consensus_fair_prob": round(consensus[outcome], 4),
                        "edge": round(consensus[outcome] - implied(price), 4),
                        "expected_value": round(ev, 4),
                        "book_count": len(quotes),
                    })
    df = pd.DataFrame(rows)
    group = ["fetched_at", "event_id", "market_key", "outcome_name"]
    best = df.groupby(group)["decimal_odds"].transform("max")
    df["is_best_price"] = df["decimal_odds"] == best
    df["is_latest_snapshot"] = df["fetched_at"] == df["fetched_at"].max()
    return df


if __name__ == "__main__":
    out = Path(__file__).parent / "ev_opportunities.csv"
    df = build()
    df.to_csv(out, index=False)
    print(f"{len(df)} rows, {df['fetched_at'].nunique()} snapshots -> {out}")
