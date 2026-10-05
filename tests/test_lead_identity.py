"""Lead identity / phone uniqueness behaviour."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.agent.orchestrator import get_or_create_lead
from app.models import Channel, Lead, LeadStatus
from app.schemas import Channel as ChannelEnum
from app.schemas import EnquiryRequest


AEST = timezone(timedelta(hours=10))
NOW = datetime(2026, 10, 11, 10, 0, 0, tzinfo=AEST)


def test_get_or_create_lead_reuses_existing_phone(seeded_session):
    seeded_session.add(
        Lead(
            phone="+61491571491",
            name="Aisha",
            channel=Channel.whatsapp.value,
            status=LeadStatus.awaiting_info.value,
        )
    )
    seeded_session.commit()

    req = EnquiryRequest(
        channel=ChannelEnum.whatsapp,
        from_phone="+61491571491",
        from_name="Aisha",
        message="It's around 120 sqm, single level, postcode 4066.",
        received_at=NOW,
    )
    lead = get_or_create_lead(seeded_session, req)
    seeded_session.flush()
    assert lead.phone == "+61491571491"
    assert lead.name == "Aisha"
    assert lead.status == LeadStatus.awaiting_info.value
