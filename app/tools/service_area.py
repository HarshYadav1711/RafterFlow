"""Deterministic service-area check against seeded Appendix B data."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import ServiceArea


@dataclass(frozen=True, slots=True)
class ServiceAreaResult:
    postcode: str
    in_area: bool
    canonical_suburb: str | None


def check_service_area(session: Session, postcode: str) -> ServiceAreaResult:
    """Exact postcode lookup only. Suburb text never decides area."""
    normalised = postcode.strip()
    row = session.get(ServiceArea, normalised)
    if row is None:
        return ServiceAreaResult(postcode=normalised, in_area=False, canonical_suburb=None)
    return ServiceAreaResult(
        postcode=row.postcode,
        in_area=True,
        canonical_suburb=row.suburb,
    )
