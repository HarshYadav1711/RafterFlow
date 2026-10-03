from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas import EnquiryResponse, Lead, LeadStatus, ToolCall, Urgency

AEST = timezone(timedelta(hours=10))
NOW = datetime(2026, 10, 11, 10, 0, 0, tzinfo=AEST)


def _minimal_lead(**overrides):
    data = dict(
        lead_id="00000000-0000-0000-0000-000000000001",
        phone="+61491570157",
        name=None,
        channel="whatsapp",
        service_type=None,
        roof_material=None,
        storeys=None,
        steep_pitch=None,
        size_m2=None,
        gutter_length_m=None,
        postcode=None,
        suburb=None,
        urgency="standard",
        status="new",
        quote_low=None,
        quote_high=None,
        booked_slot_id=None,
        created_at=NOW,
        updated_at=NOW,
    )
    data.update(overrides)
    return Lead(**data)


def test_appendix_a_nullable_fields_can_remain_null():
    lead = _minimal_lead()
    assert lead.name is None
    assert lead.service_type is None
    assert lead.roof_material is None
    assert lead.storeys is None
    assert lead.steep_pitch is None
    assert lead.size_m2 is None
    assert lead.gutter_length_m is None
    assert lead.postcode is None
    assert lead.suburb is None
    assert lead.quote_low is None
    assert lead.quote_high is None
    assert lead.booked_slot_id is None


def test_allowed_enums_work():
    lead = _minimal_lead(
        service_type="roof_restoration",
        roof_material="tile",
        urgency="emergency",
        status="awaiting_info",
    )
    assert lead.service_type.value == "roof_restoration"
    assert lead.roof_material.value == "tile"
    assert lead.urgency is Urgency.emergency
    assert lead.status is LeadStatus.awaiting_info


def test_invented_status_rejected():
    with pytest.raises(ValidationError):
        _minimal_lead(status="qualified")


def test_invented_service_type_rejected():
    with pytest.raises(ValidationError):
        _minimal_lead(service_type="solar_install")


def test_enquiry_response_contract_shape():
    response = EnquiryResponse(
        reply="Thanks — we will need your postcode.",
        lead=_minimal_lead(status="awaiting_info"),
        tool_calls=[
            ToolCall(
                tool="check_service_area",
                args={"postcode": "4064"},
                result={"in_area": True},
            )
        ],
    )
    assert response.tool_calls[0].tool == "check_service_area"
    assert response.lead.status is LeadStatus.awaiting_info
