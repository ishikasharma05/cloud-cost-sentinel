import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import engine, pipeline
from core.detector import detect_anomalies


def series(provider, costs, end, service="Svc", **extra):
    start = end - timedelta(days=len(costs) - 1)
    return [{"provider": provider, "service": service,
             "date": (start + timedelta(days=i)).isoformat(), "cost": c, **extra}
            for i, c in enumerate(costs)]


def test_lagging_provider_is_still_checked():
    """GCP data ends a day before AWS; its spike must not be skipped."""
    spike = [4.0, 4.2, 3.9, 4.1, 4.0, 4.3, 4.1, 16.0]
    recs = series("aws", [1.0] * 9, date(2026, 10, 18)) + series("gcp", spike, date(2026, 10, 17))
    found = detect_anomalies(recs)
    assert [a.provider for a in found] == ["gcp"]


def test_currency_flows_to_anomaly():
    spike = [400.0, 410.0, 395.0, 405.0, 400.0, 415.0, 405.0, 1600.0]
    recs = series("azure", spike, date(2026, 10, 17), currency="INR")
    assert detect_anomalies(recs)[0].currency == "INR"


def test_pipeline_end_to_end(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(engine, "DATA_FILE", tmp_path / "h.json")
    monkeypatch.setattr(engine, "log", lambda m: None)
    monkeypatch.setattr("core.alerter.DEFAULT_STATE", tmp_path / "alerted.json")
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    yesterday = date.today() - timedelta(days=1)
    spike = [4.0, 4.2, 3.9, 4.1, 4.0, 4.3, 4.1, 16.0]
    monkeypatch.setattr(engine, "fetch_all",
                        lambda days=14: (series("aws", spike, yesterday, "Amazon EC2"), {}))
    assert pipeline.run_pipeline() == 0
    assert "Amazon EC2" in capsys.readouterr().out
