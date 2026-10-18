import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.detector import detect_anomalies


def make_series(provider, service, costs, start=date(2026, 9, 1)):
    return [
        {"provider": provider, "service": service,
         "date": (start + timedelta(days=i)).isoformat(), "cost": c}
        for i, c in enumerate(costs)
    ]


def test_flags_clear_spike():
    records = make_series("aws", "Amazon EC2", [4.0, 4.2, 3.9, 4.1, 4.0, 4.3, 4.1, 12.0])
    result = detect_anomalies(records)
    assert len(result) == 1
    assert result[0].service == "Amazon EC2"
    assert result[0].pct_over_baseline > 100


def test_normal_variation_not_flagged():
    records = make_series("aws", "Amazon S3", [2.0, 2.1, 1.9, 2.2, 2.0, 2.1, 2.0, 2.3])
    assert detect_anomalies(records) == []


def test_tiny_dollar_spike_ignored():
    # 0.01 -> 0.20 is a huge percentage jump but only $0.19; absolute gate blocks it.
    records = make_series("gcp", "Cloud Logging", [0.01] * 7 + [0.20])
    assert detect_anomalies(records) == []


def test_not_enough_history_skipped():
    records = make_series("aws", "AWS Lambda", [1.0, 1.0, 1.0, 9.0])
    assert detect_anomalies(records) == []


def test_flat_baseline_does_not_crash():
    records = make_series("gcp", "Compute Engine", [3.0] * 7 + [6.0])
    result = detect_anomalies(records)
    assert len(result) == 1


def test_providers_isolated():
    records = (
        make_series("aws", "Compute", [4.0, 4.1, 3.9, 4.0, 4.2, 4.1, 4.0, 4.1])
        + make_series("gcp", "Compute", [4.0, 4.1, 3.9, 4.0, 4.2, 4.1, 4.0, 15.0])
    )
    result = detect_anomalies(records)
    assert [a.provider for a in result] == ["gcp"]