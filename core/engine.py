"""
engine.py

Fetches cost data from every connected cloud provider adapter and stores
it locally as JSON, in one normalized format regardless of provider.
Detection and alerting get wired in during Week 2 and Week 3 --
see detector.py and alerter.py for the (currently stubbed) next steps.

Run this manually once a day to build up real baseline data:
    python3 core/engine.py

If a provider's adapter fails (e.g. GCP billing export still
initializing), the run continues with whichever providers succeeded
rather than failing the whole run.
"""

import json
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.aws_adapter import get_daily_costs as get_aws_costs
from adapters.gcp_adapter import get_daily_costs as get_gcp_costs

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
        seen[key] = r
    return list(seen.values())


def run() -> None:
    print(f"[{datetime.now().isoformat()}] Fetching cost data...")

    new_records = []

    try:
        aws_records = get_aws_costs(days=14)
        print(f"  AWS: fetched {len(aws_records)} records.")
        new_records.extend(aws_records)
    except Exception as e:
        print(f"  AWS: fetch failed ({e})")

    try:
        gcp_records = get_gcp_costs(days=14)
        print(f"  GCP: fetched {len(gcp_records)} records.")
        new_records.extend(gcp_records)
    except Exception as e:
        print(f"  GCP: fetch failed ({e})")

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
