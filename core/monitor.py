"""Run detection + alerting over stored cost history.

    python3 -m core.monitor                 # check newest day in data/cost_history.json
    python3 -m core.monitor --simulate      # inject a fake spike to demo the alert
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from core.alerter import send_alerts
from core.detector import detect_anomalies

HISTORY = Path(__file__).resolve().parent.parent / "data" / "cost_history.json"


def load_history(path: Path = HISTORY) -> list[dict]:
    data = json.loads(path.read_text())
    return data["records"] if isinstance(data, dict) else data


def simulated_records() -> list[dict]:
    """8 calm days then a 4x spike on EC2, for demos and screenshots."""
    start = date.today() - timedelta(days=8)
    costs = [4.0, 4.2, 3.9, 4.1, 4.0, 4.3, 4.1, 16.5]
    return [
        {"provider": "aws", "service": "Amazon EC2",
         "date": (start + timedelta(days=i)).isoformat(), "cost": c}
        for i, c in enumerate(costs)
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulate", action="store_true", help="use a fake spike instead of real data")
    args = ap.parse_args()

    records = simulated_records() if args.simulate else load_history()
    anomalies = detect_anomalies(records)
    print(f"Checked {len(records)} records, found {len(anomalies)} anomaly(ies).")
    if args.simulate:
        # don't pollute the real dedup state during a demo
        send_alerts(anomalies, state_path=Path("/tmp/sentinel_demo_state.json"))
    else:
        send_alerts(anomalies)


if __name__ == "__main__":
    main()