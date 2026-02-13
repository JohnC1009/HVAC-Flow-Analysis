"""Tests for SensibleHeatRecoveryNode — sensible-only heat exchange."""

import pytest

from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.sensible_heat_recovery import SensibleHeatRecoveryNode

calc = PsychroCalc()

# ── helpers ──────────────────────────────────────────────────────────

def _make_node(eps=0.65, bypass=0.0):
    node = SensibleHeatRecoveryNode(name="TestSHR")
    node.parameters["sensible_effectiveness"] = eps
    node.parameters["bypass_fraction"] = bypass
    return node


def _set_standard_inlets(node, supply_state=None, exhaust_state=None,
                         mass_flow=750.0):
    if supply_state is None:
        supply_state = calc.from_db_rh(95, 0.40)
    if exhaust_state is None:
        exhaust_state = calc.from_db_rh(75, 0.50)

    node.ports["supply_in"].air_state = supply_state
    node.ports["supply_in"].mass_flow = mass_flow
    node.ports["exhaust_in"].air_state = exhaust_state
    node.ports["exhaust_in"].mass_flow = mass_flow


# ── tests ────────────────────────────────────────────────────────────

def test_nominal_w_unchanged():
    """Sensible-only exchange must not alter humidity ratios."""
    node = _make_node(eps=0.65, bypass=0.0)
    supply_in = calc.from_db_rh(95, 0.40)
    exhaust_in = calc.from_db_rh(75, 0.50)
    _set_standard_inlets(node, supply_in, exhaust_in)

    node.compute(calc)

    supply_out = node.ports["supply_out"].air_state
    exhaust_out = node.ports["exhaust_out"].air_state

    # Humidity ratios must be unchanged (sensible only)
    assert supply_out.humidity_ratio == pytest.approx(
        supply_in.humidity_ratio, rel=1e-6
    )
    assert exhaust_out.humidity_ratio == pytest.approx(
        exhaust_in.humidity_ratio, rel=1e-6
    )

    # DB should have shifted toward the other stream
    assert supply_out.dry_bulb < supply_in.dry_bulb   # cooled
    assert exhaust_out.dry_bulb > exhaust_in.dry_bulb  # warmed


def test_bypass_full():
    """Full bypass — supply out DB equals supply in DB."""
    node = _make_node(eps=0.65, bypass=1.0)
    supply_in = calc.from_db_rh(95, 0.40)
    exhaust_in = calc.from_db_rh(75, 0.50)
    _set_standard_inlets(node, supply_in, exhaust_in)

    node.compute(calc)

    supply_out = node.ports["supply_out"].air_state
    assert supply_out.dry_bulb == pytest.approx(supply_in.dry_bulb, abs=0.1)


def test_bypass_half():
    """50 % bypass — supply out DB between no-bypass result and supply in."""
    supply_in = calc.from_db_rh(95, 0.40)
    exhaust_in = calc.from_db_rh(75, 0.50)

    # Reference: no bypass
    ref = _make_node(eps=0.65, bypass=0.0)
    _set_standard_inlets(ref, supply_in, exhaust_in)
    ref.compute(calc)
    no_bypass_db = ref.ports["supply_out"].air_state.dry_bulb

    # Half bypass
    node = _make_node(eps=0.65, bypass=0.5)
    _set_standard_inlets(node, supply_in, exhaust_in)
    node.compute(calc)
    half_db = node.ports["supply_out"].air_state.dry_bulb

    low = min(no_bypass_db, supply_in.dry_bulb)
    high = max(no_bypass_db, supply_in.dry_bulb)
    assert low < half_db < high


def test_get_iterable_inlet():
    """get_iterable_inlet should return 'exhaust_in'."""
    node = _make_node()
    assert node.get_iterable_inlet() == "exhaust_in"
