"""Per-request agent turn state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.tools.booking import BookingResult
from app.tools.pricing import PricingResult
from app.tools.service_area import ServiceAreaResult


@dataclass
class TurnState:
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    emergency: bool = False
    out_of_area: bool = False
    out_of_scope: bool = False
    notified: bool = False
    area: ServiceAreaResult | None = None
    pricing: PricingResult | None = None
    booking: BookingResult | None = None
    policies: dict[str, Any] = field(default_factory=dict)
    blocked_tools: list[str] = field(default_factory=list)
    recovery_used: bool = False
    unresolved_required_tools: list[str] = field(default_factory=list)

    def record(self, tool: str, args: dict[str, Any], result: Any) -> None:
        self.tool_calls.append({"tool": tool, "args": args, "result": result})
