"""Tests for DesiccantWheelNode — active dehumidification via adsorption."""

import pytest

from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.desiccant_wheel import DesiccantWheelNode

calc = PsychroCalc()

# ── helpers ──────────────────────────────────────────────────────────

def _make_wheel(**overrides):
    wheel = DesiccantWheelNode(name="TestDesiccant")
    for k, v in overrides.items():
        wheel.parameters[k] = v
    return wheel


def _set_inlets(wheel, process_state, regen_state, mass_flow=750.0):
    wheel.ports["process_in"].air_state = process_state
    wheel.ports["process_in"].mass_flow = mass_flow
    wheel.ports["regen_in"].air_state = regen_state
    wheel.ports["regen_in"].mass_flow = mass_flow


# ── tests ────────────────────────────────────────────────────────────

def test_nominal_dehumidification():
    """Process air should be dehumidified (lower W) and warmed (higher DB)."""
    wheel = _make_wheel()
    process_in = calc.from_db_rh(85, 0.50)
    regen_in = calc.from_db_w(200, 0.0093)
    _set_inlets(wheel, process_in, regen_in)

    wheel.compute(calc)

    process_out = wheel.ports["process_out"].air_state
    regen_out = wheel.ports["regen_out"].air_state

    # Process air dehumidified
    assert process_out.humidity_ratio < process_in.humidity_ratio

    # Process air warmed (heat of adsorption)
    assert process_out.dry_bulb > process_in.dry_bulb

    # Regen air picks up moisture
    assert regen_out.humidity_ratio > regen_in.humidity_ratio


def test_w_clamping_no_negative():
    """Process out W must never go negative even with very low inlet W."""
    wheel = _make_wheel()
    process_in = calc.from_db_w(85, 0.001)
    regen_in = calc.from_db_w(200, 0.0005)
    _set_inlets(wheel, process_in, regen_in)

    wheel.compute(calc)

    process_out = wheel.ports["process_out"].air_state
    assert process_out.humidity_ratio >= 0.0


def test_get_iterable_inlet():
    """get_iterable_inlet should return 'regen_in'."""
    wheel = _make_wheel()
    assert wheel.get_iterable_inlet() == "regen_in"
