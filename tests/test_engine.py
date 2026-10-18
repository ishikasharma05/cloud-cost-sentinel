import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import engine


def rec(provider, service, date, cost):
    return {"provider": provider, "service": service, "date": date, "cost": cost}


def test_merge_replaces_instead_of_duplicating():
    old = [rec("aws", "EC2", "2026-09-10", 1.0), rec("aws", "EC2", "2026-09-11", 2.0)]
    new = [rec("aws", "EC2", "2026-09-11", 2.5), rec("aws", "EC2", "2026-09-12", 3.0)]
    merged = engine.merge_records(old, new)
    assert len(merged) == 3
    assert {r["date"]: r["cost"] for r in merged}["2026-09-11"] == 2.5


def test_drop_today_removes_partial_day():
    rows = [rec("gcp", "GCE", "2026-10-17", 5.0), rec("gcp", "GCE", "2026-10-18", 1.0)]
    assert [r["date"] for r in engine.drop_today(rows, today="2026-10-18")] == ["2026-10-17"]


def test_one_provider_failing_does_not_stop_the_other(monkeypatch):
    class Good:
        @staticmethod
        def get_daily_costs(days):
            return [rec("aws", "EC2", "2026-10-17", 4.0)]

    class Bad:
        @staticmethod
        def get_daily_costs(days):
            raise RuntimeError("billing export initializing")

    monkeypatch.setattr(engine, "ADAPTERS", {"aws": "good", "gcp": "bad"})
    monkeypatch.setattr(engine.importlib, "import_module", lambda p: Good if p == "good" else Bad)
    monkeypatch.setattr(engine, "log", lambda m: None)
    records, errors = engine.fetch_all(days=7)
    assert len(records) == 1 and "gcp" in errors and "aws" not in errors