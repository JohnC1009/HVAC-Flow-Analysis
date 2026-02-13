"""Tests for ZoneProcessNode — sensible + latent heat gain from occupied space."""

import pytest

from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.zone_process import ZoneProcessNode

calc = PsychroCalc()

# ── helpers ──────────────────────────────────────────────────────────

def _make_zone(**overrides):
    zone = ZoneProcessNode(name="TestZone")
    for k, v in overrides.items():
        zone.parameters[k] = v
    return zone


def _set_supply(zone, supply_state, mass_flow=750.0):
    zone.ports["supply_air"].air_state = supply_state
    zone.ports["supply_air"].mass_flow = mass_flow


# ── tests ────────────────────────────────────────────────────────────

def test_loads_mode():
    """Direct loads mode: return air should be warmer and more humid."""
    supply = calc.from_db_w(55, 0.008)
    zone = _make_zone(
        input_mode="loads",
        sensible_load_btuh=120000,
        latent_load_btuh=30000,
    )
    _set_supply(zone, supply)

    zone.compute(calc)

    ret = zone.ports["return_air"].air_state
    assert ret.dry_bulb > supply.dry_bulb
    assert ret.humidity_ratio > supply.humidity_ratio

    # Results dict should contain the loads
    assert "sensible_load_btuh" in zone.results
    assert "latent_load_btuh" in zone.results


def test_shr_total_mode():
    """SHR + total mode: return air warmer and more humid, SHR preserved."""
    supply = calc.from_db_w(55, 0.008)
    zone = _make_zone(
        input_mode="shr_total",
        total_load_btuh=150000,
        sensible_heat_ratio=0.80,
    )
    _set_supply(zone, supply)

    zone.compute(calc)

    ret = zone.ports["return_air"].air_state
    assert ret.dry_bulb > supply.dry_bulb
    assert ret.humidity_ratio > supply.humidity_ratio

    assert zone.results["shr"] == pytest.approx(0.80, abs=0.01)


def test_negative_w_clamped():
    """Negative latent load (dehumidification) must not yield negative W."""
    supply = calc.from_db_w(55, 0.0001)
    zone = _make_zone(
        input_mode="loads",
        sensible_load_btuh=120000,
        latent_load_btuh=-50000,
    )
    _set_supply(zone, supply)

    zone.compute(calc)

    ret = zone.ports["return_air"].air_state
    assert ret.humidity_ratio >= 0.0
