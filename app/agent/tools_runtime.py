"""Whitelist of model-callable tools and their deterministic executors."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sqlalchemy.orm import Session

from app.agent.turn import TurnState
from app.clock import reference_now
from app.models import Lead, LeadStatus, Urgency
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

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "capture_lead_details",
            "description": (
                "Record only facts the customer explicitly stated. "
                "Omit any field not stated. Omitted fields leave existing lead values unchanged."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "service_type": {
                        "type": "string",
                        "enum": [
                            "roof_restoration",
                            "roof_replacement",
                            "gutter_replacement",
                            "leak_repair",
                            "inspection_only",
                            "other",
                        ],
                    },
                    "roof_material": {"type": "string", "enum": ["tile", "metal"]},
                    "storeys": {"type": "integer"},
                    "steep_pitch": {"type": "boolean"},
                    "size_m2": {"type": "number"},
                    "gutter_length_m": {"type": "number"},
                    "postcode": {"type": "string"},
                    "suburb": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_service_area",
            "description": "Check whether a postcode is inside Summit Roofing's service area.",
            "parameters": {
                "type": "object",
                "properties": {"postcode": {"type": "string"}},
                "required": ["postcode"],
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
            "description": "Fetch an exact Appendix E policy topic.",
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
            "description": "Mark the requested service as outside offered services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "requested_service": {"type": "string"},
                },
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
    """Update only keys present in args; omission never clears existing values."""
    applied: dict[str, Any] = {}
    for key in CAPTURE_FIELDS:
        if key not in args:
            continue
        value = args[key]
        setattr(lead, key, value)
        applied[key] = value
    lead.updated_at = reference_now()
    return {"updated_fields": applied}


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

    # Emergency short-circuit: block pricing/area/booking-style work after escalation.
    if turn.emergency and name in {"estimate_price", "check_service_area"}:
        result = {"blocked": True, "reason": "emergency_active"}
        turn.blocked_tools.append(name)
        turn.record(name, args, result)
        return result

    if turn.out_of_area and name == "estimate_price":
        result = {"blocked": True, "reason": "out_of_area"}
        turn.blocked_tools.append(name)
        turn.record(name, args, result)
        return result

    if turn.out_of_scope and name == "estimate_price":
        result = {"blocked": True, "reason": "out_of_scope"}
        turn.blocked_tools.append(name)
        turn.record(name, args, result)
        return result

    if name == "capture_lead_details":
        result = capture_lead_details(lead, args)
        turn.record(name, args, result)
        return result

    if name == "check_service_area":
        postcode = args.get("postcode") or lead.postcode
        if not postcode:
            result = {"error": "postcode_required"}
            turn.record(name, args, result)
            return result
        area = check_service_area(session, str(postcode))
        turn.area = area
        if not area.in_area:
            turn.out_of_area = True
            lead.status = LeadStatus.out_of_area.value
            lead.quote_low = None
            lead.quote_high = None
        result = asdict(area)
        turn.record(name, {"postcode": str(postcode)}, result)
        return result

    if name == "estimate_price":
        if not lead.service_type:
            result = {"error": "service_type_required"}
            turn.record(name, args, result)
            return result
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
        result = _pricing_result_dict(pricing)
        turn.record(name, args, result)
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

    result = {"error": "unhandled_tool", "tool": name}
    turn.record(name, args, result)
    return result
