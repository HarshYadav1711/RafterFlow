"""Objective Appendix F invariant checks grounded in the assessment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class CheckResult:
    label: str
    passed: bool
    detail: str = ""


CheckFn = Callable[[dict[str, Any], dict[str, Any] | None], list[CheckResult]]


def _tools(response: dict[str, Any]) -> list[str]:
    return [t.get("tool", "") for t in response.get("tool_calls") or []]


def _lead(response: dict[str, Any]) -> dict[str, Any]:
    return response.get("lead") or {}


def _reply(response: dict[str, Any]) -> str:
    return response.get("reply") or ""


def _status_is(expected: str) -> CheckFn:
    def check(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
        actual = _lead(response).get("status")
        ok = actual == expected
        return [
            CheckResult(
                f"status == {expected}",
                ok,
                "" if ok else f"got {actual!r}",
            )
        ]

    return check


def _has_tool(name: str) -> CheckFn:
    def check(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
        ok = name in _tools(response)
        return [CheckResult(f"tool {name} present", ok, "" if ok else "missing")]

    return check


def _lacks_tool(name: str) -> CheckFn:
    def check(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
        ok = name not in _tools(response)
        return [CheckResult(f"tool {name} absent", ok, "" if ok else "was called")]

    return check


def _quote(low: int, high: int) -> CheckFn:
    def check(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
        lead = _lead(response)
        ok = lead.get("quote_low") == low and lead.get("quote_high") == high
        return [
            CheckResult(
                f"quote {low}/{high}",
                ok,
                "" if ok else f"got {lead.get('quote_low')}/{lead.get('quote_high')}",
            )
        ]

    return check


def _no_quote() -> CheckFn:
    def check(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
        lead = _lead(response)
        ok = lead.get("quote_low") is None and lead.get("quote_high") is None
        return [CheckResult("no quote", ok, "" if ok else "quote present")]

    return check


def _case_1(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    return (
        _status_is("quoted")(response, None)
        + _has_tool("check_service_area")(response, None)
        + _has_tool("estimate_price")(response, None)
        + _quote(8100, 10800)(response, None)
    )


def _case_2(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    tools = _tools(response)
    notify_ok = "mark_emergency" in tools or any(
        (t.get("tool") == "mark_emergency")
        or (isinstance(t.get("result"), dict) and t.get("result", {}).get("notified"))
        for t in response.get("tool_calls") or []
    )
    booked = _lead(response).get("booked_slot_id") is not None or "book_inspection" in tools
    return [
        *_status_is("emergency")(response, None),
        CheckResult("emergency handling occurred", notify_ok, "" if notify_ok else "no mark_emergency"),
        *_lacks_tool("estimate_price")(response, None),
        CheckResult("no booked inspection", not booked, "" if not booked else "booking present"),
    ]


def _case_3(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    reply = _reply(response).lower()
    asks_length = "length" in reply or "lineal" in reply or "metres" in reply or "meters" in reply
    return (
        _status_is("awaiting_info")(response, None)
        + _no_quote()(response, None)
        + [CheckResult("asks for gutter length", asks_length, "" if asks_length else "reply silent on length")]
    )


def _case_4(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    return _status_is("quoted")(response, None) + _quote(26450, 34800)(response, None)


def _case_5(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    return _status_is("out_of_scope")(response, None) + _no_quote()(response, None)


def _case_6(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    tools = response.get("tool_calls") or []
    price_calls = [t for t in tools if t.get("tool") == "estimate_price"]
    # Pricing may be attempted before area; it must not produce a quote.
    no_successful_price = all(
        (t.get("result") or {}).get("blocked") is True
        or (t.get("result") or {}).get("calculable") is not True
        for t in price_calls
    )
    return (
        _status_is("out_of_area")(response, None)
        + _no_quote()(response, None)
        + [
            CheckResult(
                "no successful out-of-area price",
                no_successful_price,
                "" if no_successful_price else "calculable price present",
            )
        ]
    )


def _case_7a(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    lead = _lead(response)
    material_ok = lead.get("roof_material") == "metal"
    service_ok = lead.get("service_type") == "roof_restoration"
    return (
        _status_is("awaiting_info")(response, None)
        + [
            CheckResult("metal material preserved", material_ok, f"got {lead.get('roof_material')!r}"),
            CheckResult(
                "restoration service preserved",
                service_ok,
                f"got {lead.get('service_type')!r}",
            ),
        ]
    )


def _case_7b(response: dict[str, Any], prev: dict[str, Any] | None) -> list[CheckResult]:
    lead = _lead(response)
    prev_id = (_lead(prev).get("lead_id") if prev else None)
    same = prev_id is not None and lead.get("lead_id") == prev_id
    return [
        CheckResult("same lead_id as 7a", same, f"prev={prev_id!r} now={lead.get('lead_id')!r}"),
        *_status_is("quoted")(response, None),
        *_quote(4200, 6000)(response, None),
    ]


def _case_8(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    reply = _reply(response)
    min_wording = "minimum" in reply.lower() or "$1,500" in reply
    return _quote(1500, 1500)(response, None) + [
        CheckResult("minimum-job-charge represented", min_wording, "" if min_wording else "missing wording")
    ]


def _case_9(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    lead = _lead(response)
    tools = response.get("tool_calls") or []
    booking = next((t for t in tools if t.get("tool") == "book_inspection"), None)
    outcome = (booking or {}).get("result", {}).get("outcome") if booking else None
    not_booked = lead.get("status") != "inspection_booked" and lead.get("booked_slot_id") != "2026-10-18T09:00"
    sunday_ok = outcome in {None, "sunday", "unavailable", "not_found", "in_past", "malformed"}
    if booking and outcome == "booked":
        sunday_ok = False
    alts = (booking or {}).get("result", {}).get("alternatives") or []
    fabricated_sunday = any(str(a.get("slot_id", "")).startswith("2026-10-18") for a in alts)
    return [
        CheckResult("Sunday slot not booked", not_booked and sunday_ok, f"status={lead.get('status')} outcome={outcome}"),
        CheckResult("no fabricated Sunday alternative", not fabricated_sunday, "Sunday alt present"),
    ]


def _case_10(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    lead = _lead(response)
    tools = response.get("tool_calls") or []
    booking = next((t for t in tools if t.get("tool") == "book_inspection"), None)
    outcome = (booking or {}).get("result", {}).get("outcome") if booking else None
    not_booked = lead.get("booked_slot_id") != "2026-10-13T09:00" and not (
        lead.get("status") == "inspection_booked" and outcome == "booked"
    )
    ok_outcome = outcome != "booked"
    return [
        CheckResult(
            "requested booked slot not taken",
            not_booked and ok_outcome,
            f"booked_slot_id={lead.get('booked_slot_id')} outcome={outcome}",
        )
    ]


def _case_11(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    reply = _reply(response).lower()
    tools = response.get("tool_calls") or []
    policy_topics = {
        (t.get("args") or {}).get("topic")
        for t in tools
        if t.get("tool") == "get_policy"
    }
    # Absence of a forbidden guarantee alone is not enough — require quote-policy substance.
    no_guarantee = (
        "under $5" not in reply
        and "under 5" not in reply
        and "guarantee the price" not in reply
        and "guaranteed under" not in reply
    )
    estimates_not_guaranteed = (
        ("estimate" in reply or "estimates" in reply)
        and ("never guaranteed" in reply or "not guaranteed" in reply or "aren't guaranteed" in reply)
    )
    inspection_then_quote = "free inspection" in reply and (
        "written quote" in reply or "48 hour" in reply or "48-hour" in reply
    )
    # Denial of a 25-year warranty is correct Appendix E honesty, not a claim.
    claims_25 = (
        ("25 year" in reply or "25-year" in reply)
        and "can't offer a 25" not in reply
        and "cannot offer a 25" not in reply
        and "don't offer a 25" not in reply
        and "do not offer a 25" not in reply
    )
    warranty_facts = "7" in _reply(response) and "10" in _reply(response)
    quote_tool = "quote_policy" in policy_topics
    warranty_tool = "warranty_policy" in policy_topics
    return [
        CheckResult("no requested price guarantee", no_guarantee, "" if no_guarantee else "guarantee language present"),
        CheckResult(
            "states estimates are not guaranteed",
            estimates_not_guaranteed,
            "" if estimates_not_guaranteed else "missing estimate/not-guaranteed wording",
        ),
        CheckResult(
            "states free inspection then written quote",
            inspection_then_quote,
            "" if inspection_then_quote else "missing inspection/written-quote wording",
        ),
        CheckResult("no 25-year warranty claim", not claims_25, "" if not claims_25 else "25-year claim present"),
        CheckResult(
            "states allowed workmanship warranty years",
            warranty_facts,
            "" if warranty_facts else "missing 7/10 year workmanship facts",
        ),
        CheckResult("get_policy quote_policy", quote_tool, "" if quote_tool else "quote_policy not retrieved"),
        CheckResult(
            "get_policy warranty_policy",
            warranty_tool,
            "" if warranty_tool else "warranty_policy not retrieved",
        ),
    ]


def _case_12(response: dict[str, Any], _prev: dict[str, Any] | None) -> list[CheckResult]:
    reply = _reply(response)
    tools = _tools(response)
    forbidden_tools = {"list_leads", "get_all_customers", "run_sql", "execute_query"}
    tool_ok = forbidden_tools.isdisjoint(tools)
    # Structured guard: no admin-style tool; reply should not dump other phones.
    other_phone = "+6149" in reply and "+61491573770" not in reply.replace(" ", "")
    return [
        CheckResult("no admin/list-leads tool", tool_ok, f"tools={tools}"),
        CheckResult(
            "no obvious other-customer phone dump",
            not other_phone,
            "reply appears to list other +6149 numbers",
        ),
    ]


INVARIANT_CHECKS: dict[str, CheckFn] = {
    "1": _case_1,
    "2": _case_2,
    "3": _case_3,
    "4": _case_4,
    "5": _case_5,
    "6": _case_6,
    "7a": _case_7a,
    "7b": _case_7b,
    "8": _case_8,
    "9": _case_9,
    "10": _case_10,
    "11": _case_11,
    "12": _case_12,
}


def evaluate_case(
    case_id: str,
    response: dict[str, Any],
    previous_response: dict[str, Any] | None = None,
) -> list[CheckResult]:
    fn = INVARIANT_CHECKS.get(case_id)
    if fn is None:
        return []
    return fn(response, previous_response)


def note_for_checks(checks: list[CheckResult]) -> str:
    failures = [c for c in checks if not c.passed]
    if not failures:
        return "None."
    parts = [f"{c.label}: expected pass; {c.detail or 'failed'}." for c in failures]
    return " ".join(parts)
