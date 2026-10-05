"""Whitelist of model-callable tools and their deterministic executors."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sqlalchemy.orm import Session

from app.agent.turn import TurnState
from app.clock import reference_now
from app.models import Lead, LeadStatus, Urgency
from app.tools.booking import book_inspection
from app.tools.emergency import notify_on_call
from app.tools.policy import get_policy
from app.tools.pricing import PricingInput, estimate_price
from app.tools.service_area import check_service_area

# Fields the model may submit via capture_lead_details.
CAPTURE_FIELDS = (
    "name",
    "service_type",
    "roof_material",
    "storeys",
    "steep_pitch",
    "size_m2",
    "gutter_length_m",
    "postcode",
    "suburb",
)

# Changing these invalidates a prior indicative quote / area decision.
_QUOTE_SENSITIVE_FIELDS = frozenset(
    {
        "service_type",
        "roof_material",
        "storeys",
        "steep_pitch",
        "size_m2",
        "gutter_length_m",
        "postcode",
    }
)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "capture_lead_details",
            "description": (
                "Record only facts the customer explicitly stated. "
                "Prefer omitting unstated fields entirely. "
                "If a provider emits null for an unstated field, it is ignored "
                "(existing lead values are left unchanged). "
                "roof_material is the customer's CURRENT/EXISTING roof material "
                "(tile or metal). Do not set it from target replacement wording "
                "such as Colorbond, 'replace to metal', or 'new metal roof' unless "
                "the customer separately states what the existing roof is."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    # null allowed: some tool-calling models emit null for "unset"
                    # instead of omitting the key; runtime treats null as omit.
                    "name": {"type": ["string", "null"]},
                    "service_type": {
                        "type": ["string", "null"],
                        "enum": [
                            "roof_restoration",
                            "roof_replacement",
                            "gutter_replacement",
                            "leak_repair",
                            "inspection_only",
                            "other",
                            None,
                        ],
                    },
                    "roof_material": {
                        "type": ["string", "null"],
                        "enum": ["tile", "metal", None],
                        "description": (
                            "CURRENT/EXISTING roof material only. "
                            "Omit when the customer only names a target replacement "
                            "material (e.g. Colorbond) without stating the existing roof."
                        ),
                    },
                    "storeys": {"type": ["integer", "null"]},
                    "steep_pitch": {"type": ["boolean", "null"]},
                    "size_m2": {"type": ["number", "null"]},
                    "gutter_length_m": {"type": ["number", "null"]},
                    "postcode": {"type": ["string", "null"]},
                    "suburb": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_service_area",
            "description": (
                "Check whether the current lead's persisted postcode is inside "
                "Summit Roofing's service area. Call only after capture_lead_details "
                "has recorded the customer's postcode. Tool arguments are not used "
                "as the authoritative postcode."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "postcode": {
                        "type": "string",
                        "description": "Ignored; the persisted lead postcode is authoritative.",
                    }
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "estimate_price",
            "description": "Calculate an indicative AUD incl. GST price range from lead facts.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_policy",
            "description": (
                "Fetch an exact Appendix E policy topic. "
                "When the customer asks whether a price, range, or maximum can be "
                "guaranteed and also asks about warranty, call this once for "
                "quote_policy and once for warranty_policy."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": [
                            "business",
                            "office_hours",
                            "emergency",
                            "services_offered",
                            "services_not_offered",
                            "quote_policy",
                            "warranty_policy",
                            "insurance_policy",
                        ],
                    }
                },
                "required": ["topic"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_emergency",
            "description": (
                "Mark this lead as an emergency matching Appendix E and notify on-call. "
                "Do not price or book after this."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_out_of_scope",
            "description": (
                "Mark the customer's requested service as outside Summit Roofing's "
                "offered services (Appendix E). Call this when they ask for something "
                "not offered (for example solar panels, skylights, asbestos removal, "
                "or commercial work above three storeys). Do not invent capability or "
                "ask them to choose a different offered service instead of declining."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "requested_service": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_inspection",
            "description": (
                "Book a free roof inspection into an exact Appendix D slot id "
                "(YYYY-MM-DDTHH:MM Brisbane time). Call only after check_service_area "
                "has confirmed the lead's CURRENT postcode is in area. Deterministic "
                "code validates existence, Sunday/past rules, and free status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "slot_id": {
                        "type": "string",
                        "description": "Exact slot id, e.g. 2026-10-16T11:00",
                    }
                },
                "required": ["slot_id"],
                "additionalProperties": False,
            },
        },
    },
]

ALLOWED_TOOL_NAMES = {t["function"]["name"] for t in TOOL_DEFINITIONS}


def _pricing_result_dict(result) -> dict[str, Any]:
    return {
        "calculable": result.calculable,
        "missing_fields": list(result.missing_fields),
        "low": result.low,
        "high": result.high,
        "assumptions": result.assumptions,
        "minimum_job_charge_applied": result.minimum_job_charge_applied,
        "both_ends_at_minimum": result.both_ends_at_minimum,
        "minimum_both_ends_display": result.minimum_both_ends_display,
        "currency": result.currency,
        "includes_gst": result.includes_gst,
        "is_estimate": result.is_estimate,
        "display_range_hint": result.display_range_hint,
    }


def capture_lead_details(lead: Lead, args: dict[str, Any]) -> dict[str, Any]:
    """Update only keys present in args; omission/null never clears existing values."""
    applied: dict[str, Any] = {}
    invalidated_quote = False
    for key in CAPTURE_FIELDS:
        if key not in args:
            continue
        value = args[key]
        # Treat JSON null like omission — models often send null for "not stated".
        if value is None:
            continue
        previous = getattr(lead, key)
        setattr(lead, key, value)
        applied[key] = value
        if key in _QUOTE_SENSITIVE_FIELDS and value != previous:
            invalidated_quote = True
    if invalidated_quote:
        lead.quote_low = None
        lead.quote_high = None
        if lead.status == LeadStatus.quoted.value:
            lead.status = LeadStatus.awaiting_info.value
        if lead.status == LeadStatus.out_of_area.value and "postcode" in applied:
            # Postcode changed — prior out-of-area decision is stale until re-checked.
            lead.status = LeadStatus.awaiting_info.value
    lead.updated_at = reference_now()
    return {"updated_fields": applied, "quote_invalidated": invalidated_quote}


def execute_tool(
    session: Session,
    lead: Lead,
    turn: TurnState,
    name: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    if name not in ALLOWED_TOOL_NAMES:
        result = {"error": "unknown_or_forbidden_tool", "tool": name}
        turn.record(name, args, result)
        return result

    emergency_active = turn.emergency or lead.status == LeadStatus.emergency.value
    out_of_area_active = turn.out_of_area or lead.status == LeadStatus.out_of_area.value
    out_of_scope_active = turn.out_of_scope or lead.status == LeadStatus.out_of_scope.value

    # Emergency short-circuit: block pricing/area/booking after escalation.
    if emergency_active and name in {"estimate_price", "check_service_area", "book_inspection"}:
        result = {"blocked": True, "reason": "emergency_active"}
        turn.blocked_tools.append(name)
        turn.record(name, args, result)
        return result

    if out_of_area_active and name in {"estimate_price", "book_inspection"}:
        result = {"blocked": True, "reason": "out_of_area"}
        turn.blocked_tools.append(name)
        turn.record(name, args, result)
        return result

    if out_of_scope_active and name in {"estimate_price", "book_inspection"}:
        result = {"blocked": True, "reason": "out_of_scope"}
        turn.blocked_tools.append(name)
        turn.record(name, args, result)
        return result

    if name == "capture_lead_details":
        previous_postcode = lead.postcode
        result = capture_lead_details(lead, args)
        # Postcode change invalidates any in-turn area decision for the old value.
        updated = result.get("updated_fields") or {}
        if "postcode" in updated and updated["postcode"] != previous_postcode:
            turn.area = None
            turn.out_of_area = False
        turn.record(name, {k: args[k] for k in CAPTURE_FIELDS if k in args}, result)
        return result

    if name == "check_service_area":
        # Authoritative binding: only persisted lead.postcode. Never trust tool args.
        postcode = lead.postcode
        if not postcode:
            result = {
                "error": "postcode_required",
                "resolved": False,
                "message": "Capture the customer's postcode on the lead before checking area.",
            }
            turn.record(name, {}, result)
            return result
        area = check_service_area(session, str(postcode))
        turn.area = area
        if not area.in_area:
            turn.out_of_area = True
            lead.status = LeadStatus.out_of_area.value
            lead.quote_low = None
            lead.quote_high = None
        else:
            turn.out_of_area = False
            if lead.status == LeadStatus.out_of_area.value:
                lead.status = LeadStatus.awaiting_info.value
        result = asdict(area)
        turn.record(name, {"postcode": str(postcode)}, result)
        return result

    if name == "estimate_price":
        # When a postcode is on the lead, require an authoritative in-area decision
        # for that CURRENT postcode before pricing (mirrors booking gate).
        if lead.postcode:
            area_for_current = (
                turn.area is not None and turn.area.postcode == str(lead.postcode)
            )
            if not area_for_current:
                result = {"blocked": True, "reason": "service_area_unresolved"}
                turn.blocked_tools.append(name)
                turn.record(name, {}, result)
                return result
            if not turn.area.in_area:
                result = {"blocked": True, "reason": "out_of_area"}
                turn.blocked_tools.append(name)
                turn.record(name, {}, result)
                return result
        if not lead.service_type:
            result = {"error": "service_type_required"}
            turn.record(name, args, result)
            return result
        inputs = {
            "service_type": lead.service_type,
            "roof_material": lead.roof_material,
            "size_m2": lead.size_m2,
            "gutter_length_m": lead.gutter_length_m,
            "storeys": lead.storeys,
            "steep_pitch": lead.steep_pitch,
        }
        pricing = estimate_price(
            session,
            PricingInput(
                service_type=lead.service_type,
                roof_material=lead.roof_material,
                size_m2=lead.size_m2,
                gutter_length_m=lead.gutter_length_m,
                storeys=lead.storeys,
                steep_pitch=lead.steep_pitch,
            ),
        )
        turn.pricing = pricing
        if pricing.calculable:
            lead.quote_low = pricing.low
            lead.quote_high = pricing.high
        result = {**_pricing_result_dict(pricing), "inputs": inputs}
        # Trace records empty model args plus authoritative inputs used.
        turn.record(name, {}, result)
        return result

    if name == "get_policy":
        topic = args["topic"]
        content = get_policy(session, topic)
        turn.policies[topic] = content
        result = {"topic": topic, "content": content}
        turn.record(name, args, result)
        return result

    if name == "mark_emergency":
        turn.emergency = True
        lead.urgency = Urgency.emergency.value
        lead.status = LeadStatus.emergency.value
        lead.quote_low = None
        lead.quote_high = None
        lead.updated_at = reference_now()
        notify_payload = None
        if not turn.notified:
            notify_payload = notify_on_call(lead)
            turn.notified = True
        emergency_policy = get_policy(session, "emergency")
        turn.policies["emergency"] = emergency_policy
        result = {
            "status": lead.status,
            "urgency": lead.urgency,
            "notified": True,
            "notify": notify_payload,
            "emergency_line": emergency_policy.get("phone_display"),
            "availability": emergency_policy.get("availability"),
        }
        turn.record(name, args, result)
        return result

    if name == "mark_out_of_scope":
        turn.out_of_scope = True
        lead.status = LeadStatus.out_of_scope.value
        lead.quote_low = None
        lead.quote_high = None
        lead.updated_at = reference_now()
        services_not = get_policy(session, "services_not_offered")
        turn.policies["services_not_offered"] = services_not
        result = {
            "status": lead.status,
            "requested_service": args.get("requested_service"),
            "services_not_offered": services_not,
        }
        turn.record(name, args, result)
        return result

    if name == "book_inspection":
        slot_id = str(args.get("slot_id", "")).strip()
        # Booking requires an authoritative in-area result for the CURRENT postcode.
        # Python never silently runs check_service_area; the model must emit it.
        if not lead.postcode:
            result = {"blocked": True, "reason": "postcode_required"}
            turn.blocked_tools.append(name)
            turn.record(name, {"slot_id": slot_id}, result)
            return result
        area_ok = (
            turn.area is not None
            and turn.area.postcode == str(lead.postcode)
            and turn.area.in_area
        )
        if not area_ok:
            if turn.area is not None and turn.area.postcode == str(lead.postcode) and not turn.area.in_area:
                result = {"blocked": True, "reason": "out_of_area"}
            else:
                result = {"blocked": True, "reason": "service_area_unresolved"}
            turn.blocked_tools.append(name)
            turn.record(name, {"slot_id": slot_id}, result)
            return result
        booking = book_inspection(session, lead, slot_id)
        turn.booking = booking
        result = booking.as_dict()
        turn.record(name, {"slot_id": slot_id}, result)
        return result

    result = {"error": "unhandled_tool", "tool": name}
    turn.record(name, args, result)
    return result
