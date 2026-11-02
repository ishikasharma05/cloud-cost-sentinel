import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.alerter import send_alerts, format_message
from core.detector import Anomaly


def an(date="2026-09-20"):
    return Anomaly("aws", "Amazon EC2", date, 16.5, 4.1, 0.1, 12.0, 302.4)


def test_message_contains_key_facts():
    msg = format_message(an())
    assert "AWS / Amazon EC2" in msg and "$16.50" in msg and "+302.4%" in msg


def test_dedup_same_anomaly_sent_once(tmp_path, capsys):
    state = tmp_path / "state.json"
    first = send_alerts([an()], webhook_url=None, state_path=state)
    second = send_alerts([an()], webhook_url=None, state_path=state)
    assert len(first) == 1 and second == []


def test_new_date_is_a_new_alert(tmp_path):
    state = tmp_path / "state.json"
    send_alerts([an("2026-09-20")], state_path=state)
    assert len(send_alerts([an("2026-09-21")], state_path=state)) == 1

def test_inr_symbol_used_for_non_usd():
    a = Anomaly("azure", "Storage", "2026-09-20", 1600.0, 400.0, 5.0, 9.0, 300.0, "INR")
    assert "₹1600.00" in format_message(a)


def test_telegram_sends_plain_text_and_dedups(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("core.alerter._post_telegram", lambda tok, chat, text: calls.append((tok, chat, text)))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    state = tmp_path / "s.json"
    assert len(send_alerts([an()], state_path=state)) == 1
    assert send_alerts([an()], state_path=state) == []
    assert calls[0][:2] == ("tok", "123") and len(calls) == 1


def test_one_channel_failing_does_not_block_the_other(tmp_path, monkeypatch):
    got = []
    def boom(*a): raise OSError("down")
    monkeypatch.setattr("core.alerter._post", boom)
    monkeypatch.setattr("core.alerter._post_telegram", lambda t, c, m: got.append(m))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    sent = send_alerts([an()], webhook_url="https://example.invalid/x", state_path=tmp_path / "s.json")
    assert len(sent) == 1 and len(got) == 1


def test_all_channels_failing_is_retried_next_run(tmp_path, monkeypatch):
    def boom(*a): raise OSError("down")
    monkeypatch.setattr("core.alerter._post", boom)
    state = tmp_path / "s.json"
    assert send_alerts([an()], webhook_url="https://example.invalid/x", state_path=state) == []
