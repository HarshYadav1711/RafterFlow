from decimal import Decimal

from app.tools.pricing import PricingInput, estimate_price, round_nearest_aud


def test_worked_example_appendix_c(seeded_session):
    result = estimate_price(
        seeded_session,
        PricingInput(
            service_type="roof_replacement",
            size_m2=150,
            storeys=2,
            steep_pitch=True,
        ),
    )
    assert result.calculable is True
    assert result.low == 18050
    assert result.high == 23700
    assert result.includes_gst is True
    assert result.display_range_hint == "$18,050 to $23,700 (incl. GST)"


def test_priya_tile_restoration(seeded_session):
    result = estimate_price(
        seeded_session,
        PricingInput(
            service_type="roof_restoration",
            roof_material="tile",
            size_m2=180,
            storeys=1,
            steep_pitch=None,
        ),
    )
    assert result.calculable is True
    assert result.low == 8100
    assert result.high == 10800
    assert result.assumptions == {"steep_pitch": False}


def test_daniel_replacement(seeded_session):
    result = estimate_price(
        seeded_session,
        PricingInput(
            service_type="roof_replacement",
            size_m2=220,
            storeys=2,
            steep_pitch=True,
        ),
    )
    assert result.calculable is True
    assert result.low == 26450
    assert result.high == 34800


def test_replacement_ignores_lead_roof_material_for_rate_lookup(seeded_session):
    """Colorbond / metal on a replacement lead must still use the null-material rate."""
    result = estimate_price(
        seeded_session,
        PricingInput(
            service_type="roof_replacement",
            roof_material="metal",
            size_m2=220,
            storeys=2,
            steep_pitch=True,
        ),
    )
    assert result.calculable is True
    assert result.low == 26450
    assert result.high == 34800


def test_aisha_metal_restoration(seeded_session):
    result = estimate_price(
        seeded_session,
        PricingInput(
            service_type="roof_restoration",
            roof_material="metal",
            size_m2=120,
            storeys=1,
            steep_pitch=None,
        ),
    )
    assert result.calculable is True
    assert result.low == 4200
    assert result.high == 6000
    assert result.assumptions == {"steep_pitch": False}


def test_ben_minimum_job_charge(seeded_session):
    result = estimate_price(
        seeded_session,
        PricingInput(
            service_type="roof_restoration",
            roof_material="metal",
            size_m2=20,
            storeys=None,
            steep_pitch=None,
        ),
    )
    assert result.calculable is True
    assert result.low == 1500
    assert result.high == 1500
    assert result.minimum_job_charge_applied is True
    assert result.both_ends_at_minimum is True
    assert result.minimum_both_ends_display == "$1,500 (minimum job charge)"
    assert result.assumptions == {"storeys": 1, "steep_pitch": False}
    assert result.display_range_hint == "$1,500 (minimum job charge)"


def test_restoration_missing_material_not_calculable(seeded_session):
    result = estimate_price(
        seeded_session,
        PricingInput(service_type="roof_restoration", size_m2=100, storeys=1),
    )
    assert result.calculable is False
    assert "roof_material" in result.missing_fields
    assert result.low is None


def test_gutter_missing_length_not_calculable(seeded_session):
    result = estimate_price(
        seeded_session,
        PricingInput(service_type="gutter_replacement", storeys=1),
    )
    assert result.calculable is False
    assert "gutter_length_m" in result.missing_fields


def test_leak_repair_no_multipliers(seeded_session):
    result = estimate_price(
        seeded_session,
        PricingInput(
            service_type="leak_repair",
            storeys=3,
            steep_pitch=True,
        ),
    )
    assert result.calculable is True
    assert result.low == 250
    assert result.high == 650
    assert result.minimum_job_charge_applied is False


def test_inspection_only_free(seeded_session):
    result = estimate_price(
        seeded_session,
        PricingInput(service_type="inspection_only"),
    )
    assert result.calculable is True
    assert result.low == 0
    assert result.high == 0
    assert result.minimum_job_charge_applied is False


def test_half_up_rounding_boundary():
    # 25 is exactly halfway from 0 to 50 -> half-up => 50
    assert round_nearest_aud(Decimal("25"), 50, "up") == 50
    # just below midpoint stays down
    assert round_nearest_aud(Decimal("24.99"), 50, "up") == 0
    # worked-example fragment: 18026.25 / 50 = 360.525 -> 361 -> 18050
    assert round_nearest_aud(Decimal("18026.25"), 50, "up") == 18050
    # 23718.75 / 50 = 474.375 -> 474 -> 23700
    assert round_nearest_aud(Decimal("23718.75"), 50, "up") == 23700
