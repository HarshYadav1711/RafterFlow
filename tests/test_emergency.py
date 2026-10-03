import json
from pathlib import Path

from app.models import Channel, Lead, Urgency
from app.tools.emergency import notify_on_call


def test_notify_on_call_writes_one_json_line(seeded_session, tmp_path, monkeypatch):
    log_path = tmp_path / "on_call.jsonl"
    monkeypatch.setenv("NOTIFICATIONS_LOG_PATH", str(log_path))

    lead = Lead(
        phone="+61491570158",
        name="Mark",
        channel=Channel.whatsapp.value,
        postcode="4066",
        urgency=Urgency.emergency.value,
    )
    seeded_session.add(lead)
    seeded_session.commit()

    payload = notify_on_call(lead, log_path=log_path)
    assert payload["lead_id"] == lead.lead_id
    assert payload["phone"] == "+61491570158"
    assert payload["name"] == "Mark"
    assert payload["postcode"] == "4066"
    assert payload["notified_at"] == "2026-10-11T10:00:00+10:00"

    lines = Path(log_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed == payload
    assert "message" not in parsed
    assert "conversation" not in parsed


def test_notify_on_call_appends(seeded_session, tmp_path):
    log_path = tmp_path / "on_call.jsonl"
    a = Lead(phone="+61490000010", channel=Channel.whatsapp.value)
    b = Lead(phone="+61490000011", channel=Channel.whatsapp.value)
    seeded_session.add_all([a, b])
    seeded_session.commit()

    notify_on_call(a, log_path=log_path)
    notify_on_call(b, log_path=log_path)
    lines = Path(log_path).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
