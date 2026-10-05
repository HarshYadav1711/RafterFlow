"""LLM client provider-error handling (no live network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.deps import get_db, get_llm
from app.llm import (
    LLMRateLimitError,
    OpenAICompatibleClient,
    _retry_after_seconds,
)
from app.main import app


def test_retry_after_parses_groq_minutes_seconds_message():
    exc = RuntimeError(
        "Rate limit reached for model `openai/gpt-oss-120b`. "
        "Please try again in 4m15.312s. Need more tokens?"
    )
    assert _retry_after_seconds(exc) == pytest.approx(4 * 60 + 15.312)


def test_retry_after_uses_response_header():
    exc = SimpleNamespace(response=SimpleNamespace(headers={"retry-after": "12"}))
    assert _retry_after_seconds(exc) == 12.0


def test_complete_raises_rate_limit_without_long_sleep(monkeypatch):
    """Long TPD waits must fail fast with LLMRateLimitError, not hang the request."""
    sleeps: list[float] = []
    monkeypatch.setattr("app.llm.time.sleep", lambda seconds: sleeps.append(seconds))

    class FakeRateLimitError(Exception):
        pass

    class FakeCompletions:
        def create(self, **_kwargs):
            raise FakeRateLimitError(
                "Error code: 429 - Please try again in 4m15.312s."
            )

    class FakeClient:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    import openai

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setattr(openai, "RateLimitError", FakeRateLimitError)
    monkeypatch.setattr(openai, "APIError", Exception)

    settings = SimpleNamespace(
        llm_api_key="test-key",
        llm_base_url="https://example.test/v1",
        llm_model="test-model",
    )
    client = OpenAICompatibleClient(settings=settings)  # type: ignore[arg-type]

    with pytest.raises(LLMRateLimitError) as caught:
        client.complete([{"role": "user", "content": "hi"}], tools=[])

    assert caught.value.retry_after_seconds == pytest.approx(4 * 60 + 15.312)
    assert sleeps == []


def test_enquiry_maps_rate_limit_to_503(seeded_engine, monkeypatch, tmp_path):
    monkeypatch.setenv("NOTIFICATIONS_LOG_PATH", str(tmp_path / "notifications.log"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "enquiry_audit.jsonl"))
    get_settings.cache_clear()

    class RateLimitedLLM:
        def complete(self, messages, tools):
            raise LLMRateLimitError(
                "LLM rate limit exceeded; retry after about 255s.",
                retry_after_seconds=255.0,
            )

    def _db():
        from app.db import make_session_factory

        session = make_session_factory(seeded_engine)()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_llm] = lambda: RateLimitedLLM()
    client = TestClient(app)
    try:
        resp = client.post(
            "/enquiries",
            json={
                "channel": "whatsapp",
                "from_phone": "+61491149999",
                "message": "hello",
                "received_at": "2026-10-11T10:00:00+10:00",
            },
        )
        assert resp.status_code == 503
        assert "rate limit" in resp.json()["detail"].lower()
        assert resp.headers.get("retry-after") == "255"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_complete_retries_short_rate_limit_then_succeeds(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("app.llm.time.sleep", lambda seconds: sleeps.append(seconds))
    calls = {"n": 0}

    class FakeRateLimitError(Exception):
        pass

    class FakeMessage:
        content = "ok"
        tool_calls = []

    class FakeCompletions:
        def create(self, **_kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise FakeRateLimitError("Please try again in 1.5s.")
            return SimpleNamespace(choices=[SimpleNamespace(message=FakeMessage())])

    class FakeClient:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    import openai

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    monkeypatch.setattr(openai, "RateLimitError", FakeRateLimitError)
    monkeypatch.setattr(openai, "APIError", Exception)

    settings = SimpleNamespace(
        llm_api_key="test-key",
        llm_base_url="https://example.test/v1",
        llm_model="test-model",
    )
    client = OpenAICompatibleClient(settings=settings)  # type: ignore[arg-type]

    result = client.complete([{"role": "user", "content": "hi"}], tools=[])
    assert result.content == "ok"
    assert calls["n"] == 2
    assert sleeps == [1.5]
