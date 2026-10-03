"""Unit tests for the Appendix F eval runner (no real LLM, no live server)."""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import app.evaluation.runner as runner_mod
import run_eval as run_eval_mod
from app.evaluation.appendix_f import APPENDIX_F_CASES, CASE_ORDER
from app.evaluation.invariants import evaluate_case, note_for_checks
from app.evaluation.runner import CaseResult, EvalRunError, build_payload, render_eval_md, run_evaluation

AEST = timezone(timedelta(hours=10))
NOW = datetime(2026, 10, 11, 10, 0, 0, tzinfo=AEST)


def test_appendix_f_order_and_phones():
    assert CASE_ORDER == (
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7a",
        "7b",
        "8",
        "9",
        "10",
        "11",
        "12",
    )
    assert len(APPENDIX_F_CASES) == 13
    aisha = [c for c in APPENDIX_F_CASES if c.case_id in {"7a", "7b"}]
    assert aisha[0].phone == aisha[1].phone == "+61491571491"
    assert "solar panels" in APPENDIX_F_CASES[4].message
    assert APPENDIX_F_CASES[12].case_id == "12"
    assert APPENDIX_F_CASES[12].from_name is None


def test_build_payload_whatsapp_and_reference_time():
    case = APPENDIX_F_CASES[0]
    payload = build_payload(case, NOW)
    assert payload["channel"] == "whatsapp"
    assert payload["from_phone"] == case.phone
    assert payload["from_name"] == "Priya"
    assert payload["message"] == case.message
    assert payload["received_at"] == NOW.isoformat()


def test_run_evaluation_order_and_eval_md(tmp_path: Path):
    calls: list[dict] = []

    def fake_post(url: str, payload: dict, timeout: float) -> dict:
        assert url.endswith("/enquiries")
        assert "X-API-Key" not in str(payload)
        calls.append(payload)
        idx = len(calls)
        return {
            "_http_status": 200,
            "reply": f"reply-{idx}",
            "lead": {
                "lead_id": f"lead-{payload['from_phone']}",
                "phone": payload["from_phone"],
                "status": "awaiting_info",
                "quote_low": None,
                "quote_high": None,
                "booked_slot_id": None,
                "roof_material": "metal" if payload["from_phone"] == "+61491571491" else None,
                "service_type": (
                    "roof_restoration" if payload["from_phone"] == "+61491571491" else None
                ),
            },
            "tool_calls": [{"tool": "capture_lead_details", "args": {}, "result": {}}],
        }

    out = tmp_path / "eval.md"
    results = run_evaluation(
        base_url="http://example.test",
        output_path=out,
        http_post=fake_post,
        received_at=NOW,
    )

    assert [c["from_phone"] for c in calls] == [c.phone for c in APPENDIX_F_CASES]
    assert [c["message"] for c in calls] == [c.message for c in APPENDIX_F_CASES]
    assert calls[6]["from_phone"] == calls[7]["from_phone"]
    assert len(results) == 13
    text = out.read_text(encoding="utf-8")
    for case in APPENDIX_F_CASES:
        assert f"Case {case.case_id}" in text
        assert case.message in text
        assert case.phone in text
    assert "reply-1" in text
    assert "capture_lead_details" in text


def test_failing_invariant_writes_honest_note():
    response = {
        "reply": "ok",
        "lead": {
            "lead_id": "x",
            "status": "awaiting_info",
            "quote_low": None,
            "quote_high": None,
        },
        "tool_calls": [],
    }
    checks = evaluate_case("1", response)
    note = note_for_checks(checks)
    assert any(not c.passed for c in checks)
    assert note != "None."
    assert "expected pass" in note.lower() or "got" in note.lower()


def test_passing_checks_note_none():
    response = {
        "reply": "estimate $8,100 to $10,800",
        "lead": {
            "lead_id": "p",
            "status": "quoted",
            "quote_low": 8100,
            "quote_high": 10800,
        },
        "tool_calls": [
            {"tool": "check_service_area", "args": {}, "result": {}},
            {"tool": "estimate_price", "args": {}, "result": {}},
        ],
    }
    checks = evaluate_case("1", response)
    assert all(c.passed for c in checks)
    assert note_for_checks(checks) == "None."


def test_http_failure_does_not_fabricate_eval(tmp_path: Path):
    def boom(url: str, payload: dict, timeout: float) -> dict:
        raise EvalRunError("connection refused")

    out = tmp_path / "eval.md"
    with pytest.raises(EvalRunError, match="connection refused"):
        run_evaluation(
            base_url="http://127.0.0.1:9",
            output_path=out,
            http_post=boom,
            received_at=NOW,
        )
    assert not out.exists()


def test_runner_is_http_only_no_db_reset_hooks():
    """run_eval / runner must not depend on seed reset or DATABASE_URL mutation."""
    assert not hasattr(runner_mod, "reset_baseline")
    assert "run_seed" not in dir(runner_mod)
    src = Path(runner_mod.__file__).read_text(encoding="utf-8")
    assert "run_seed" not in src
    assert "reset_db" not in src
    assert "DATABASE_URL" not in src
    assert "ADMIN_API_KEY" not in src

    cli_src = Path(run_eval_mod.__file__).read_text(encoding="utf-8")
    assert "--no-reset" not in cli_src
    assert "reset_db" not in cli_src
    assert "run_seed" not in cli_src
    assert "ADMIN_API_KEY" not in cli_src

    params = inspect.signature(run_evaluation).parameters
    assert "reset_db" not in params
    assert "database_url" not in params


def test_render_includes_response_fields():
    case = APPENDIX_F_CASES[0]
    result = CaseResult(
        case=case,
        http_status=200,
        response={
            "reply": "Hello Priya",
            "lead": {"lead_id": "abc", "status": "quoted"},
            "tool_calls": [{"tool": "estimate_price", "args": {}, "result": {"low": 1}}],
        },
        checks=[],
        note="None.",
    )
    md = render_eval_md([result], base_url="http://localhost:8000")
    assert "Hello Priya" in md
    assert "quoted" in md
    assert "estimate_price" in md
    assert case.message in md
