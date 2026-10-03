from app.tools.availability import (
    SlotRequestOutcome,
    find_nearest_free_slots,
    get_slot,
    inspect_slot_request,
)


def test_exact_free_slot(seeded_session):
    view = get_slot(seeded_session, "2026-10-16T07:00")
    assert view is not None
    assert view.status == "free"
    inspection = inspect_slot_request(seeded_session, "2026-10-16T07:00")
    assert inspection.exists is True
    assert inspection.bookable is True
    assert inspection.outcome is SlotRequestOutcome.free


def test_exact_booked_slot_priya_k(seeded_session):
    view = get_slot(seeded_session, "2026-10-13T09:00")
    assert view is not None
    assert view.status == "booked"
    inspection = inspect_slot_request(seeded_session, "2026-10-13T09:00")
    assert inspection.exists is True
    assert inspection.bookable is False
    assert inspection.outcome is SlotRequestOutcome.booked


def test_nonexistent_slot(seeded_session):
    assert get_slot(seeded_session, "2026-10-16T09:30") is None
    inspection = inspect_slot_request(seeded_session, "2026-10-16T09:30")
    assert inspection.exists is False
    assert inspection.outcome is SlotRequestOutcome.not_found
    assert inspection.bookable is False


def test_chris_sunday_not_bookable(seeded_session):
    inspection = inspect_slot_request(seeded_session, "2026-10-18T09:00")
    assert inspection.exists is False
    assert inspection.is_sunday is True
    assert inspection.bookable is False
    assert inspection.outcome is SlotRequestOutcome.sunday


def test_past_relative_to_reference_now(seeded_session):
    # REFERENCE_NOW is 2026-10-11; invent a parseable past id that is not in Appendix D.
    inspection = inspect_slot_request(seeded_session, "2026-10-10T09:00")
    assert inspection.exists is False
    assert inspection.is_past is True
    assert inspection.bookable is False
    assert inspection.outcome is SlotRequestOutcome.in_past


def test_alternatives_only_explicit_free_valid_slots(seeded_session):
    alts = find_nearest_free_slots(seeded_session, "2026-10-18T09:00", limit=3)
    assert len(alts) <= 3
    for slot in alts:
        assert slot.status == "free"
        assert get_slot(seeded_session, slot.slot_id) is not None
        assert slot.starts_at.weekday() != 6
        assert inspect_slot_request(seeded_session, slot.slot_id).bookable is True


def test_alternatives_deterministic_and_at_most_three(seeded_session):
    first = [s.slot_id for s in find_nearest_free_slots(seeded_session, "2026-10-13T09:00")]
    second = [s.slot_id for s in find_nearest_free_slots(seeded_session, "2026-10-13T09:00")]
    assert first == second
    assert len(first) <= 3


def test_chris_alternatives(seeded_session):
    alts = find_nearest_free_slots(seeded_session, "2026-10-18T09:00")
    assert len(alts) == 3
    # Nearest free valid slots after/around Sunday 18 Oct 09:00 should be from Sat 17.
    ids = [s.slot_id for s in alts]
    assert "2026-10-17T08:00" in ids
    assert all(i.startswith("2026-10-") for i in ids)


def test_priya_k_alternatives_for_booked_slot(seeded_session):
    alts = find_nearest_free_slots(seeded_session, "2026-10-13T09:00")
    ids = [s.slot_id for s in alts]
    assert len(ids) == 3
    assert "2026-10-13T09:00" not in ids
    # Same-day free neighbours should rank highly.
    assert "2026-10-13T07:00" in ids
    assert "2026-10-13T11:00" in ids


def test_availability_helpers_do_not_mutate(seeded_session):
    before = get_slot(seeded_session, "2026-10-16T11:00")
    find_nearest_free_slots(seeded_session, "2026-10-16T11:00")
    inspect_slot_request(seeded_session, "2026-10-16T11:00")
    after = get_slot(seeded_session, "2026-10-16T11:00")
    assert before is not None and after is not None
    assert before.status == after.status == "free"
