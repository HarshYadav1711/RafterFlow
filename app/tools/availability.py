"""Read-only availability helpers against seeded Appendix D slots. No booking mutation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import reference_now
from app.models import AvailabilitySlot, SlotStatus

# Assessment: Australia/Brisbane is UTC+10 with no daylight saving.
BRISBANE = timezone(timedelta(hours=10))


class SlotRequestOutcome(str, Enum):
    free = "free"
    booked = "booked"
    not_found = "not_found"
    sunday = "sunday"
    in_past = "in_past"


@dataclass(frozen=True, slots=True)
class SlotView:
    slot_id: str
    status: str
    starts_at: datetime


@dataclass(frozen=True, slots=True)
class SlotInspection:
    requested_slot_id: str
    exists: bool
    status: str | None
    starts_at: datetime | None
    is_sunday: bool
    is_past: bool
    is_free: bool
    bookable: bool
    outcome: SlotRequestOutcome


def parse_slot_id(slot_id: str) -> datetime | None:
    """Parse YYYY-MM-DDTHH:MM as Brisbane-local time. Returns None if malformed."""
    try:
        date_part, time_part = slot_id.split("T", 1)
        year, month, day = (int(p) for p in date_part.split("-"))
        hour, minute = (int(p) for p in time_part.split(":"))
        return datetime(year, month, day, hour, minute, tzinfo=BRISBANE)
    except (ValueError, TypeError):
        return None


def _is_sunday(when: datetime) -> bool:
    return when.weekday() == 6  # Monday=0 … Sunday=6


def _is_past(when: datetime, now: datetime) -> bool:
    return when < now


def get_slot(session: Session, slot_id: str) -> SlotView | None:
    row = session.get(AvailabilitySlot, slot_id)
    if row is None:
        return None
    starts = parse_slot_id(row.slot_id)
    if starts is None:
        raise RuntimeError(f"Stored slot_id is malformed: {row.slot_id!r}")
    return SlotView(slot_id=row.slot_id, status=row.status, starts_at=starts)


def inspect_slot_request(session: Session, slot_id: str) -> SlotInspection:
    """
    Classify a requested slot without mutating state.
    Only Appendix D rows exist; Sunday / past are never bookable.
    """
    now = reference_now()
    starts = parse_slot_id(slot_id)
    sunday = bool(starts and _is_sunday(starts))
    past = bool(starts and _is_past(starts, now))

    row = session.get(AvailabilitySlot, slot_id)
    if row is None:
        if sunday:
            outcome = SlotRequestOutcome.sunday
        elif starts is not None and past:
            outcome = SlotRequestOutcome.in_past
        else:
            outcome = SlotRequestOutcome.not_found
        return SlotInspection(
            requested_slot_id=slot_id,
            exists=False,
            status=None,
            starts_at=starts,
            is_sunday=sunday,
            is_past=past if starts is not None else False,
            is_free=False,
            bookable=False,
            outcome=outcome,
        )

    assert starts is not None
    is_free = row.status == SlotStatus.free.value
    # Existing Appendix D rows are Mon–Sat only; still apply past/sunday checks.
    if sunday:
        outcome = SlotRequestOutcome.sunday
        bookable = False
    elif past:
        outcome = SlotRequestOutcome.in_past
        bookable = False
    elif is_free:
        outcome = SlotRequestOutcome.free
        bookable = True
    else:
        outcome = SlotRequestOutcome.booked
        bookable = False

    return SlotInspection(
        requested_slot_id=slot_id,
        exists=True,
        status=row.status,
        starts_at=starts,
        is_sunday=sunday,
        is_past=past,
        is_free=is_free,
        bookable=bookable,
        outcome=outcome,
    )


def find_nearest_free_slots(
    session: Session,
    requested_slot_id: str,
    *,
    limit: int = 3,
) -> list[SlotView]:
    """
    Return up to `limit` nearest valid free alternatives.

    Deterministic assumption (documented in README):
    - only existing free slots that are not Sunday and not before REFERENCE_NOW;
    - sort by absolute temporal distance from the requested datetime;
    - if distances tie, prefer the later slot;
    - return at most three.
    """
    if limit < 0:
        raise ValueError("limit must be >= 0")

    requested_at = parse_slot_id(requested_slot_id)
    if requested_at is None:
        # Fall back to REFERENCE_NOW as the distance anchor when the request is unparseable.
        requested_at = reference_now()

    now = reference_now()
    candidates: list[tuple[timedelta, datetime, SlotView]] = []

    rows = session.scalars(select(AvailabilitySlot)).all()
    for row in rows:
        if row.status != SlotStatus.free.value:
            continue
        starts = parse_slot_id(row.slot_id)
        if starts is None:
            continue
        if _is_sunday(starts) or _is_past(starts, now):
            continue
        view = SlotView(slot_id=row.slot_id, status=row.status, starts_at=starts)
        distance = abs(starts - requested_at)
        candidates.append((distance, starts, view))

    # Sort by absolute distance, then later slot on ties.
    candidates.sort(key=lambda item: (item[0], -item[1].timestamp()))
    return [view for _, _, view in candidates[:limit]]
