"""Phase 4 booking mutation and concurrency."""

from __future__ import annotations

import threading

from sqlalchemy import select

from app.db import make_session_factory
from app.models import AvailabilitySlot, Channel, Lead, LeadStatus, SlotStatus
from app.tools.booking import BookingOutcome, book_inspection


def _lead(session, phone: str, name: str) -> Lead:
    lead = Lead(
        phone=phone,
        name=name,
        channel=Channel.whatsapp.value,
        postcode="4010",
        status=LeadStatus.new.value,
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead


def test_successful_booking(seeded_session):
    lead = _lead(seeded_session, "+61491110001", "Alex")
    result = book_inspection(seeded_session, lead, "2026-10-16T11:00")
    seeded_session.commit()

    assert result.outcome is BookingOutcome.booked
    assert result.booked_slot_id == "2026-10-16T11:00"
    assert lead.booked_slot_id == "2026-10-16T11:00"
    assert lead.status == LeadStatus.inspection_booked.value

    slot = seeded_session.get(AvailabilitySlot, "2026-10-16T11:00")
    assert slot is not None
    assert slot.status == SlotStatus.booked.value
    assert slot.booked_lead_id == lead.lead_id


def test_chris_sunday_cannot_be_booked(seeded_session):
    lead = _lead(seeded_session, "+61491572549", "Chris")
    before = {
        s.slot_id: s.status
        for s in seeded_session.scalars(select(AvailabilitySlot)).all()
    }
    result = book_inspection(seeded_session, lead, "2026-10-18T09:00")
    seeded_session.commit()

    assert result.outcome is BookingOutcome.sunday
    assert lead.booked_slot_id is None
    assert lead.status != LeadStatus.inspection_booked.value
    assert 1 <= len(result.alternatives) <= 3
    for alt in result.alternatives:
        slot = seeded_session.get(AvailabilitySlot, alt["slot_id"])
        assert slot is not None
        assert slot.status == SlotStatus.free.value
    after = {
        s.slot_id: s.status
        for s in seeded_session.scalars(select(AvailabilitySlot)).all()
    }
    assert before == after


def test_priya_k_occupied_slot_cannot_be_booked(seeded_session):
    lead = _lead(seeded_session, "+61491572665", "Priya K")
    slot = seeded_session.get(AvailabilitySlot, "2026-10-13T09:00")
    assert slot is not None
    assert slot.status == SlotStatus.booked.value
    prior_owner = slot.booked_lead_id

    result = book_inspection(seeded_session, lead, "2026-10-13T09:00")
    seeded_session.commit()

    assert result.outcome is BookingOutcome.unavailable
    assert lead.booked_slot_id is None
    assert lead.status != LeadStatus.inspection_booked.value
    seeded_session.refresh(slot)
    assert slot.status == SlotStatus.booked.value
    assert slot.booked_lead_id == prior_owner
    assert 1 <= len(result.alternatives) <= 3
    assert all(
        seeded_session.get(AvailabilitySlot, a["slot_id"]).status == SlotStatus.free.value
        for a in result.alternatives
    )


def test_concurrent_double_booking_one_winner(seeded_engine):
    factory = make_session_factory(seeded_engine)
    setup = factory()
    a = Lead(phone="+61491120001", name="A", channel=Channel.whatsapp.value)
    b = Lead(phone="+61491120002", name="B", channel=Channel.whatsapp.value)
    setup.add_all([a, b])
    setup.commit()
    lead_a_id, lead_b_id = a.lead_id, b.lead_id
    setup.close()

    slot_id = "2026-10-14T07:00"
    barrier = threading.Barrier(2)
    outcomes: dict[str, BookingOutcome] = {}
    errors: list[BaseException] = []

    def worker(lead_id: str, key: str) -> None:
        try:
            session = factory()
            lead = session.get(Lead, lead_id)
            assert lead is not None
            barrier.wait(timeout=5)
            result = book_inspection(session, lead, slot_id)
            session.commit()
            outcomes[key] = result.outcome
            session.close()
        except BaseException as exc:  # noqa: BLE001 — collect for assertion
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=(lead_a_id, "a"))
    t2 = threading.Thread(target=worker, args=(lead_b_id, "b"))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert errors == []
    assert set(outcomes.values()) == {BookingOutcome.booked, BookingOutcome.unavailable}

    verify = factory()
    slot = verify.get(AvailabilitySlot, slot_id)
    assert slot is not None
    assert slot.status == SlotStatus.booked.value
    winner = verify.get(Lead, slot.booked_lead_id)
    loser_id = lead_b_id if winner and winner.lead_id == lead_a_id else lead_a_id
    loser = verify.get(Lead, loser_id)
    assert winner is not None
    assert winner.booked_slot_id == slot_id
    assert winner.status == LeadStatus.inspection_booked.value
    assert loser is not None
    assert loser.booked_slot_id != slot_id
    assert loser.status != LeadStatus.inspection_booked.value
    verify.close()
