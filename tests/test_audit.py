"""R10 enquiry audit JSONL behaviour."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.audit import AuditLogError, write_enquiry_audit
from app.config import get_settings
from app.db import make_session_factory
from app.deps import get_db, get_llm
from app.main import app
from app.models import Lead, Message
from tests.fakes import DONE, ScriptedLLM, round_with, tool

AEST = timezone(timedelta(hours=10))
NOW = datetime(2026, 10, 11, 10, 0, 0, tzinfo=AEST)


def test_write_enquiry_audit_appends(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    first = write_enquiry_audit(
        lead_id="lead-1",
        final_status="quoted",
        tool_calls=[{"tool": "estimate_price", "args": {}, "result": {"low": 1}}],
        latency_ms=12,
        log_path=path,
    )
    second = write_enquiry_audit(
        lead_id="lead-2",
        final_status="emergency",
        tool_calls=[{"tool": "mark_emergency", "args": {}, "result": {}}],
        latency_ms=3,
        log_path=path,
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == first
    assert json.loads(lines[1]) == second


def test_write_enquiry_audit_failure_surfaces(tmp_path: Path):
    bad = tmp_path / "missing" / "nope.jsonl"
    # Create a directory where a file is expected to force a write failure.
    bad.mkdir(parents=True)
    with pytest.raises(AuditLogError):
        write_enquiry_audit(
            lead_id="lead-x",
            final_status="new",
            tool_calls=[],
            latency_ms=0,
            log_path=bad,
        )


def test_audit_write_failure_rolls_back_enquiry(seeded_engine, monkeypatch, tmp_path: Path):
    """
    Existing policy: business work may flush, but if R10 audit fails the request
    must return 500 and the FastAPI DB dependency must roll back the session.
    """
    # Point audit path at a directory so the real write_enquiry_audit open fails.
    bad_audit = tmp_path / "audit_is_a_dir"
    bad_audit.mkdir()
    monkeypatch.setenv("AUDIT_LOG_PATH", str(bad_audit))
    monkeypatch.setenv("NOTIFICATIONS_LOG_PATH", str(tmp_path / "notifications.log"))
    get_settings.cache_clear()

    def _db():
        session = make_session_factory(seeded_engine)()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    phone = "+61491990001"
    capture = {
        "name": "AuditFail",
        "service_type": "roof_restoration",
        "roof_material": "tile",
        "size_m2": 180,
        "storeys": 1,
        "postcode": "4064",
        "suburb": "Paddington",
    }
    llm = ScriptedLLM(
        [
            round_with(tool("capture_lead_details", capture)),
            round_with(tool("check_service_area", {"postcode": "4064"})),
            round_with(tool("estimate_price", {})),
            DONE,
        ]
    )

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_llm] = lambda: llm
    client = TestClient(app)
    try:
        before = make_session_factory(seeded_engine)()
        lead_count_before = before.scalar(select(func.count()).select_from(Lead)) or 0
        message_count_before = before.scalar(select(func.count()).select_from(Message)) or 0
        before.close()

        response = client.post(
            "/enquiries",
            json={
                "channel": "whatsapp",
                "from_phone": phone,
                "from_name": "AuditFail",
                "message": (
                    "Hi, need a quote for restoring my tiled roof, about 180 sqm, "
                    "single storey, in Paddington 4064."
                ),
                "received_at": NOW.isoformat(),
            },
        )
        assert response.status_code == 500

        after = make_session_factory(seeded_engine)()
        assert (after.scalar(select(func.count()).select_from(Lead)) or 0) == lead_count_before
        assert (after.scalar(select(func.count()).select_from(Message)) or 0) == message_count_before
        assert after.scalar(select(Lead).where(Lead.phone == phone)) is None
        after.close()
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
