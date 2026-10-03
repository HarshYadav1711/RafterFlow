"""Seed appendix reference data from data/business_rules.json into SQLite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import Base, create_schema, make_engine, session_scope
from app.models import (
    AvailabilitySlot,
    PolicyRecord,
    PricingConfig,
    PricingRate,
    ServiceArea,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_PATH = ROOT / "data" / "business_rules.json"
PRICING_CONFIG_ID = 1


def load_business_rules(path: Path | None = None) -> dict[str, Any]:
    rules_path = path or DEFAULT_RULES_PATH
    with rules_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _material_key(roof_material: str | None) -> str:
    return roof_material or ""


def seed_service_areas(session: Session, rules: dict[str, Any]) -> None:
    for entry in rules["service_area"]:
        existing = session.get(ServiceArea, entry["postcode"])
        if existing is None:
            session.add(ServiceArea(postcode=entry["postcode"], suburb=entry["suburb"]))
        else:
            # Reference data may be corrected in JSON; suburb is not runtime state.
            existing.suburb = entry["suburb"]


def seed_pricing_rates(session: Session, rules: dict[str, Any]) -> None:
    for rate in rules["pricing"]["rates"]:
        material = rate.get("roof_material")
        key = _material_key(material)
        existing = session.scalar(
            select(PricingRate).where(
                PricingRate.service_type == rate["service_type"],
                PricingRate.roof_material_key == key,
            )
        )
        values = dict(
            service_type=rate["service_type"],
            roof_material_key=key,
            roof_material=material,
            unit=rate["unit"],
            low_rate=rate["low_rate"],
            high_rate=rate["high_rate"],
            quantity_field=rate.get("quantity_field"),
            notes=rate.get("notes"),
        )
        if existing is None:
            session.add(PricingRate(**values))
        else:
            for field, value in values.items():
                setattr(existing, field, value)


def seed_pricing_config(session: Session, rules: dict[str, Any]) -> None:
    pricing = rules["pricing"]
    multipliers = pricing["multipliers"]
    defaults = pricing["defaults_when_unknown"]
    rounding = pricing["rounding"]
    minimum = pricing["minimum_job_charge"]

    payload = dict(
        id=PRICING_CONFIG_ID,
        currency=pricing["currency"],
        includes_gst=pricing["includes_gst"],
        storey_multiplier=multipliers["two_or_more_storeys"],
        steep_pitch_multiplier=multipliers["steep_pitch"],
        combined_multiplier=multipliers["combined_when_both_apply"],
        multiplier_service_types_json=json.dumps(multipliers["applies_to_service_types"]),
        default_storeys=defaults["storeys"],
        default_steep_pitch=defaults["steep_pitch"],
        must_state_assumption=defaults["must_state_assumption_in_reply"],
        rounding_nearest_aud=rounding["nearest_aud"],
        rounding_half=rounding["half_rounds"],
        minimum_job_charge_aud=minimum["amount_aud"],
        minimum_charge_service_types_json=json.dumps(minimum["applies_to_service_types"]),
        minimum_both_ends_display=minimum["both_ends_at_minimum_display"],
        roof_restoration_requires_roof_material=pricing["roof_restoration_requires_roof_material"],
        estimate_wording_json=json.dumps(pricing["estimate_wording"]),
        calculation_order_json=json.dumps(pricing["calculation_order"]),
        worked_example_json=json.dumps(pricing["worked_example"]),
    )

    existing = session.get(PricingConfig, PRICING_CONFIG_ID)
    if existing is None:
        session.add(PricingConfig(**payload))
    else:
        for key, value in payload.items():
            if key != "id":
                setattr(existing, key, value)


def seed_availability(session: Session, rules: dict[str, Any]) -> None:
    """Insert missing Appendix D slots only. Never rewrite existing status/bookings."""
    for day, times in rules["availability"]["slots"].items():
        for time_label, status in times.items():
            slot_id = f"{day}T{time_label}"
            if session.get(AvailabilitySlot, slot_id) is None:
                session.add(
                    AvailabilitySlot(
                        slot_id=slot_id,
                        slot_date=day,
                        slot_time=time_label,
                        status=status,
                        booked_lead_id=None,
                    )
                )


def seed_policies(session: Session, rules: dict[str, Any]) -> None:
    policies = rules["policies"]
    topics: dict[str, Any] = {
        "business": rules["business"],
        "office_hours": policies["office_hours"],
        "emergency": policies["emergency"],
        "services_offered": policies["services_offered"],
        "services_not_offered": policies["services_not_offered"],
        "quote_policy": policies["quote_policy"],
        "warranty_policy": policies["warranty_policy"],
        "insurance_policy": policies["insurance_policy"],
    }
    for topic, content in topics.items():
        content_json = json.dumps(content)
        existing = session.get(PolicyRecord, topic)
        if existing is None:
            session.add(PolicyRecord(topic=topic, content_json=content_json))
        else:
            existing.content_json = content_json


def seed_all(session: Session, rules: dict[str, Any]) -> None:
    seed_service_areas(session, rules)
    seed_pricing_rates(session, rules)
    seed_pricing_config(session, rules)
    seed_policies(session, rules)
    seed_availability(session, rules)


def count_seed_rows(session: Session) -> dict[str, int]:
    return {
        "service_areas": session.scalar(select(func.count()).select_from(ServiceArea)) or 0,
        "pricing_rates": session.scalar(select(func.count()).select_from(PricingRate)) or 0,
        "pricing_config": session.scalar(select(func.count()).select_from(PricingConfig)) or 0,
        "availability_slots": session.scalar(select(func.count()).select_from(AvailabilitySlot)) or 0,
        "policies": session.scalar(select(func.count()).select_from(PolicyRecord)) or 0,
    }


def reset_database(engine: Engine) -> None:
    """Explicit eval/test reset: wipe schema and recreate empty tables."""
    Base.metadata.drop_all(bind=engine)
    create_schema(engine)


def clear_availability_to_appendix(session: Session, rules: dict[str, Any]) -> None:
    """Optional helper: replace slot rows with Appendix D baseline (does not drop leads)."""
    session.execute(delete(AvailabilitySlot))
    session.flush()
    for day, times in rules["availability"]["slots"].items():
        for time_label, status in times.items():
            session.add(
                AvailabilitySlot(
                    slot_id=f"{day}T{time_label}",
                    slot_date=day,
                    slot_time=time_label,
                    status=status,
                    booked_lead_id=None,
                )
            )


def run_seed(
    database_url: str | None = None,
    *,
    rules_path: Path | None = None,
    reset: bool = False,
) -> dict[str, int]:
    """
    Initialise schema and seed reference data from business_rules.json.

    Normal seed (reset=False):
      - create missing tables
      - insert missing reference rows
      - never change existing availability status (runtime booking state is preserved)

    Explicit reset (reset=True):
      - drop and recreate all tables
      - seed Appendix baseline, including initial free/booked slot states
    """
    engine = make_engine(database_url)
    rules = load_business_rules(rules_path)

    if reset:
        reset_database(engine)
    else:
        create_schema(engine)

    with session_scope(engine) as session:
        seed_all(session, rules)
        session.flush()
        return count_seed_rows(session)
