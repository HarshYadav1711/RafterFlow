"""Bounded agent loop + deterministic finalisation for POST /enquiries."""

from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.missing import missing_essential_fields
from app.agent.prompts import SYSTEM_PROMPT, lead_context_block
from app.agent.replies import compose_reply
from app.agent.tools_runtime import TOOL_DEFINITIONS, execute_tool
from app.agent.turn import TurnState
from app.audit import write_enquiry_audit
from app.clock import reference_now
from app.llm import LLMClient, LLMResponse
from app.models import Lead, LeadStatus, Message, MessageDirection, Urgency
from app.schemas import EnquiryRequest, EnquiryResponse, Lead as LeadSchema, ToolCall

MAX_ROUNDS = 6


def _lead_snapshot(lead: Lead) -> dict[str, Any]:
    return {
        "lead_id": lead.lead_id,
        "phone": lead.phone,
        "name": lead.name,
        "channel": lead.channel,
        "service_type": lead.service_type,
        "roof_material": lead.roof_material,
        "storeys": lead.storeys,
        "steep_pitch": lead.steep_pitch,
        "size_m2": lead.size_m2,
        "gutter_length_m": lead.gutter_length_m,
        "postcode": lead.postcode,
        "suburb": lead.suburb,
        "urgency": lead.urgency,
        "status": lead.status,
        "quote_low": lead.quote_low,
        "quote_high": lead.quote_high,
    }


def _conversation_messages(session: Session, lead: Lead) -> list[Message]:
    return list(
        session.scalars(
            select(Message)
            .where(Message.lead_id == lead.lead_id)
            .order_by(Message.created_at.asc(), Message.message_id.asc())
        ).all()
    )


def get_or_create_lead(session: Session, request: EnquiryRequest) -> Lead:
    lead = session.scalar(select(Lead).where(Lead.phone == request.from_phone))
    if lead is None:
        lead = Lead(
            phone=request.from_phone,
            name=request.from_name,
            channel=request.channel.value,
            urgency=Urgency.standard.value,
            status=LeadStatus.new.value,
            created_at=reference_now(),
            updated_at=reference_now(),
        )
        session.add(lead)
        session.flush()
        return lead

    if request.from_name:
        lead.name = request.from_name
    lead.channel = request.channel.value
    lead.updated_at = reference_now()
    return lead


def _build_llm_messages(
    lead: Lead,
    history: list[Message],
    inbound_text: str,
) -> list[dict[str, Any]]:
    """Privacy boundary: only this lead's record and conversation."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": lead_context_block(_lead_snapshot(lead))},
    ]
    for msg in history:
        role = "user" if msg.direction == MessageDirection.inbound.value else "assistant"
        messages.append({"role": role, "content": msg.body})
    messages.append({"role": "user", "content": inbound_text})
    return messages


def required_authoritative_tools(lead: Lead, turn: TurnState) -> list[str]:
    """
    Principal business tools that must be model-emitted for this turn to resolve.
    Finalisation must not execute these itself.
    """
    if turn.emergency or lead.status == LeadStatus.emergency.value:
        return []
    if turn.out_of_scope or lead.status == LeadStatus.out_of_scope.value:
        return []
    # Booking attempt (success or failure) resolves the booking path for this turn.
    if turn.booking is not None:
        return []
    if (
        ("warranty_policy" in turn.policies or "quote_policy" in turn.policies)
        and not lead.service_type
    ):
        return []
    if not lead.service_type and not lead.postcode and not turn.tool_calls:
        return []

    if lead.postcode and turn.area is None:
        return ["check_service_area"]

    if turn.out_of_area or (turn.area is not None and not turn.area.in_area):
        return []

    if missing_essential_fields(lead):
        return []

    if turn.pricing is None:
        return ["estimate_price"]
    return []


def _recovery_nudge(needed: list[str]) -> str:
    tools = ", ".join(needed)
    return (
        "An authoritative business decision for this turn is still unresolved. "
        "Do not answer from memory. Call the appropriate available tool(s) now: "
        f"{tools}."
    )


def finalize_business_state(session: Session, lead: Lead, turn: TurnState) -> None:
    """
    Enforce status precedence and validate tool outcomes.
    Must not invoke check_service_area / estimate_price / book_inspection itself.
    """
    del session  # session reserved for future persistence-only finalisation needs
    lead.updated_at = reference_now()

    if turn.emergency or lead.status == LeadStatus.emergency.value:
        lead.status = LeadStatus.emergency.value
        lead.urgency = Urgency.emergency.value
        lead.quote_low = None
        lead.quote_high = None
        return

    if turn.out_of_area or (turn.area is not None and not turn.area.in_area):
        lead.status = LeadStatus.out_of_area.value
        lead.quote_low = None
        lead.quote_high = None
        return

    if turn.out_of_scope or lead.status == LeadStatus.out_of_scope.value:
        lead.status = LeadStatus.out_of_scope.value
        lead.quote_low = None
        lead.quote_high = None
        return

    # Successful booking already mutated lead/slot in the booking tool.
    if turn.booking is not None and turn.booking.outcome.value == "booked":
        lead.status = LeadStatus.inspection_booked.value
        return

    if turn.unresolved_required_tools:
        # Fail safe: never invent area/price/booking results in Python.
        if missing_essential_fields(lead) and lead.booked_slot_id is None:
            lead.status = LeadStatus.awaiting_info.value
        return

    if (
        ("warranty_policy" in turn.policies or "quote_policy" in turn.policies)
        and not lead.service_type
    ):
        return

    if not lead.service_type and not lead.postcode and not turn.tool_calls:
        return

    # Failed booking attempt: do not set inspection_booked; keep prior quoted/new state.
    if turn.booking is not None:
        if turn.pricing is not None and turn.pricing.calculable:
            lead.quote_low = turn.pricing.low
            lead.quote_high = turn.pricing.high
            if lead.status != LeadStatus.inspection_booked.value:
                lead.status = LeadStatus.quoted.value
        return

    missing = missing_essential_fields(lead)
    if missing:
        lead.status = LeadStatus.awaiting_info.value
        return

    # Quote only when an authoritative estimate_price tool result exists.
    if turn.pricing is not None and turn.pricing.calculable:
        lead.quote_low = turn.pricing.low
        lead.quote_high = turn.pricing.high
        lead.status = LeadStatus.quoted.value
        return

    lead.status = LeadStatus.awaiting_info.value


def _append_assistant_and_execute(
    session: Session,
    lead: Lead,
    turn: TurnState,
    messages: list[dict[str, Any]],
    response: LLMResponse,
) -> None:
    messages.append(
        {
            "role": "assistant",
            "content": response.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in response.tool_calls
            ],
        }
    )
    for tc in response.tool_calls:
        result = execute_tool(session, lead, turn, tc.name, tc.arguments)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            }
        )
        if tc.name == "capture_lead_details":
            messages[1] = {
                "role": "system",
                "content": lead_context_block(_lead_snapshot(lead)),
            }


def run_agent_loop(
    session: Session,
    lead: Lead,
    llm_messages: list[dict[str, Any]],
    llm: LLMClient,
    turn: TurnState,
) -> None:
    messages = list(llm_messages)
    for _ in range(MAX_ROUNDS):
        response: LLMResponse = llm.complete(messages, TOOL_DEFINITIONS)

        if response.tool_calls:
            _append_assistant_and_execute(session, lead, turn, messages, response)
            if turn.emergency:
                return
            continue

        # Model attempted to finish without tool calls.
        needed = required_authoritative_tools(lead, turn)
        if not needed:
            return
        if turn.recovery_used:
            turn.unresolved_required_tools = needed
            return

        turn.recovery_used = True
        messages.append({"role": "system", "content": _recovery_nudge(needed)})
        # Continue within MAX_ROUNDS for the recovery completion.


def handle_enquiry(
    session: Session,
    request: EnquiryRequest,
    llm: LLMClient,
) -> EnquiryResponse:
    # Monotonic host timer for R10 latency only — business time still uses REFERENCE_NOW.
    started = time.perf_counter()

    lead = get_or_create_lead(session, request)

    inbound = Message(
        lead_id=lead.lead_id,
        direction=MessageDirection.inbound.value,
        channel=request.channel.value,
        body=request.message,
        created_at=request.received_at,
    )
    session.add(inbound)
    session.flush()

    history = [m for m in _conversation_messages(session, lead) if m.message_id != inbound.message_id]
    llm_messages = _build_llm_messages(lead, history, request.message)

    turn = TurnState()
    run_agent_loop(session, lead, llm_messages, llm, turn)
    finalize_business_state(session, lead, turn)

    reply = compose_reply(lead, turn)
    outbound = Message(
        lead_id=lead.lead_id,
        direction=MessageDirection.outbound.value,
        channel=request.channel.value,
        body=reply,
        created_at=reference_now(),
    )
    session.add(outbound)
    session.flush()

    response = EnquiryResponse(
        reply=reply,
        lead=LeadSchema.model_validate(lead),
        tool_calls=[ToolCall(**item) for item in turn.tool_calls],
    )

    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    write_enquiry_audit(
        lead_id=lead.lead_id,
        final_status=lead.status,
        tool_calls=list(turn.tool_calls),
        latency_ms=latency_ms,
    )
    return response
