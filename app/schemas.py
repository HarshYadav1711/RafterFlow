"""Appendix A API / domain contracts. Structural validation only — no business tools."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Channel(str, Enum):
    whatsapp = "whatsapp"
    web_form = "web_form"


class ServiceType(str, Enum):
    roof_restoration = "roof_restoration"
    roof_replacement = "roof_replacement"
    gutter_replacement = "gutter_replacement"
    leak_repair = "leak_repair"
    inspection_only = "inspection_only"
    other = "other"


class RoofMaterial(str, Enum):
    tile = "tile"
    metal = "metal"


class Urgency(str, Enum):
    emergency = "emergency"
    standard = "standard"


class LeadStatus(str, Enum):
    new = "new"
    awaiting_info = "awaiting_info"
    quoted = "quoted"
    inspection_booked = "inspection_booked"
    emergency = "emergency"
    out_of_area = "out_of_area"
    out_of_scope = "out_of_scope"


class EnquiryRequest(BaseModel):
    """Inbound contract for future POST /enquiries."""

    model_config = ConfigDict(extra="forbid")

    channel: Channel
    from_phone: str = Field(min_length=1)
    from_name: Optional[str] = None
    message: str = Field(min_length=1)
    received_at: datetime

    @field_validator("received_at")
    @classmethod
    def received_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        return value


class Lead(BaseModel):
    """Lead record as returned in the enquiry response (Appendix A)."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    lead_id: str
    phone: str
    name: Optional[str] = None
    channel: Channel
    service_type: Optional[ServiceType] = None
    roof_material: Optional[RoofMaterial] = None
    storeys: Optional[int] = Field(default=None, ge=0)
    steep_pitch: Optional[bool] = None
    size_m2: Optional[float] = Field(default=None, ge=0)
    gutter_length_m: Optional[float] = Field(default=None, ge=0)
    postcode: Optional[str] = None
    suburb: Optional[str] = None
    urgency: Urgency
    status: LeadStatus
    quote_low: Optional[int] = None
    quote_high: Optional[int] = None
    booked_slot_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("lead timestamps must be timezone-aware")
        return value


class ToolCall(BaseModel):
    """Record of a deterministic tool invocation (tools implemented in later phases)."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    args: dict[str, Any]
    result: dict[str, Any] | Any


class EnquiryResponse(BaseModel):
    """Outbound contract for future POST /enquiries."""

    model_config = ConfigDict(extra="forbid")

    reply: str
    lead: Lead
    tool_calls: list[ToolCall]
