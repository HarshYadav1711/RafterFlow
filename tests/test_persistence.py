from sqlalchemy import select

from app.clock import reference_now
from app.models import Channel, Lead, LeadStatus, Message, MessageDirection, Urgency
from app.schemas import Lead as LeadSchema


def test_create_and_retrieve_lead(session):
    lead = Lead(
        phone="+61491570157",
        name="Priya",
        channel=Channel.whatsapp.value,
        urgency=Urgency.standard.value,
        status=LeadStatus.new.value,
    )
    session.add(lead)
    session.commit()

    loaded = session.get(Lead, lead.lead_id)
    assert loaded is not None
    assert loaded.phone == "+61491570157"
    assert loaded.created_at == reference_now()
    assert loaded.updated_at.tzinfo is not None

    schema = LeadSchema.model_validate(loaded)
    assert schema.lead_id == lead.lead_id
    assert schema.channel.value == "whatsapp"


def test_lookup_by_phone(session):
    session.add(
        Lead(
            phone="+61491571491",
            name="Aisha",
            channel=Channel.whatsapp.value,
        )
    )
    session.commit()

    found = session.scalar(select(Lead).where(Lead.phone == "+61491571491"))
    assert found is not None
    assert found.name == "Aisha"


def test_update_lead_does_not_create_second_row(session):
    lead = Lead(phone="+61491570158", name="Mark", channel=Channel.whatsapp.value)
    session.add(lead)
    session.commit()

    lead.postcode = "4066"
    lead.suburb = "Toowong"
    lead.status = LeadStatus.awaiting_info.value
    lead.updated_at = reference_now()
    session.commit()

    rows = session.scalars(select(Lead).where(Lead.phone == "+61491570158")).all()
    assert len(rows) == 1
    assert rows[0].postcode == "4066"
    assert rows[0].status == LeadStatus.awaiting_info.value


def test_messages_associate_with_correct_lead(session):
    lead = Lead(phone="+61490000001", channel=Channel.whatsapp.value)
    session.add(lead)
    session.flush()

    inbound = Message(
        lead_id=lead.lead_id,
        direction=MessageDirection.inbound.value,
        channel=Channel.whatsapp.value,
        body="Hi, restore my roof",
        created_at=reference_now(),
    )
    outbound = Message(
        lead_id=lead.lead_id,
        direction=MessageDirection.outbound.value,
        channel=Channel.whatsapp.value,
        body="Thanks — what is your postcode?",
        created_at=reference_now(),
    )
    session.add_all([inbound, outbound])
    session.commit()

    session.refresh(lead)
    assert len(lead.messages) == 2
    bodies = {m.body for m in lead.messages}
    assert "Hi, restore my roof" in bodies


def test_message_isolation_between_leads(session):
    a = Lead(phone="+61490000002", channel=Channel.whatsapp.value)
    b = Lead(phone="+61490000003", channel=Channel.web_form.value)
    session.add_all([a, b])
    session.flush()

    session.add_all(
        [
            Message(
                lead_id=a.lead_id,
                direction=MessageDirection.inbound.value,
                body="Message for A",
            ),
            Message(
                lead_id=b.lead_id,
                direction=MessageDirection.inbound.value,
                body="Message for B",
            ),
        ]
    )
    session.commit()

    session.refresh(a)
    session.refresh(b)
    assert [m.body for m in a.messages] == ["Message for A"]
    assert [m.body for m in b.messages] == ["Message for B"]
