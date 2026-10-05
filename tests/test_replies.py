"""Deterministic reply composition edge cases."""

from __future__ import annotations

from app.agent.replies import _ask_for, compose_reply
from app.agent.turn import TurnState
from app.models import Channel, Lead, LeadStatus, Urgency


def _lead(**kwargs) -> Lead:
    defaults = {
        "phone": "+61491887700",
        "name": "Casey",
        "channel": Channel.whatsapp.value,
        "status": LeadStatus.awaiting_info.value,
        "urgency": Urgency.standard.value,
    }
    defaults.update(kwargs)
    return Lead(**defaults)


def test_ask_for_empty_list_does_not_crash():
    text = _ask_for([])
    assert "share" in text.lower() or "details" in text.lower()
    assert text  # non-empty


def test_awaiting_info_with_no_missing_essentials_does_not_500():
    """
    Regression: finalize can set awaiting_info when essentials are already
    complete but no quote was produced this turn. Reply composition must not
    IndexError inside _ask_for([]).
    """
    lead = _lead(
        service_type="roof_restoration",
        roof_material="tile",
        size_m2=180,
        storeys=1,
        postcode="4064",
        status=LeadStatus.awaiting_info.value,
    )
    reply = compose_reply(lead, TurnState())
    assert isinstance(reply, str)
    assert len(reply) > 0
    assert "tile" in reply.lower() or "details" in reply.lower()


def test_out_of_area_reply_has_no_unsourced_geography():
    lead = _lead(
        postcode="4300",
        status=LeadStatus.out_of_area.value,
    )
    reply = compose_reply(lead, TurnState(out_of_area=True))
    lower = reply.lower()
    assert "4300" in reply
    assert "inner brisbane" not in lower
    assert "brisbane" not in lower
    assert "price" in lower
    assert "inspection" in lower


def test_quote_policy_reply_states_estimates_never_guaranteed():
    lead = _lead(name="Casey", status=LeadStatus.new.value)
    turn = TurnState()
    turn.policies["quote_policy"] = (
        "Free inspection, then a written quote within 48 hours. "
        "Online figures are estimates only and are never guaranteed."
    )
    turn.policies["warranty_policy"] = {
        "workmanship_restorations_years": 7,
        "workmanship_replacements_years": 10,
        "colorbond_material_warranty": "provided by the manufacturer",
        "no_other_warranty_may_be_promised": True,
    }
    reply = compose_reply(lead, turn).lower()
    assert "estimates" in reply
    assert "never guaranteed" in reply
    assert "free inspection" in reply
    assert "written quote" in reply
    assert "48" in reply
    assert "7" in reply and "10" in reply
