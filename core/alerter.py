"""Alerting: Slack webhook and/or Telegram bot, with console fallback and dedup.

Configure either or both via environment variables (see .env.example):
    SLACK_WEBHOOK_URL
    TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
With nothing configured, alerts are printed instead, so the pipeline never
fails silently. Uses only the standard library (no new dependencies).
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from core.detector import Anomaly

DEFAULT_STATE = Path(__file__).resolve().parent.parent / "data" / "alerted.json"


SYMBOLS = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}


def format_message(a: Anomaly) -> str:
    sym = SYMBOLS.get(a.currency, a.currency + " ")
    pct = "new spend" if a.pct_over_baseline == float("inf") else f"+{a.pct_over_baseline}%"
    return (
        f":rotating_light: Cost anomaly on *{a.provider.upper()} / {a.service}* ({a.date})\n"
        f"Cost: {sym}{a.cost:.2f} vs baseline {sym}{a.baseline_mean:.2f} ({pct}, z={a.z_score})"
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


def _post_telegram(token: str, chat_id: str, text: str) -> None:
    # Telegram gets plain text: Slack's :emoji: codes and *bold* don't render there.
    plain = text.replace(":rotating_light:", "🚨").replace("*", "")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": plain}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def send_alerts(
    anomalies: list[Anomaly],
    webhook_url: str | None = None,
    state_path: Path | None = None,
) -> list[Anomaly]:
    """Send each anomaly once (dedup by provider+service+date). Returns those sent."""
    webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID")
    state_path = state_path or DEFAULT_STATE
    already = _load_state(state_path)
    sent: list[Anomaly] = []

    for a in anomalies:
        if _key(a) in already:
            continue
        msg = format_message(a)
        senders = []
        if webhook_url:
            senders.append(("slack", lambda m: _post(webhook_url, m)))
        if tg_token and tg_chat:
            senders.append(("telegram", lambda m: _post_telegram(tg_token, tg_chat, m)))
        if not senders:
            print(msg)
            delivered = True
        else:
            delivered = False
            for name, send in senders:
                try:
                    send(msg)
                    delivered = True
                except Exception as exc:  # one channel failing must not block the other
                    print(f"[alerter] {name} failed for {_key(a)}: {exc}")
        if not delivered:  # not marked as sent, so it is retried next run
            continue
        already.add(_key(a))
        sent.append(a)

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(sorted(already)))
    return sent
