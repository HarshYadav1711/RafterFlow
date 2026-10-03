"""Admin GET /leads with X-API-Key auth."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.deps import get_db
from app.main import app
from app.models import Channel, Lead, LeadStatus


def test_admin_auth_and_list(seeded_engine, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret-admin-key")
    get_settings.cache_clear()

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
    client = TestClient(app)
    try:
        from app.db import make_session_factory

        seed_session = make_session_factory(seeded_engine)()
        seed_session.add(
            Lead(
                phone="+61491130001",
                name="AdminVisible",
                channel=Channel.whatsapp.value,
                status=LeadStatus.quoted.value,
            )
        )
        seed_session.commit()
        seed_session.close()

        assert client.get("/leads").status_code == 401
        assert client.get("/leads", headers={"X-API-Key": "wrong"}).status_code == 401

        ok = client.get("/leads", headers={"X-API-Key": "secret-admin-key"})
        assert ok.status_code == 200
        bodies = ok.json()
        assert any(row["phone"] == "+61491130001" for row in bodies)

        filtered = client.get(
            "/leads",
            params={"status": "quoted"},
            headers={"X-API-Key": "secret-admin-key"},
        )
        assert filtered.status_code == 200
        assert all(row["status"] == "quoted" for row in filtered.json())

        bad_filter = client.get(
            "/leads",
            params={"status": "qualified"},
            headers={"X-API-Key": "secret-admin-key"},
        )
        assert bad_filter.status_code == 422

        lead_id = next(row["lead_id"] for row in bodies if row["phone"] == "+61491130001")
        one = client.get(f"/leads/{lead_id}", headers={"X-API-Key": "secret-admin-key"})
        assert one.status_code == 200
        assert one.json()["name"] == "AdminVisible"

        missing = client.get(
            "/leads/00000000-0000-0000-0000-000000000099",
            headers={"X-API-Key": "secret-admin-key"},
        )
        assert missing.status_code == 404
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_agent_tools_have_no_admin_capability():
    from app.agent.tools_runtime import ALLOWED_TOOL_NAMES

    forbidden = {
        "list_leads",
        "get_lead",
        "get_all_customers",
        "run_sql",
        "execute_query",
        "admin",
    }
    assert ALLOWED_TOOL_NAMES.isdisjoint(forbidden)
    assert "book_inspection" in ALLOWED_TOOL_NAMES
