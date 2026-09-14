"""
engine.py

Week 1 scope: fetch AWS cost data and store it locally as JSON.
Detection and alerting get wired in during Week 2 and Week 3 --
see detector.py and alerter.py for the (currently stubbed) next steps.

Run this manually once a day for the first week to build up real
baseline data:
    python core/engine.py
"""

import json
import sys
import os
from datetime import datetime

# Allow running this file directly (python core/engine.py) by adding
# the project root to the path, so `adapters` can be imported.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.aws_adapter import get_daily_costs

DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "cost_history.json",
)


def load_history() -> list[dict]:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_history(records: list[dict]) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(records, f, indent=2)


def dedupe(records: list[dict]) -> list[dict]:
    """Keep only one record per (provider, service, date) combo."""
    seen = {}
    for r in records:
        key = (r["provider"], r["service"], r["date"])
        seen[key] = r  # later fetches overwrite earlier ones for the same day
    return list(seen.values())


def run() -> None:
    print(f"[{datetime.now().isoformat()}] Fetching AWS cost data...")

    new_records = get_daily_costs(days=14)
    existing = load_history()

    combined = dedupe(existing + new_records)
    save_history(combined)

    print(f"Stored {len(combined)} total records ({len(new_records)} fetched this run).")
    print(f"Data written to: {DATA_FILE}")

    # Week 2 will plug in here:
    # anomalies = detector.find_anomalies(combined)
    # if anomalies:
    #     alerter.send_alert(anomalies)


if __name__ == "__main__":
    run()
