"""Tests for EnthalpyWheelNode — two-stream heat/moisture exchange."""

import pytest

from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.enthalpy_wheel import EnthalpyWheelNode

calc = PsychroCalc()

# ── helpers ──────────────────────────────────────────────────────────

def _make_wheel(eps_s=0.75, eps_l=0.70, bypass=0.0):
    """Return a configured EnthalpyWheelNode."""
    wheel = EnthalpyWheelNode(name="TestWheel")
    wheel.parameters["sensible_effectiveness"] = eps_s
    wheel.parameters["latent_effectiveness"] = eps_l
    wheel.parameters["bypass_fraction"] = bypass
    return wheel


def _set_standard_inlets(wheel, supply_state=None, exhaust_state=None,
                         mass_flow=750.0):
    """Assign the standard 95 F / 75 F test conditions to both inlets."""
    if supply_state is None:
        supply_state = calc.from_db_rh(95, 0.40)
    if exhaust_state is None:
        exhaust_state = calc.from_db_rh(75, 0.50)

    wheel.ports["supply_in"].air_state = supply_state
    wheel.ports["supply_in"].mass_flow = mass_flow
    wheel.ports["exhaust_in"].air_state = exhaust_state
    wheel.ports["exhaust_in"].mass_flow = mass_flow


# ── tests ────────────────────────────────────────────────────────────

def test_nominal_no_bypass():
    """Wheel with no bypass should move both streams toward each other."""
    wheel = _make_wheel(eps_s=0.75, eps_l=0.70, bypass=0.0)
    supply_in = calc.from_db_rh(95, 0.40)
    exhaust_in = calc.from_db_rh(75, 0.50)
    _set_standard_inlets(wheel, supply_in, exhaust_in)

    wheel.compute(calc)

    supply_out = wheel.ports["supply_out"].air_state
    exhaust_out = wheel.ports["exhaust_out"].air_state

    # Supply out DB must be between the two inlet DBs
    low_db = min(supply_in.dry_bulb, exhaust_in.dry_bulb)
    high_db = max(supply_in.dry_bulb, exhaust_in.dry_bulb)
    assert low_db < supply_out.dry_bulb < high_db

    # Exhaust out DB must also be between the two inlet DBs
    assert low_db < exhaust_out.dry_bulb < high_db

    # Humidity ratios should have changed
    assert supply_out.humidity_ratio != pytest.approx(
        supply_in.humidity_ratio, abs=1e-6
    )
    assert exhaust_out.humidity_ratio != pytest.approx(
        exhaust_in.humidity_ratio, abs=1e-6
    )


def test_bypass_zero_matches_no_bypass():
    """Explicitly setting bypass_fraction=0 should give identical results."""
    wheel_a = _make_wheel(eps_s=0.75, eps_l=0.70, bypass=0.0)
    wheel_b = _make_wheel(eps_s=0.75, eps_l=0.70, bypass=0.0)

    supply_in = calc.from_db_rh(95, 0.40)
    exhaust_in = calc.from_db_rh(75, 0.50)

    _set_standard_inlets(wheel_a, supply_in, exhaust_in)
    _set_standard_inlets(wheel_b, supply_in, exhaust_in)

    wheel_a.compute(calc)
    wheel_b.compute(calc)

    a_sup = wheel_a.ports["supply_out"].air_state
    b_sup = wheel_b.ports["supply_out"].air_state
    a_exh = wheel_a.ports["exhaust_out"].air_state
    b_exh = wheel_b.ports["exhaust_out"].air_state

    assert a_sup.dry_bulb == pytest.approx(b_sup.dry_bulb, abs=0.01)
    assert a_sup.humidity_ratio == pytest.approx(b_sup.humidity_ratio, rel=1e-6)
    assert a_exh.dry_bulb == pytest.approx(b_exh.dry_bulb, abs=0.01)
    assert a_exh.humidity_ratio == pytest.approx(b_exh.humidity_ratio, rel=1e-6)


def test_bypass_full():
    """Full bypass (1.0) — no exchange at all on the supply side."""
    wheel = _make_wheel(bypass=1.0)
    supply_in = calc.from_db_rh(95, 0.40)
    exhaust_in = calc.from_db_rh(75, 0.50)
    _set_standard_inlets(wheel, supply_in, exhaust_in)

    wheel.compute(calc)

    supply_out = wheel.ports["supply_out"].air_state
    exhaust_out = wheel.ports["exhaust_out"].air_state

    # Supply out equals supply in (all air bypassed)
    assert supply_out.dry_bulb == pytest.approx(supply_in.dry_bulb, abs=0.1)
    assert supply_out.humidity_ratio == pytest.approx(
        supply_in.humidity_ratio, rel=0.01
    )

    # Exhaust out equals exhaust in (through_fraction is 0 so no exchange)
    assert exhaust_out.dry_bulb == pytest.approx(exhaust_in.dry_bulb, abs=0.1)
    assert exhaust_out.humidity_ratio == pytest.approx(
        exhaust_in.humidity_ratio, rel=0.01
    )


def test_bypass_half():
    """50 % bypass — supply out DB between no-bypass result and supply in."""
    # First get no-bypass result for reference
    wheel_ref = _make_wheel(bypass=0.0)
    supply_in = calc.from_db_rh(95, 0.40)
    exhaust_in = calc.from_db_rh(75, 0.50)
    _set_standard_inlets(wheel_ref, supply_in, exhaust_in)
    wheel_ref.compute(calc)
    no_bypass_db = wheel_ref.ports["supply_out"].air_state.dry_bulb

    # Now with 50 % bypass
    wheel = _make_wheel(bypass=0.5)
    _set_standard_inlets(wheel, supply_in, exhaust_in)
    wheel.compute(calc)
    half_bypass_db = wheel.ports["supply_out"].air_state.dry_bulb

    # half-bypass DB should be between no-bypass DB and supply_in DB
    low = min(no_bypass_db, supply_in.dry_bulb)
    high = max(no_bypass_db, supply_in.dry_bulb)
    assert low < half_bypass_db < high


def test_get_iterable_inlet():
    """get_iterable_inlet should return 'exhaust_in'."""
    wheel = _make_wheel()
    assert wheel.get_iterable_inlet() == "exhaust_in"
