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