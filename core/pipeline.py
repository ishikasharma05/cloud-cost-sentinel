"""One command for the whole agent: fetch -> store -> detect -> alert.

    python3 -m core.pipeline
"""

from __future__ import annotations

import sys

from core import engine
from core.alerter import send_alerts
from core.detector import detect_anomalies


def run_pipeline(days: int = 14) -> int:
    errors = engine.run(days)
    records = engine.load_history()
    anomalies = detect_anomalies(records)
    sent = send_alerts(anomalies)
    engine.log(
        f"Checked {len(records)} records: {len(anomalies)} anomaly(ies), "
        f"{len(sent)} new alert(s) sent."
    )
    if errors:
        engine.log(f"Providers that failed this run: {', '.join(sorted(errors))}")
    # fail only if nothing could be fetched at all, so CI surfaces real outages
    return 1 if len(errors) == len(engine.ADAPTERS) else 0


if __name__ == "__main__":
    sys.exit(run_pipeline())
