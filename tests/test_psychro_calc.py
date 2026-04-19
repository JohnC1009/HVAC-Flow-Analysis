"""Unit tests for PsychroCalc engine."""

import unittest

from hvac_flow.engine.air_state import AirState
from hvac_flow.engine.constants import UnitSystem, STD_ATM_PRESSURE_IP, STD_ATM_PRESSURE_SI
from hvac_flow.engine.psychro_calc import PsychroCalc


class TestPsychroCalcIP(unittest.TestCase):
    """Test PsychroCalc in IP (Imperial) units."""

    def setUp(self):
        """Create IP calculator."""
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)

    def test_from_db_rh(self):
        """Test creating AirState from dry-bulb and relative humidity."""
        state = self.calc.from_db_rh(dry_bulb=75.0, rel_hum=0.50, label="Test")
        self.assertIsInstance(state, AirState)
        self.assertEqual(state.dry_bulb, 75.0)
        self.assertAlmostEqual(state.relative_humidity, 0.50, places=4)
        self.assertEqual(state.label, "Test")
        # Verify derived properties are reasonable
        self.assertGreater(state.humidity_ratio, 0)
        self.assertGreater(state.wet_bulb, 0)
        self.assertGreater(state.enthalpy, 0)

    def test_from_db_wb(self):
        """Test creating AirState from dry-bulb and wet-bulb."""
        state = self.calc.from_db_wb(dry_bulb=80.0, wet_bulb=65.0)
        self.assertEqual(state.dry_bulb, 80.0)
        self.assertEqual(state.wet_bulb, 65.0)
        self.assertGreater(state.relative_humidity, 0)
        self.assertGreater(state.relative_humidity, state.humidity_ratio)

    def test_from_db_dp(self):
        """Test creating AirState from dry-bulb and dew-point."""
        state = self.calc.from_db_dp(dry_bulb=85.0, dew_point=60.0)
        self.assertEqual(state.dry_bulb, 85.0)
        self.assertEqual(state.dew_point, 60.0)
        self.assertGreater(state.relative_humidity, 0)

    def test_from_db_w(self):
        """Test creating AirState from dry-bulb and humidity ratio."""
        state = self.calc.from_db_w(dry_bulb=70.0, hum_ratio=0.010)
        self.assertEqual(state.dry_bulb, 70.0)
        self.assertEqual(state.humidity_ratio, 0.010)
        self.assertGreater(state.relative_humidity, 0)

    def test_from_enthalpy_w(self):
        """Test creating AirState from enthalpy and humidity ratio."""
        state = self.calc.from_enthalpy_w(enthalpy=30.0, hum_ratio=0.010)
        self.assertAlmostEqual(state.humidity_ratio, 0.010, places=4)
        self.assertGreater(state.dry_bulb, 0)

    def test_get_saturation_humidity_ratio(self):
        """Test saturation humidity ratio calculation."""
        w_sat = self.calc.get_saturation_humidity_ratio(dry_bulb=75.0)
        self.assertGreater(w_sat, 0)
        # Saturation HR should be higher at higher temperatures
        w_sat_hot = self.calc.get_saturation_humidity_ratio(dry_bulb=95.0)
        self.assertGreater(w_sat_hot, w_sat)

    def test_get_moist_air_density(self):
        """Test moist air density calculation."""
        state = self.calc.from_db_rh(dry_bulb=75.0, rel_hum=0.50)
        density = self.calc.get_moist_air_density(state)
        self.assertGreater(density, 0)
        self.assertLess(density, 0.1)  # Reasonable range for air density

    def test_get_humidity_ratio_from_rh(self):
        """Test HR calculation from RH."""
        w = self.calc.get_humidity_ratio_from_rh(dry_bulb=75.0, rel_hum=0.50)
        self.assertGreater(w, 0)
        # Higher RH should give higher HR
        w_high = self.calc.get_humidity_ratio_from_rh(dry_bulb=75.0, rel_hum=0.80)
        self.assertGreater(w_high, w)

    def test_get_humidity_ratio_from_twetbulb(self):
        """Test HR calculation from wet-bulb."""
        w = self.calc.get_humidity_ratio_from_twetbulb(dry_bulb=80.0, wet_bulb=65.0)
        self.assertGreater(w, 0)


class TestPsychroCalcSI(unittest.TestCase):
    """Test PsychroCalc in SI units."""

    def setUp(self):
        """Create SI calculator."""
        self.calc = PsychroCalc(unit_system=UnitSystem.SI)

    def test_from_db_rh_si(self):
        """Test creating AirState in SI units."""
        state = self.calc.from_db_rh(dry_bulb=24.0, rel_hum=0.50)
        self.assertEqual(state.dry_bulb, 24.0)
        self.assertAlmostEqual(state.relative_humidity, 0.50, places=4)
        # SI humidity ratio should be different from IP
        self.assertGreater(state.humidity_ratio, 0)

    def test_pressure_defaults(self):
        """Test that SI uses correct default pressure."""
        self.assertEqual(self.calc.pressure, STD_ATM_PRESSURE_SI)


class TestPsychroCalcConsistency(unittest.TestCase):
    """Test consistency between different calculation methods."""

    def setUp(self):
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)

    def test_round_trip_db_rh(self):
        """Test that db/rh -> state -> db/rh is consistent."""
        original_db = 75.0
        original_rh = 0.50
        state = self.calc.from_db_rh(dry_bulb=original_db, rel_hum=original_rh)
        # Recalculate RH from the resulting state
        w = self.calc.get_humidity_ratio_from_rh(
            dry_bulb=state.dry_bulb, rel_hum=state.relative_humidity
        )
        self.assertAlmostEqual(w, state.humidity_ratio, places=4)

    def test_consistency_between_methods(self):
        """Test that different input methods give consistent results."""
        # Create state from db/rh
        state1 = self.calc.from_db_rh(dry_bulb=75.0, rel_hum=0.50)
        # Create state from the resulting db and w
        state2 = self.calc.from_db_w(
            dry_bulb=state1.dry_bulb, hum_ratio=state1.humidity_ratio
        )
        # Should have same RH
        self.assertAlmostEqual(
            state1.relative_humidity, state2.relative_humidity, places=3
        )


class TestPsychroCalcEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions."""

    def setUp(self):
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)

    def test_saturated_air(self):
        """Test calculations at 100% relative humidity."""
        state = self.calc.from_db_rh(dry_bulb=75.0, rel_hum=1.0)
        self.assertEqual(state.relative_humidity, 1.0)
        # At saturation, DB should equal WB
        self.assertAlmostEqual(state.dry_bulb, state.wet_bulb, places=1)

    def test_dry_air(self):
        """Test calculations at very low humidity."""
        state = self.calc.from_db_rh(dry_bulb=75.0, rel_hum=0.01)
        self.assertAlmostEqual(state.relative_humidity, 0.01, places=3)
        self.assertLess(state.humidity_ratio, 0.001)

    def test_freezing_conditions(self):
        """Test calculations below freezing."""
        state = self.calc.from_db_rh(dry_bulb=32.0, rel_hum=0.80)
        self.assertEqual(state.dry_bulb, 32.0)
        self.assertGreater(state.humidity_ratio, 0)

    def test_hot_humid_conditions(self):
        """Test calculations at hot, humid conditions."""
        state = self.calc.from_db_rh(dry_bulb=95.0, rel_hum=0.80)
        self.assertEqual(state.dry_bulb, 95.0)
        self.assertGreater(state.humidity_ratio, 0.02)


if __name__ == "__main__":
    unittest.main()
