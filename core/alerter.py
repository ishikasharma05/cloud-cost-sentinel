"""Alerting: Slack-compatible webhook, with console fallback and dedup.

Set SLACK_WEBHOOK_URL in your environment (see .env.example). With no webhook
configured, alerts are printed instead, so the pipeline never fails silently.
Uses only the standard library (no new dependencies).
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from core.detector import Anomaly

DEFAULT_STATE = Path(__file__).resolve().parent.parent / "data" / "alerted.json"


def format_message(a: Anomaly) -> str:
    pct = "new spend" if a.pct_over_baseline == float("inf") else f"+{a.pct_over_baseline}%"
    return (
        f":rotating_light: Cost anomaly on *{a.provider.upper()} / {a.service}* ({a.date})\n"
        f"Cost: ${a.cost:.2f} vs baseline ${a.baseline_mean:.2f} ({pct}, z={a.z_score})"
    )


def _key(a: Anomaly) -> str:
    return f"{a.provider}|{a.service}|{a.date}"


def _load_state(path: Path) -> set[str]:
    try:
        return set(json.loads(path.read_text()))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _post(webhook_url: str, text: str) -> None:
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def send_alerts(
    anomalies: list[Anomaly],
    webhook_url: str | None = None,
    state_path: Path = DEFAULT_STATE,
) -> list[Anomaly]:
    """Send each anomaly once (dedup by provider+service+date). Returns those sent."""
    webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
    already = _load_state(state_path)
    sent: list[Anomaly] = []

    for a in anomalies:
        if _key(a) in already:
            continue
        msg = format_message(a)
        try:
            if webhook_url:
                _post(webhook_url, msg)
            else:
                print(msg)
        except Exception as exc:  # a failed alert must not crash the run or be marked as sent
            print(f"[alerter] failed to send alert for {_key(a)}: {exc}")
            continue
        already.add(_key(a))
        sent.append(a)

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(sorted(already)))
    return sent