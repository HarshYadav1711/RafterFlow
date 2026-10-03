"""Deterministic inspection booking with atomic free→booked transition."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.clock import reference_now
from app.models import AvailabilitySlot, Lead, LeadStatus, SlotStatus
from app.tools.availability import (
    SlotRequestOutcome,
    find_nearest_free_slots,
    inspect_slot_request,
    parse_slot_id,
)


class BookingOutcome(str, Enum):
    booked = "booked"
    unavailable = "unavailable"
    not_found = "not_found"
    sunday = "sunday"
    in_past = "in_past"
    malformed = "malformed"


@dataclass(frozen=True, slots=True)
class BookingResult:
    outcome: BookingOutcome
    requested_slot_id: str
    booked_slot_id: str | None = None
    alternatives: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    message: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "requested_slot_id": self.requested_slot_id,
            "booked_slot_id": self.booked_slot_id,
            "alternatives": list(self.alternatives),
            "message": self.message,
        }


def _alternative_dicts(session: Session, slot_id: str) -> tuple[dict[str, Any], ...]:
    alts = find_nearest_free_slots(session, slot_id, limit=3)
    return tuple(
        {
            "slot_id": a.slot_id,
            "starts_at": a.starts_at.isoformat(),
            "status": a.status,
        }
        for a in alts
    )


def book_inspection(session: Session, lead: Lead, slot_id: str) -> BookingResult:
    """
    Atomically book an Appendix D slot for the lead.

    Concurrency: UPDATE ... WHERE status='free' so exactly one waiter wins.
    Validates existence / Sunday / past independently of the LLM.
    """
    requested = (slot_id or "").strip()
    if not requested or parse_slot_id(requested) is None:
        return BookingResult(
            outcome=BookingOutcome.malformed,
            requested_slot_id=requested,
            alternatives=_alternative_dicts(session, requested or "2026-10-12T11:00"),
            message="Slot id must be YYYY-MM-DDTHH:MM in Brisbane time.",
        )

    inspection = inspect_slot_request(session, requested)
    if inspection.outcome is SlotRequestOutcome.sunday:
        return BookingResult(
            outcome=BookingOutcome.sunday,
            requested_slot_id=requested,
            alternatives=_alternative_dicts(session, requested),
            message="Sunday inspections are not available.",
        )
    if inspection.outcome is SlotRequestOutcome.in_past:
        return BookingResult(
            outcome=BookingOutcome.in_past,
            requested_slot_id=requested,
            alternatives=_alternative_dicts(session, requested),
            message="That time is in the past.",
        )
    if inspection.outcome is SlotRequestOutcome.not_found:
        return BookingResult(
            outcome=BookingOutcome.not_found,
            requested_slot_id=requested,
            alternatives=_alternative_dicts(session, requested),
            message="That inspection slot does not exist.",
        )
    if inspection.outcome is SlotRequestOutcome.booked:
        return BookingResult(
            outcome=BookingOutcome.unavailable,
            requested_slot_id=requested,
            alternatives=_alternative_dicts(session, requested),
            message="That inspection slot is already booked.",
        )

    # Atomic conditional update — do not check-then-write in Python.
    result = session.execute(
        update(AvailabilitySlot)
        .where(
            AvailabilitySlot.slot_id == requested,
            AvailabilitySlot.status == SlotStatus.free.value,
        )
        .values(
            status=SlotStatus.booked.value,
            booked_lead_id=lead.lead_id,
        )
    )
    if result.rowcount != 1:
        # Lost the race or state changed under us.
        return BookingResult(
            outcome=BookingOutcome.unavailable,
            requested_slot_id=requested,
            alternatives=_alternative_dicts(session, requested),
            message="That inspection slot is no longer available.",
        )

    lead.booked_slot_id = requested
    lead.status = LeadStatus.inspection_booked.value
    lead.updated_at = reference_now()
    session.flush()

    return BookingResult(
        outcome=BookingOutcome.booked,
        requested_slot_id=requested,
        booked_slot_id=requested,
        alternatives=(),
        message="Inspection booked.",
    )
