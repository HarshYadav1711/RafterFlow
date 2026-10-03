"""SQLAlchemy persistence models for Appendix A leads and appendix reference data."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.clock import reference_now
from app.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


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


class MessageDirection(str, Enum):
    inbound = "inbound"
    outbound = "outbound"


class SlotStatus(str, Enum):
    free = "free"
    booked = "booked"


class Lead(Base):
    """One continuing assessment lead per phone (R7)."""

    __tablename__ = "leads"

    lead_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)

    service_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    roof_material: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    storeys: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    steep_pitch: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    size_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gutter_length_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    postcode: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    suburb: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    urgency: Mapped[str] = mapped_column(String(32), nullable=False, default=Urgency.standard.value)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=LeadStatus.new.value)

    quote_low: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quote_high: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    booked_slot_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=reference_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=reference_now,
        onupdate=reference_now,
    )

    messages: Mapped[list[Message]] = relationship(back_populates="lead", cascade="all, delete-orphan")


class Message(Base):
    """Inbound/outbound message belonging to a single lead."""

    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.lead_id", ondelete="CASCADE"), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    channel: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=reference_now)

    lead: Mapped[Lead] = relationship(back_populates="messages")


class ServiceArea(Base):
    __tablename__ = "service_areas"

    postcode: Mapped[str] = mapped_column(String(16), primary_key=True)
    suburb: Mapped[str] = mapped_column(String(128), nullable=False)


class PricingRate(Base):
    """One Appendix C price-table row."""

    __tablename__ = "pricing_rates"
    __table_args__ = (
        UniqueConstraint("service_type", "roof_material_key", name="uq_pricing_rate_service_material"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Empty string means "not material-specific" (JSON null). Avoids SQLite NULL unique quirks.
    roof_material_key: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    roof_material: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    low_rate: Mapped[float] = mapped_column(Float, nullable=False)
    high_rate: Mapped[float] = mapped_column(Float, nullable=False)
    quantity_field: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PricingConfig(Base):
    """Singleton-ish row of Appendix C calculation configuration (not runtime state)."""

    __tablename__ = "pricing_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    includes_gst: Mapped[bool] = mapped_column(Boolean, nullable=False)
    storey_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    steep_pitch_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    combined_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    multiplier_service_types_json: Mapped[str] = mapped_column(Text, nullable=False)
    default_storeys: Mapped[int] = mapped_column(Integer, nullable=False)
    default_steep_pitch: Mapped[bool] = mapped_column(Boolean, nullable=False)
    must_state_assumption: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rounding_nearest_aud: Mapped[int] = mapped_column(Integer, nullable=False)
    rounding_half: Mapped[str] = mapped_column(String(16), nullable=False)
    minimum_job_charge_aud: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_charge_service_types_json: Mapped[str] = mapped_column(Text, nullable=False)
    minimum_both_ends_display: Mapped[str] = mapped_column(String(128), nullable=False)
    roof_restoration_requires_roof_material: Mapped[bool] = mapped_column(Boolean, nullable=False)
    estimate_wording_json: Mapped[str] = mapped_column(Text, nullable=False)
    calculation_order_json: Mapped[str] = mapped_column(Text, nullable=False)
    worked_example_json: Mapped[str] = mapped_column(Text, nullable=False)


class AvailabilitySlot(Base):
    """Exact Appendix D inspection slot. Status is runtime-mutable after seed."""

    __tablename__ = "availability_slots"

    slot_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    slot_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    slot_time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    booked_lead_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("leads.lead_id", ondelete="SET NULL"),
        nullable=True,
    )


class PolicyRecord(Base):
    """Appendix E policy fragment stored as JSON under a stable topic key."""

    __tablename__ = "policies"

    topic: Mapped[str] = mapped_column(String(64), primary_key=True)
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
