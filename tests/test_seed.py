import json

from sqlalchemy import func, select

from app.models import AvailabilitySlot, PolicyRecord, PricingConfig, PricingRate, ServiceArea
from app.seed import load_business_rules, run_seed


def test_seed_succeeds_and_counts(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REFERENCE_NOW", "2026-10-11T10:00:00+10:00")
    monkeypatch.setenv("ADMIN_API_KEY", "change-me")

    counts = run_seed(database_url)
    assert counts["service_areas"] == 15
    assert counts["availability_slots"] == 22
    assert counts["pricing_rates"] == 6
    assert counts["pricing_config"] == 1
    assert counts["policies"] >= 6


def test_seed_idempotent_no_duplicates(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REFERENCE_NOW", "2026-10-11T10:00:00+10:00")
    monkeypatch.setenv("ADMIN_API_KEY", "change-me")

    first = run_seed(database_url)
    second = run_seed(database_url)
    assert first == second
    assert second["service_areas"] == 15
    assert second["availability_slots"] == 22
    assert second["pricing_rates"] == 6


def test_pricing_rows_match_appendix_json(database_url, monkeypatch, engine):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REFERENCE_NOW", "2026-10-11T10:00:00+10:00")
    monkeypatch.setenv("ADMIN_API_KEY", "change-me")
    run_seed(database_url)

    rules = load_business_rules()
    from app.db import make_session_factory

    session = make_session_factory(engine)()
    try:
        rows = session.scalars(select(PricingRate)).all()
        assert len(rows) == 6
        by_key = {(r.service_type, r.roof_material): r for r in rows}
        for rate in rules["pricing"]["rates"]:
            material = rate.get("roof_material")
            stored = by_key[(rate["service_type"], material)]
            assert stored.low_rate == rate["low_rate"]
            assert stored.high_rate == rate["high_rate"]
            assert stored.unit == rate["unit"]
            assert stored.quantity_field == rate.get("quantity_field")

        config = session.get(PricingConfig, 1)
        assert config is not None
        assert config.storey_multiplier == 1.15
        assert config.steep_pitch_multiplier == 1.10
        assert config.combined_multiplier == 1.265
        assert config.minimum_job_charge_aud == 1500
        assert config.rounding_nearest_aud == 50
        assert config.rounding_half == "up"
        assert config.roof_restoration_requires_roof_material is True
    finally:
        session.close()


def test_important_policies_exist(database_url, monkeypatch, engine):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REFERENCE_NOW", "2026-10-11T10:00:00+10:00")
    monkeypatch.setenv("ADMIN_API_KEY", "change-me")
    run_seed(database_url)

    from app.db import make_session_factory

    session = make_session_factory(engine)()
    try:
        for topic in (
            "office_hours",
            "emergency",
            "services_offered",
            "services_not_offered",
            "quote_policy",
            "warranty_policy",
            "insurance_policy",
        ):
            row = session.get(PolicyRecord, topic)
            assert row is not None, topic
            content = json.loads(row.content_json)
            assert content is not None

        emergency = json.loads(session.get(PolicyRecord, "emergency").content_json)
        assert emergency["phone_display"] == "0491 570 110"
        warranty = json.loads(session.get(PolicyRecord, "warranty_policy").content_json)
        assert warranty["workmanship_restorations_years"] == 7
        assert warranty["workmanship_replacements_years"] == 10
    finally:
        session.close()


def test_normal_seed_preserves_runtime_slot_mutation(database_url, monkeypatch, engine):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REFERENCE_NOW", "2026-10-11T10:00:00+10:00")
    monkeypatch.setenv("ADMIN_API_KEY", "change-me")
    run_seed(database_url)

    from app.db import make_session_factory

    session = make_session_factory(engine)()
    try:
        slot = session.get(AvailabilitySlot, "2026-10-16T07:00")
        assert slot is not None
        assert slot.status == "free"
        slot.status = "booked"
        session.commit()
    finally:
        session.close()

    run_seed(database_url)  # normal idempotent seed must not reset

    session = make_session_factory(engine)()
    try:
        slot = session.get(AvailabilitySlot, "2026-10-16T07:00")
        assert slot.status == "booked"
        assert session.scalar(select(func.count()).select_from(AvailabilitySlot)) == 22
        assert session.scalar(select(func.count()).select_from(ServiceArea)) == 15
    finally:
        session.close()


def test_explicit_reset_restores_appendix_slot_state(database_url, monkeypatch, engine):
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REFERENCE_NOW", "2026-10-11T10:00:00+10:00")
    monkeypatch.setenv("ADMIN_API_KEY", "change-me")
    run_seed(database_url)

    from app.db import make_session_factory

    session = make_session_factory(engine)()
    try:
        session.get(AvailabilitySlot, "2026-10-16T07:00").status = "booked"
        session.commit()
    finally:
        session.close()

    counts = run_seed(database_url, reset=True)
    assert counts["availability_slots"] == 22

    session = make_session_factory(engine)()
    try:
        assert session.get(AvailabilitySlot, "2026-10-16T07:00").status == "free"
        assert session.get(AvailabilitySlot, "2026-10-12T07:00").status == "booked"
    finally:
        session.close()
