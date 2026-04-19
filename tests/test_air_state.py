"""Unit tests for AirState dataclass."""

import unittest
from dataclasses import FrozenInstanceError

from hvac_flow.engine.air_state import AirState


class TestAirState(unittest.TestCase):
    """Test cases for the immutable AirState dataclass."""

    def setUp(self):
        """Create a standard air state for testing."""
        self.state = AirState(
            dry_bulb=75.0,
            humidity_ratio=0.009,
            relative_humidity=0.50,
            wet_bulb=62.5,
            dew_point=55.0,
            enthalpy=28.5,
            specific_volume=13.7,
            pressure=14.696,
            label="Test State"
        )

    def test_air_state_creation(self):
        """Test that AirState can be created with all properties."""
        self.assertEqual(self.state.dry_bulb, 75.0)
        self.assertEqual(self.state.humidity_ratio, 0.009)
        self.assertEqual(self.state.relative_humidity, 0.50)
        self.assertEqual(self.state.wet_bulb, 62.5)
        self.assertEqual(self.state.dew_point, 55.0)
        self.assertEqual(self.state.enthalpy, 28.5)
        self.assertEqual(self.state.specific_volume, 13.7)
        self.assertEqual(self.state.pressure, 14.696)
        self.assertEqual(self.state.label, "Test State")

    def test_air_state_immutability(self):
        """Test that AirState is frozen and cannot be modified."""
        with self.assertRaises(FrozenInstanceError):
            self.state.dry_bulb = 80.0

    def test_with_label(self):
        """Test creating a copy with a new label."""
        new_state = self.state.with_label("New Label")
        self.assertEqual(new_state.label, "New Label")
        # Original should be unchanged
        self.assertEqual(self.state.label, "Test State")
        # All other properties should be the same
        self.assertEqual(new_state.dry_bulb, self.state.dry_bulb)
        self.assertEqual(new_state.humidity_ratio, self.state.humidity_ratio)

    def test_summary_ip(self):
        """Test the summary string generation."""
        summary = self.state.summary_ip()
        self.assertIn("DB: 75.0°F", summary)
        self.assertIn("WB: 62.5°F", summary)
        self.assertIn("RH: 50.0%", summary)
        self.assertIn("W: 0.0090 lb/lb", summary)
        self.assertIn("h: 28.50 Btu/lb", summary)
        self.assertIn("DP: 55.0°F", summary)

    def test_air_state_without_label(self):
        """Test creating AirState without optional label."""
        state = AirState(
            dry_bulb=70.0,
            humidity_ratio=0.008,
            relative_humidity=0.45,
            wet_bulb=60.0,
            dew_point=50.0,
            enthalpy=26.0,
            specific_volume=13.5,
            pressure=14.696
        )
        self.assertIsNone(state.label)


class TestAirStateEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_extreme_cold(self):
        """Test air state at very cold conditions."""
        state = AirState(
            dry_bulb=-20.0,
            humidity_ratio=0.0001,
            relative_humidity=0.80,
            wet_bulb=-25.0,
            dew_point=-30.0,
            enthalpy=-5.0,
            specific_volume=11.0,
            pressure=14.696
        )
        self.assertEqual(state.dry_bulb, -20.0)

    def test_extreme_hot(self):
        """Test air state at very hot conditions."""
        state = AirState(
            dry_bulb=120.0,
            humidity_ratio=0.025,
            relative_humidity=0.60,
            wet_bulb=95.0,
            dew_point=100.0,
            enthalpy=55.0,
            specific_volume=16.0,
            pressure=14.696
        )
        self.assertEqual(state.dry_bulb, 120.0)

    def test_zero_humidity(self):
        """Test air state with zero humidity ratio."""
        state = AirState(
            dry_bulb=75.0,
            humidity_ratio=0.0,
            relative_humidity=0.0,
            wet_bulb=75.0,
            dew_point=-100.0,  # Theoretical for dry air
            enthalpy=18.0,
            specific_volume=13.3,
            pressure=14.696
        )
        self.assertEqual(state.humidity_ratio, 0.0)


if __name__ == "__main__":
    unittest.main()
