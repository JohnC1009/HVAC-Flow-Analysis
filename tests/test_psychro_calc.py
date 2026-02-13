"""Tests for PsychroCalc psychrometric calculation engine."""

import pytest

from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.engine.constants import UnitSystem

# Module-level calculator instance, IP units at standard atmospheric pressure.
calc = PsychroCalc(unit_system=UnitSystem.IP)


# ── Happy-path factory method tests ─────────────────────────────────────────


def test_from_db_rh_known_value():
    """95 °F dry-bulb at 50 % RH should produce physically plausible results."""
    state = calc.from_db_rh(95.0, 0.50)

    assert state.dry_bulb == pytest.approx(95.0, abs=0.001)
    assert state.relative_humidity == pytest.approx(0.5, abs=0.001)
    assert state.humidity_ratio > 0
    assert 75.0 <= state.wet_bulb <= 85.0
    assert state.enthalpy > 0
    assert state.specific_volume > 0


def test_from_db_wb_known_value():
    """80 °F dry-bulb / 67 °F wet-bulb should give reasonable RH and W."""
    state = calc.from_db_wb(80.0, 67.0)

    assert state.dry_bulb == pytest.approx(80.0, abs=0.001)
    assert state.wet_bulb == pytest.approx(67.0, abs=0.001)
    assert state.humidity_ratio > 0
    assert 0 < state.relative_humidity < 1


def test_from_db_dp_known_value():
    """80 °F dry-bulb / 60 °F dew-point should resolve humidity ratio."""
    state = calc.from_db_dp(80.0, 60.0)

    assert state.dry_bulb == pytest.approx(80.0, abs=0.001)
    assert state.dew_point == pytest.approx(60.0, abs=0.001)
    assert state.humidity_ratio > 0


def test_from_db_w_known_value():
    """75 °F dry-bulb / W=0.0093 lb/lb should round-trip humidity ratio."""
    state = calc.from_db_w(75.0, 0.0093)

    assert state.dry_bulb == pytest.approx(75.0, abs=0.001)
    assert state.humidity_ratio == pytest.approx(0.0093, rel=0.05)
    assert 0 < state.relative_humidity < 1


def test_from_enthalpy_w():
    """Enthalpy=30 Btu/lb and W=0.0093 should recover a positive dry-bulb."""
    state = calc.from_enthalpy_w(30.0, 0.0093)

    assert state.humidity_ratio == pytest.approx(0.0093, rel=0.05)
    assert state.dry_bulb > 0


# ── Error / validation tests ────────────────────────────────────────────────


def test_from_db_w_negative_w_raises():
    """Negative humidity ratio must raise ValueError with 'negative' in msg."""
    with pytest.raises(ValueError, match="(?i)negative"):
        calc.from_db_w(75.0, -0.001)


def test_from_db_rh_invalid_rh_raises():
    """RH outside 0-1 (e.g. 2.0) must raise ValueError."""
    with pytest.raises(ValueError):
        calc.from_db_rh(75.0, 2.0)


def test_from_enthalpy_w_negative_w_raises():
    """Negative humidity ratio via enthalpy+W must raise ValueError."""
    with pytest.raises(ValueError, match="(?i)negative"):
        calc.from_enthalpy_w(30.0, -0.001)


# ── Utility method tests ────────────────────────────────────────────────────


def test_get_saturation_humidity_ratio():
    """Saturation W at 95 °F should exceed 0.03 lb/lb."""
    w_sat = calc.get_saturation_humidity_ratio(95.0)
    assert w_sat > 0.03


# ── Label / metadata tests ──────────────────────────────────────────────────


def test_with_label():
    """Labels should propagate through from_db_rh and with_label."""
    state = calc.from_db_rh(75.0, 0.50, label="test")
    assert state.label == "test"

    renamed = state.with_label("new")
    assert renamed.label == "new"
