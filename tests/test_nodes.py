"""Unit tests for HVAC equipment nodes."""

import unittest

from hvac_flow.engine.air_state import AirState
from hvac_flow.engine.constants import UnitSystem
from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.air_sink import AirSinkNode
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.fan import FanNode
from hvac_flow.models.heating_coil import HeatingCoilNode
from hvac_flow.models.mixing_box import MixingBoxNode
from hvac_flow.models.source_node import SourceNode


class TestSourceNode(unittest.TestCase):
    """Test SourceNode (outdoor air or return air source)."""

    def setUp(self):
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)
        self.node = SourceNode(name="Test Source")

    def test_init(self):
        """Test node initialization."""
        self.assertEqual(self.node.NODE_TYPE, "source")
        self.assertEqual(self.node.DISPLAY_NAME, "Source")
        self.assertEqual(self.node.name, "Test Source")

    def test_ports(self):
        """Test port configuration."""
        self.assertEqual(len(self.node.ports), 1)
        self.assertIn("outlet", self.node.ports)
        self.assertEqual(self.node.ports["outlet"].direction, "outlet")

    def test_compute(self):
        """Test computation of source node."""
        # Set parameters
        self.node.parameters["dry_bulb"] = 95.0
        self.node.parameters["relative_humidity"] = 0.50
        self.node.parameters["mass_flow"] = 1000.0

        self.node.compute(self.calc)

        outlet = self.node.ports["outlet"]
        self.assertIsNotNone(outlet.air_state)
        self.assertEqual(outlet.air_state.dry_bulb, 95.0)
        self.assertAlmostEqual(outlet.air_state.relative_humidity, 0.50, places=4)
        self.assertEqual(outlet.mass_flow, 1000.0)

    def test_results(self):
        """Test that results are populated."""
        self.node.parameters["dry_bulb"] = 85.0
        self.node.parameters["relative_humidity"] = 0.60
        self.node.parameters["mass_flow"] = 2000.0

        self.node.compute(self.calc)

        self.assertIn("outlet_state", self.node.results)
        self.assertIn("mass_flow", self.node.results)
        self.assertEqual(self.node.results["mass_flow"], 2000.0)


class TestCoolingCoilNode(unittest.TestCase):
    """Test CoolingCoilNode."""

    def setUp(self):
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)
        self.node = CoolingCoilNode(name="Test Cooling Coil")

        # Create an entering air state
        self.entering_state = self.calc.from_db_rh(80.0, 0.50)
        self.node.ports["inlet"].air_state = self.entering_state
        self.node.ports["inlet"].mass_flow = 1000.0

    def test_init(self):
        """Test node initialization."""
        self.assertEqual(self.node.NODE_TYPE, "cooling_coil")
        self.assertEqual(self.node.DISPLAY_NAME, "Cooling Coil")

    def test_ports(self):
        """Test port configuration."""
        self.assertEqual(len(self.node.ports), 2)
        self.assertIn("inlet", self.node.ports)
        self.assertIn("outlet", self.node.ports)

    def test_compute_cooling(self):
        """Test basic cooling computation."""
        self.node.parameters["leaving_db"] = 55.0
        self.node.parameters["leaving_mode"] = "rh"
        self.node.parameters["leaving_rh"] = 0.90

        self.node.compute(self.calc)

        outlet = self.node.ports["outlet"]
        self.assertIsNotNone(outlet.air_state)
        self.assertEqual(outlet.air_state.dry_bulb, 55.0)
        self.assertAlmostEqual(outlet.air_state.relative_humidity, 0.90, places=4)

    def test_compute_loads(self):
        """Test that cooling loads are calculated."""
        self.node.parameters["leaving_db"] = 55.0
        self.node.parameters["leaving_mode"] = "rh"
        self.node.parameters["leaving_rh"] = 0.90

        self.node.compute(self.calc)

        self.assertIn("total_load_btuh", self.node.results)
        self.assertIn("sensible_load_btuh", self.node.results)
        self.assertIn("latent_load_btuh", self.node.results)
        self.assertIn("total_load_tons", self.node.results)

        # Loads should be positive (cooling)
        self.assertGreater(self.node.results["total_load_btuh"], 0)
        self.assertGreater(self.node.results["sensible_load_btuh"], 0)

    def test_compute_shr(self):
        """Test Sensible Heat Ratio calculation."""
        self.node.parameters["leaving_db"] = 55.0
        self.node.parameters["leaving_mode"] = "rh"
        self.node.parameters["leaving_rh"] = 0.90

        self.node.compute(self.calc)

        shr = self.node.results["shr"]
        self.assertGreaterEqual(shr, 0.0)
        self.assertLessEqual(shr, 1.0)

    def test_error_no_inlet_state(self):
        """Test error when inlet state is missing."""
        self.node.ports["inlet"].air_state = None
        with self.assertRaises(ValueError) as context:
            self.node.compute(self.calc)
        self.assertIn("inlet air state", str(context.exception).lower())

    def test_error_no_mass_flow(self):
        """Test error when mass flow is missing."""
        self.node.ports["inlet"].mass_flow = 0
        with self.assertRaises(ValueError) as context:
            self.node.compute(self.calc)
        self.assertIn("mass flow", str(context.exception).lower())

    def test_error_invalid_leaving_temp(self):
        """Test error when leaving temp >= entering temp."""
        self.node.parameters["leaving_db"] = 85.0  # Warmer than entering (80°F)
        with self.assertRaises(ValueError) as context:
            self.node.compute(self.calc)
        self.assertIn("cannot heat", str(context.exception).lower())

    def test_boundary_conditions(self):
        """Test boundary condition checking."""
        self.node.boundary_conditions["total_load_btuh"] = 50000.0
        self.node.parameters["leaving_db"] = 55.0
        self.node.parameters["leaving_mode"] = "rh"
        self.node.parameters["leaving_rh"] = 0.90

        self.node.compute(self.calc)
        warnings = self.node.check_boundary_conditions()

        # Should have warnings if load exceeds boundary
        self.node.results["total_load_btuh"] = 60000.0
        warnings = self.node.check_boundary_conditions()
        self.assertGreater(len(warnings), 0)


class TestHeatingCoilNode(unittest.TestCase):
    """Test HeatingCoilNode."""

    def setUp(self):
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)
        self.node = HeatingCoilNode(name="Test Heating Coil")

        # Create an entering air state
        self.entering_state = self.calc.from_db_rh(55.0, 0.50)
        self.node.ports["inlet"].air_state = self.entering_state
        self.node.ports["inlet"].mass_flow = 1000.0

    def test_init(self):
        """Test node initialization."""
        self.assertEqual(self.node.NODE_TYPE, "heating_coil")
        self.assertEqual(self.node.DISPLAY_NAME, "Heating Coil")

    def test_compute_heating(self):
        """Test basic heating computation."""
        self.node.parameters["leaving_db"] = 105.0

        self.node.compute(self.calc)

        outlet = self.node.ports["outlet"]
        self.assertIsNotNone(outlet.air_state)
        self.assertEqual(outlet.air_state.dry_bulb, 105.0)
        # Humidity ratio should remain constant
        self.assertEqual(
            outlet.air_state.humidity_ratio,
            self.entering_state.humidity_ratio
        )

    def test_compute_load(self):
        """Test that heating load is calculated."""
        self.node.parameters["leaving_db"] = 105.0

        self.node.compute(self.calc)

        self.assertIn("sensible_load_btuh", self.node.results)
        self.assertGreater(self.node.results["sensible_load_btuh"], 0)

    def test_error_invalid_leaving_temp(self):
        """Test error when leaving temp <= entering temp."""
        self.node.parameters["leaving_db"] = 50.0  # Cooler than entering (55°F)
        with self.assertRaises(ValueError) as context:
            self.node.compute(self.calc)
        self.assertIn("cannot cool", str(context.exception).lower())


class TestFanNode(unittest.TestCase):
    """Test FanNode."""

    def setUp(self):
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)
        self.node = FanNode(name="Test Fan")

        # Create an entering air state
        self.entering_state = self.calc.from_db_rh(75.0, 0.50)
        self.node.ports["inlet"].air_state = self.entering_state
        self.node.ports["inlet"].mass_flow = 2000.0

    def test_init(self):
        """Test node initialization."""
        self.assertEqual(self.node.NODE_TYPE, "fan")
        self.assertEqual(self.node.DISPLAY_NAME, "Supply Fan")

    def test_compute_bhp_mode(self):
        """Test fan computation using BHP input."""
        self.node.parameters["input_mode"] = "bhp"
        self.node.parameters["bhp"] = 10.0
        self.node.parameters["motor_efficiency"] = 0.90

        self.node.compute(self.calc)

        outlet = self.node.ports["outlet"]
        self.assertIsNotNone(outlet.air_state)
        # Temperature should rise due to fan heat
        self.assertGreater(outlet.air_state.dry_bulb, self.entering_state.dry_bulb)

        self.assertIn("temp_rise_f", self.node.results)
        self.assertIn("fan_heat_btuh", self.node.results)
        self.assertGreater(self.node.results["fan_heat_btuh"], 0)

    def test_compute_temp_rise_mode(self):
        """Test fan computation using direct temperature rise."""
        self.node.parameters["input_mode"] = "temp_rise"
        self.node.parameters["temp_rise"] = 2.5

        self.node.compute(self.calc)

        outlet = self.node.ports["outlet"]
        self.assertEqual(outlet.air_state.dry_bulb, 77.5)  # 75 + 2.5
        self.assertEqual(self.node.results["temp_rise_f"], 2.5)

    def test_error_zero_efficiency(self):
        """Test error when motor efficiency is zero."""
        self.node.parameters["input_mode"] = "bhp"
        self.node.parameters["motor_efficiency"] = 0.0
        with self.assertRaises(ValueError) as context:
            self.node.compute(self.calc)
        self.assertIn("efficiency", str(context.exception).lower())


class TestMixingBoxNode(unittest.TestCase):
    """Test MixingBoxNode."""

    def setUp(self):
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)
        self.node = MixingBoxNode(name="Test Mixer")

        # Create two entering air states
        self.oa_state = self.calc.from_db_rh(95.0, 0.40)  # Hot outdoor air
        self.ra_state = self.calc.from_db_rh(75.0, 0.50)  # Cool return air

        self.node.ports["primary"].air_state = self.oa_state
        self.node.ports["primary"].mass_flow = 200.0
        self.node.ports["secondary"].air_state = self.ra_state
        self.node.ports["secondary"].mass_flow = 800.0

    def test_init(self):
        """Test node initialization."""
        self.assertEqual(self.node.NODE_TYPE, "mixing_box")
        self.assertEqual(self.node.DISPLAY_NAME, "Mixing Box")

    def test_ports(self):
        """Test port configuration."""
        self.assertEqual(len(self.node.ports), 3)
        self.assertIn("primary", self.node.ports)
        self.assertIn("secondary", self.node.ports)
        self.assertIn("mixed", self.node.ports)

    def test_compute_fixed_mode(self):
        """Test mixing with fixed fraction."""
        self.node.parameters["economizer_mode"] = "fixed"
        self.node.parameters["primary_fraction"] = 0.20

        self.node.compute(self.calc)

        outlet = self.node.ports["mixed"]
        self.assertIsNotNone(outlet.air_state)

        # Mixed temperature should be between OA and RA
        mixed_db = outlet.air_state.dry_bulb
        self.assertGreater(mixed_db, self.ra_state.dry_bulb)
        self.assertLess(mixed_db, self.oa_state.dry_bulb)

        # Total mass flow should be sum of inputs
        self.assertEqual(outlet.mass_flow, 1000.0)

    def test_compute_temperature_economizer(self):
        """Test temperature-based economizer control."""
        self.node.parameters["economizer_mode"] = "temperature"
        self.node.parameters["min_oa_fraction"] = 0.15
        self.node.parameters["econ_high_limit_db"] = 80.0  # OA is 95°F, so locked out

        self.node.compute(self.calc)

        # Should use minimum OA because it's too hot
        self.assertEqual(self.node.results["effective_oa_fraction"], 0.15)

    def test_compute_enthalpy_economizer(self):
        """Test enthalpy-based economizer control."""
        self.node.parameters["economizer_mode"] = "enthalpy"
        self.node.parameters["min_oa_fraction"] = 0.15
        self.node.parameters["econ_high_limit_h"] = 25.0  # Low limit to force lockout

        self.node.compute(self.calc)

        # Should use minimum OA
        self.assertEqual(self.node.results["effective_oa_fraction"], 0.15)

    def test_results(self):
        """Test that results are populated."""
        self.node.parameters["economizer_mode"] = "fixed"
        self.node.parameters["primary_fraction"] = 0.20

        self.node.compute(self.calc)

        self.assertIn("mixed_state", self.node.results)
        self.assertIn("total_mass_flow", self.node.results)
        self.assertIn("mixed_db", self.node.results)
        self.assertIn("mixed_rh", self.node.results)
        self.assertIn("effective_oa_fraction", self.node.results)

    def test_error_missing_primary(self):
        """Test error when primary inlet is missing."""
        self.node.ports["primary"].air_state = None
        with self.assertRaises(ValueError) as context:
            self.node.compute(self.calc)
        self.assertIn("primary", str(context.exception).lower())

    def test_error_missing_secondary(self):
        """Test error when secondary inlet is missing."""
        self.node.ports["secondary"].air_state = None
        with self.assertRaises(ValueError) as context:
            self.node.compute(self.calc)
        self.assertIn("secondary", str(context.exception).lower())


class TestAirSinkNode(unittest.TestCase):
    """Test AirSinkNode (zone or exhaust)."""

    def setUp(self):
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)
        self.node = AirSinkNode(name="Test Zone")

        # Create an entering air state
        self.entering_state = self.calc.from_db_rh(75.0, 0.50)
        self.node.ports["inlet"].air_state = self.entering_state
        self.node.ports["inlet"].mass_flow = 1000.0

    def test_init(self):
        """Test node initialization."""
        self.assertEqual(self.node.NODE_TYPE, "air_sink")
        self.assertEqual(self.node.DISPLAY_NAME, "Air Sink")

    def test_ports(self):
        """Test port configuration."""
        self.assertEqual(len(self.node.ports), 1)
        self.assertIn("inlet", self.node.ports)
        self.assertEqual(self.node.ports["inlet"].direction, "inlet")

    def test_compute(self):
        """Test sink computation."""
        self.node.compute(self.calc)

        self.assertIn("inlet_state", self.node.results)
        self.assertIn("mass_flow", self.node.results)
        self.assertEqual(self.node.results["mass_flow"], 1000.0)


if __name__ == "__main__":
    unittest.main()
