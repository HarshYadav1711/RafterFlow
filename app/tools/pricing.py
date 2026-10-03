"""Deterministic indicative pricing from seeded Appendix C data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PricingConfig, PricingRate
from app.seed import PRICING_CONFIG_ID


class PricingConfigurationError(RuntimeError):
    """Seeded pricing reference data is missing or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class PricingInput:
    service_type: str
    roof_material: str | None = None
    size_m2: float | Decimal | None = None
    gutter_length_m: float | Decimal | None = None
    storeys: int | None = None
    steep_pitch: bool | None = None


@dataclass(frozen=True, slots=True)
class PricingResult:
    calculable: bool
    missing_fields: tuple[str, ...] = ()
    low: int | None = None
    high: int | None = None
    assumptions: dict[str, Any] = field(default_factory=dict)
    minimum_job_charge_applied: bool = False
    both_ends_at_minimum: bool = False
    minimum_both_ends_display: str | None = None
    currency: str = "AUD"
    includes_gst: bool = True
    is_estimate: bool = True

    @property
    def display_range_hint(self) -> str | None:
        """Structured hint for a later reply layer — not customer prose."""
        if not self.calculable or self.low is None or self.high is None:
            return None
        if self.both_ends_at_minimum and self.minimum_both_ends_display:
            return self.minimum_both_ends_display
        return f"${self.low:,} to ${self.high:,} (incl. GST)"


def _to_decimal(value: float | Decimal | int) -> Decimal:
    # str() avoids binary float artefacts when the caller passes a float literal.
    return Decimal(str(value))


def round_nearest_aud(amount: Decimal, increment: int, half: str) -> int:
    """Round a monetary amount to the nearest increment (Appendix C: half rounds up)."""
    if half != "up":
        raise PricingConfigurationError(f"Unsupported rounding mode: {half!r}")
    step = Decimal(increment)
    rounded = (amount / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step
    return int(rounded)


def _load_config(session: Session) -> PricingConfig:
    config = session.get(PricingConfig, PRICING_CONFIG_ID)
    if config is None:
        raise PricingConfigurationError("pricing_config row is missing; run seed first")
    return config


def _find_rate(session: Session, service_type: str, roof_material: str | None) -> PricingRate | None:
    key = roof_material or ""
    return session.scalar(
        select(PricingRate).where(
            PricingRate.service_type == service_type,
            PricingRate.roof_material_key == key,
        )
    )


def estimate_price(session: Session, data: PricingInput) -> PricingResult:
    """
    Apply Appendix C calculation rules in order.
    Returns a typed not-calculable result when required fields are missing.
    """
    config = _load_config(session)
    missing: list[str] = []

    if data.service_type == "roof_restoration" and config.roof_restoration_requires_roof_material:
        if data.roof_material is None:
            missing.append("roof_material")

    rate = _find_rate(session, data.service_type, data.roof_material)
    if rate is None and "roof_material" not in missing:
        # Unknown service / material combination in seeded table.
        missing.append("service_rate")

    if rate is not None and rate.quantity_field == "size_m2" and data.size_m2 is None:
        missing.append("size_m2")
    if rate is not None and rate.quantity_field == "gutter_length_m" and data.gutter_length_m is None:
        missing.append("gutter_length_m")

    if missing:
        return PricingResult(
            calculable=False,
            missing_fields=tuple(missing),
            currency=config.currency,
            includes_gst=config.includes_gst,
        )

    assert rate is not None  # guarded above

    low_rate = _to_decimal(rate.low_rate)
    high_rate = _to_decimal(rate.high_rate)

    # 1. Base price
    if rate.quantity_field == "size_m2":
        quantity = _to_decimal(data.size_m2)  # type: ignore[arg-type]
        low = quantity * low_rate
        high = quantity * high_rate
    elif rate.quantity_field == "gutter_length_m":
        quantity = _to_decimal(data.gutter_length_m)  # type: ignore[arg-type]
        low = quantity * low_rate
        high = quantity * high_rate
    else:
        # Fixed callout / free inspection
        low = low_rate
        high = high_rate

    assumptions: dict[str, Any] = {}
    storeys = data.storeys
    steep = data.steep_pitch

    if storeys is None:
        storeys = config.default_storeys
        assumptions["storeys"] = storeys
    if steep is None:
        steep = config.default_steep_pitch
        assumptions["steep_pitch"] = steep

    multiplier_services = set(json.loads(config.multiplier_service_types_json))
    # 2. Multipliers (eligible services only)
    if data.service_type in multiplier_services:
        apply_storeys = storeys >= 2
        apply_steep = bool(steep)
        if apply_storeys and apply_steep:
            factor = _to_decimal(config.combined_multiplier)
        elif apply_storeys:
            factor = _to_decimal(config.storey_multiplier)
        elif apply_steep:
            factor = _to_decimal(config.steep_pitch_multiplier)
        else:
            factor = Decimal("1")
        low *= factor
        high *= factor

    # 5. Round each end independently
    low_rounded = round_nearest_aud(low, config.rounding_nearest_aud, config.rounding_half)
    high_rounded = round_nearest_aud(high, config.rounding_nearest_aud, config.rounding_half)

    # 6–7. Minimum job charge
    min_services = set(json.loads(config.minimum_charge_service_types_json))
    min_applied = False
    both_at_min = False
    min_display: str | None = None
    if data.service_type in min_services:
        minimum = config.minimum_job_charge_aud
        if low_rounded < minimum:
            low_rounded = minimum
            min_applied = True
        if high_rounded < minimum:
            high_rounded = minimum
            min_applied = True
        if low_rounded == minimum and high_rounded == minimum:
            both_at_min = True
            min_display = config.minimum_both_ends_display

    return PricingResult(
        calculable=True,
        missing_fields=(),
        low=low_rounded,
        high=high_rounded,
        assumptions=assumptions,
        minimum_job_charge_applied=min_applied,
        both_ends_at_minimum=both_at_min,
        minimum_both_ends_display=min_display,
        currency=config.currency,
        includes_gst=config.includes_gst,
        is_estimate=True,
    )
