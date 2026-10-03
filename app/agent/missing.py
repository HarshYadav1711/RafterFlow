"""Deterministic essential-field checks (R2 / Appendix C)."""

from __future__ import annotations

from app.models import Lead


def missing_essential_fields(lead: Lead) -> list[str]:
    """Return essential fields still needed for a normal quote path."""
    missing: list[str] = []
    if not lead.service_type:
        missing.append("service_type")
        return missing

    if not lead.postcode:
        missing.append("postcode")

    if lead.service_type == "roof_restoration":
        if not lead.roof_material:
            missing.append("roof_material")
        if lead.size_m2 is None:
            missing.append("size_m2")
    elif lead.service_type == "roof_replacement":
        if lead.size_m2 is None:
            missing.append("size_m2")
    elif lead.service_type == "gutter_replacement":
        if lead.gutter_length_m is None:
            missing.append("gutter_length_m")
    # leak_repair / inspection_only: no quantity

    return missing


def ready_for_pricing(lead: Lead) -> bool:
    return not missing_essential_fields(lead)
