"""Fetch cost data from every provider adapter and keep a local history.

Every adapter returns records in one normalized shape:
    {"provider": "aws", "service": "Amazon EC2", "date": "2026-09-13", "cost": 4.32}

Design notes:
  * Adapters are imported lazily, inside the per-provider try/except, so a
    missing SDK, missing credentials or a failing API for ONE cloud never
    stops the others.
  * The current day is dropped before saving: billing data for "today" is
    partial and would look like a fake cost drop on the next run.
  * Re-fetched days REPLACE stored ones (providers revise recent numbers).

    python3 -m core.engine
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "cost_history.json"
LOG_FILE = ROOT / "data" / "run.log"

# provider name -> adapter module (each exposes get_daily_costs(days))
ADAPTERS = {
    "aws": "adapters.aws_adapter",
    "gcp": "adapters.gcp_adapter",
    "azure": "adapters.azure_adapter",
}


def log(message: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
    print(line)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")
    except OSError:
        pass  # logging must never break a run


def load_history(path: Path | str | None = None) -> list[dict]:
    path = Path(path or DATA_FILE)  # resolved at call time so tests can redirect it
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return data["records"] if isinstance(data, dict) else data


def save_history(records: list[dict], path: Path | str | None = None) -> None:
    path = Path(path or DATA_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(records, key=lambda r: (r["provider"], r["service"], r["date"]))
    path.write_text(json.dumps(ordered, indent=2))


def merge_records(old: list[dict], new: list[dict]) -> list[dict]:
    """Union by (provider, service, date); `new` wins on conflicts."""
    merged: dict[tuple, dict] = {}
    for r in [*old, *new]:
        merged[(r["provider"], r["service"], r["date"])] = r
    return list(merged.values())


def drop_today(records: list[dict], today: str | None = None) -> list[dict]:
    """Remove today's (partial) rows."""
    today = today or date.today().isoformat()
    return [r for r in records if r["date"] != today]


def fetch_all(days: int = 14) -> tuple[list[dict], dict[str, str]]:
    """Fetch from every adapter. Returns (records, {provider: error_message})."""
    records: list[dict] = []
    errors: dict[str, str] = {}
    for provider, module_path in ADAPTERS.items():
        try:
            adapter = importlib.import_module(module_path)
            fetched = adapter.get_daily_costs(days=days)
            log(f"  {provider}: fetched {len(fetched)} records")
            records.extend(fetched)
        except Exception as exc:  # isolate each provider on purpose
            errors[provider] = f"{type(exc).__name__}: {exc}"
            log(f"  {provider}: FAILED ({errors[provider]})")
    return records, errors


def run(days: int = 14) -> dict[str, str]:
    """Fetch, merge into history, save. Returns per-provider errors."""
    log("Fetching cost data...")
    fetched, errors = fetch_all(days)
    history = merge_records(load_history(), drop_today(fetched))
    save_history(history)
    log(f"Stored {len(history)} total records ({len(fetched)} fetched this run).")
    return errors


if __name__ == "__main__":
    failed = run()
    # exit non-zero only if EVERY provider failed, so cron/CI notices real outages
    sys.exit(1 if len(failed) == len(ADAPTERS) else 0)
