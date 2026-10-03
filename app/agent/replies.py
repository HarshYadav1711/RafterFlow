"""Deterministic Australian-English reply composition. No LLM prose."""

from __future__ import annotations

from typing import Any

from app.agent.missing import missing_essential_fields
from app.agent.turn import TurnState
from app.models import Lead, LeadStatus
from app.tools.availability import parse_slot_id
from app.tools.booking import BookingOutcome


def _name_prefix(lead: Lead) -> str:
    if lead.name:
        return f"Thanks {lead.name}."
    return "Thanks."


def _format_money(amount: int) -> str:
    return f"${amount:,}"


def _format_slot_safe(slot_id: str) -> str:
    """Human slot label in Brisbane-local time."""
    when = parse_slot_id(slot_id)
    if when is None:
        return slot_id
    day = when.day
    return when.strftime(f"%A {day} %B %Y at %H:%M")


def _ask_for(fields: list[str]) -> str:
    labels = {
        "service_type": "what service you need (restoration, replacement, gutters, leak repair, or inspection)",
        "postcode": "your postcode",
        "roof_material": "whether the roof is tile or metal",
        "size_m2": "the approximate roof size in square metres",
        "gutter_length_m": "the approximate gutter length in lineal metres",
    }
    readable = [labels.get(f, f) for f in fields]
    if len(readable) == 1:
        return f"Could you please share {readable[0]}?"
    if len(readable) == 2:
        return f"Could you please share {readable[0]} and {readable[1]}?"
    return "Could you please share " + ", ".join(readable[:-1]) + f", and {readable[-1]}?"


def compose_reply(lead: Lead, turn: TurnState) -> str:
    status = lead.status

    if status == LeadStatus.emergency.value or turn.emergency:
        phone = None
        emergency = turn.policies.get("emergency") or {}
        phone = emergency.get("phone_display", "0491 570 110")
        return (
            f"{_name_prefix(lead)} This sounds like an emergency. "
            f"Please call our 24/7 emergency line on {phone} now. "
            "We've also alerted the on-call team. "
            "We won't quote or book an inspection while this is treated as an emergency."
        )

    if status == LeadStatus.out_of_area.value or turn.out_of_area:
        return (
            f"{_name_prefix(lead)} Thanks for getting in touch. "
            f"Unfortunately we don't service postcode {lead.postcode} at the moment, "
            "so I can't provide a price or book an inspection. "
            "If you're near inner Brisbane and have another property postcode, send it through."
        )

    if status == LeadStatus.out_of_scope.value or turn.out_of_scope:
        not_offered = turn.policies.get("services_not_offered") or []
        requested = None
        for call in turn.tool_calls:
            if call["tool"] == "mark_out_of_scope":
                requested = call["args"].get("requested_service")
        # Asbestos referral only when policy/request mentions it.
        if requested and "asbestos" in requested.lower():
            return (
                f"{_name_prefix(lead)} We don't offer asbestos removal. "
                "Please contact a licensed asbestos removalist for that work. "
                "Happy to help with residential roofing services we do offer."
            )
        return (
            f"{_name_prefix(lead)} We don't install or supply that service. "
            "Summit Roofing focuses on residential roof restoration and replacement to Colorbond, "
            "gutter replacement, leak repair, and free roof inspections"
            + (
                f" — we don't offer things like {', '.join(not_offered[:3])}."
                if not_offered
                else "."
            )
        )

    if turn.unresolved_required_tools:
        return (
            f"{_name_prefix(lead)} I couldn't complete the required business checks for this request, "
            "so I won't provide a quote or service-area decision yet. "
            "Please send your message again and I'll continue from the details already on file."
        )

    if turn.booking is not None:
        booking = turn.booking
        if booking.outcome is BookingOutcome.booked and booking.booked_slot_id:
            when = _format_slot_safe(booking.booked_slot_id)
            return (
                f"{_name_prefix(lead)} You're booked for a free roof inspection on {when} "
                f"(Brisbane time). Your slot id is {booking.booked_slot_id}."
            )

        reason = {
            BookingOutcome.sunday: "we don't offer Sunday inspections",
            BookingOutcome.in_past: "that time is in the past",
            BookingOutcome.not_found: "that inspection slot isn't one we offer",
            BookingOutcome.unavailable: "that inspection slot isn't available",
            BookingOutcome.malformed: "that booking time wasn't recognised",
        }.get(booking.outcome, "that inspection slot isn't available")

        alts = booking.alternatives
        if alts:
            listed = "; ".join(
                f"{_format_slot_safe(a['slot_id'])} ({a['slot_id']})" for a in alts[:3]
            )
            return (
                f"{_name_prefix(lead)} I couldn't book {booking.requested_slot_id} because {reason}. "
                f"The nearest free options are: {listed}. "
                "Reply with one of those exact slot times if you'd like me to book it."
            )
        return (
            f"{_name_prefix(lead)} I couldn't book {booking.requested_slot_id} because {reason}. "
            "There aren't any free alternatives available right now."
        )

    if status == LeadStatus.inspection_booked.value and lead.booked_slot_id:
        when = _format_slot_safe(lead.booked_slot_id)
        return (
            f"{_name_prefix(lead)} You're booked for a free roof inspection on {when} "
            f"(Brisbane time). Your slot id is {lead.booked_slot_id}."
        )

    # Policy honesty path (e.g. Raj): warranty/quote questions without a completed quote.
    if (
        status not in {LeadStatus.quoted.value, LeadStatus.awaiting_info.value}
        and ("warranty_policy" in turn.policies or "quote_policy" in turn.policies)
        and lead.quote_low is None
    ):
        parts = [f"{_name_prefix(lead)}"]
        quote_policy = turn.policies.get("quote_policy")
        warranty = turn.policies.get("warranty_policy") or {}
        if quote_policy:
            parts.append(
                "We can't guarantee a fixed price online — figures are estimates only, "
                "and a final written quote follows a free inspection."
            )
        if warranty:
            parts.append(
                "Our workmanship warranty is "
                f"{warranty.get('workmanship_restorations_years')} years on restorations and "
                f"{warranty.get('workmanship_replacements_years')} years on replacements. "
                "Colorbond material warranty is provided by the manufacturer. "
                "We can't offer a 25-year warranty or any other warranty beyond that."
            )
        parts.append("If you'd like an indicative estimate, tell me the service and job details.")
        return " ".join(parts)

    if status == LeadStatus.awaiting_info.value:
        missing = missing_essential_fields(lead)
        known_bits: list[str] = []
        if lead.service_type == "roof_restoration" and lead.roof_material:
            known_bits.append(f"a {lead.roof_material} roof restoration")
        elif lead.service_type == "gutter_replacement":
            known_bits.append("gutter replacement")
        elif lead.service_type:
            known_bits.append(lead.service_type.replace("_", " "))
        prefix = _name_prefix(lead)
        if known_bits:
            return f"{prefix} I've noted {known_bits[0]}. {_ask_for(missing)}"
        return f"{prefix} {_ask_for(missing)}"

    if status == LeadStatus.quoted.value and lead.quote_low is not None and lead.quote_high is not None:
        pricing = turn.pricing
        if pricing and pricing.both_ends_at_minimum and pricing.minimum_both_ends_display:
            price_text = pricing.minimum_both_ends_display
        elif lead.quote_low == lead.quote_high == 1500 and pricing and pricing.minimum_job_charge_applied:
            price_text = "$1,500 (minimum job charge)"
        else:
            price_text = f"{_format_money(lead.quote_low)} to {_format_money(lead.quote_high)} (incl. GST)"

        service_bits = lead.service_type.replace("_", " ") if lead.service_type else "job"
        if lead.roof_material and lead.service_type == "roof_restoration":
            service_bits = f"{lead.roof_material} roof restoration"
        size_bits = f" of about {int(lead.size_m2) if lead.size_m2 == int(lead.size_m2) else lead.size_m2} m²" if lead.size_m2 else ""

        assumptions = []
        if pricing and pricing.assumptions:
            if "steep_pitch" in pricing.assumptions and pricing.assumptions["steep_pitch"] is False:
                assumptions.append(
                    "I've assumed a non-steep pitch because you didn't mention the pitch."
                )
            if "storeys" in pricing.assumptions:
                assumptions.append(
                    f"I've assumed {pricing.assumptions['storeys']} storey "
                    "because you didn't mention the number of storeys."
                )

        reply = (
            f"{_name_prefix(lead)} For {service_bits}{size_bits}, "
            f"the indicative range is {price_text}. "
            "This is an estimate only (incl. GST), and the final written quote follows a free inspection."
        )
        if assumptions:
            reply += " " + " ".join(assumptions)
        return reply

    # Safe default — including prompt-injection / unclear asks with no business facts.
    return (
        f"{_name_prefix(lead)} I can only help with Summit Roofing enquiries "
        "(quotes, service area, emergencies, and inspections). "
        "I can't share customer records or switch into admin mode. "
        "Tell me about the roofing job you need."
    )


def serialize_tool_result(result: Any) -> Any:
    return result
