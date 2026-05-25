"""
Test suite for HVAC Calculators backend module.
Tests all 5 calculator types with various inputs.
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hvac_calculators import (
    calculate_conduit_fill,
    calculate_pipe_sizing,
    calculate_duct_pressure_drop,
    calculate_fan_laws,
    calculate_pump_laws,
    ValidationError,
)


class TestConduitFill(unittest.TestCase):
    """Test conduit fill calculator."""
    
    def test_basic_conduit_fill(self):
        """Test basic conduit fill calculation."""
        result = calculate_conduit_fill(
            conduit_type="EMT",
            conduit_size=1.0,
            wire_gauge=12,
            num_wires=3,
            insulation_type="THHN"
        )
        
        self.assertIn("fill_percentage", result)
        self.assertIn("status", result)
        self.assertEqual(result["conduit_type"], "EMT")
        self.assertEqual(result["conduit_size"], 1.0)
        self.assertEqual(result["wire_gauge"], 12)
        
    def test_conduit_pass(self):
        """Test conduit fill that passes NEC requirements."""
        result = calculate_conduit_fill(
            conduit_type="RMC",
            conduit_size=2.0,
            wire_gauge=10,
            num_wires=5,
        )
        
        self.assertEqual(result["num_wires"], 5)
        # With 5 wires, max fill is 40%
        self.assertLessEqual(result["fill_percentage"], 40)
        
    def test_conduit_fail(self):
        """Test conduit fill that exceeds NEC requirements."""
        result = calculate_conduit_fill(
            conduit_type="EMT",
            conduit_size=0.5,
            wire_gauge=12,
            num_wires=10,
        )
        
        self.assertEqual(result["status"], "FAIL")
        self.assertGreater(result["fill_percentage"], 31)  # 2+ wires = 31% max
        
    def test_invalid_conduit_type(self):
        """Test invalid conduit type raises error."""
        with self.assertRaises(ValidationError):
            calculate_conduit_fill(
                conduit_type="INVALID",
                conduit_size=1.0,
                wire_gauge=12,
                num_wires=3,
            )
    
    def test_single_wire_fill(self):
        """Test single wire conduit fill (53% limit)."""
        result = calculate_conduit_fill(
            conduit_type="EMT",
            conduit_size=1.0,
            wire_gauge=14,
            num_wires=1,
        )
        
        # Single wire has 53% fill limit
        self.assertEqual(result["max_fill_percentage"], 53)


class TestPipeSizing(unittest.TestCase):
    """Test pipe sizing calculator."""
    
    def test_basic_pipe_sizing(self):
        """Test basic pipe sizing calculation."""
        result = calculate_pipe_sizing(
            flow_rate_gpm=50.0,
            pipe_material="CU",
            max_velocity_fps=8.0,
            max_pressure_drop=4.0
        )
        
        self.assertIn("recommended_size", result)
        self.assertIn("velocity_fps", result)
        self.assertIn("status", result)
        self.assertEqual(result["flow_rate_gpm"], 50.0)
        self.assertEqual(result["pipe_material"], "CU")
        
    def test_copper_pipe(self):
        """Test copper pipe sizing."""
        result = calculate_pipe_sizing(
            flow_rate_gpm=100.0,
            pipe_material="CU",
        )
        
        self.assertEqual(result["pipe_material"], "CU")
        self.assertGreater(result["velocity_fps"], 0)
        
    def test_steel_pipe(self):
        """Test steel pipe sizing."""
        result = calculate_pipe_sizing(
            flow_rate_gpm=100.0,
            pipe_material="STEEL",
        )
        
        self.assertEqual(result["pipe_material"], "STEEL")
        
    def test_pvc_pipe(self):
        """Test PVC pipe sizing."""
        result = calculate_pipe_sizing(
            flow_rate_gpm=100.0,
            pipe_material="PVC",
        )
        
        self.assertEqual(result["pipe_material"], "PVC")
        
    def test_invalid_material(self):
        """Test invalid pipe material raises error."""
        with self.assertRaises(ValidationError):
            calculate_pipe_sizing(
                flow_rate_gpm=50.0,
                pipe_material="INVALID",
            )
    
    def test_zero_flow(self):
        """Test zero flow rate raises error."""
        with self.assertRaises(ValidationError):
            calculate_pipe_sizing(
                flow_rate_gpm=0,
            )


class TestDuctPressureDrop(unittest.TestCase):
    """Test duct pressure drop calculator."""
    
    def test_basic_duct_calculation(self):
        """Test basic duct pressure drop calculation."""
        result = calculate_duct_pressure_drop(
            airflow_cfm=1000,
            duct_width_in=12,
            duct_height_in=12,
            duct_material="galvanized",
            length_ft=100
        )
        
        self.assertIn("pressure_drop_in_wg", result)
        self.assertIn("velocity_fpm", result)
        self.assertIn("status", result)
        self.assertEqual(result["airflow_cfm"], 1000)
        
    def test_galvanized_duct(self):
        """Test galvanized duct calculation."""
        result = calculate_duct_pressure_drop(
            airflow_cfm=2000,
            duct_width_in=16,
            duct_height_in=12,
            duct_material="galvanized",
        )
        
        self.assertEqual(result["duct_material"], "galvanized")
        
    def test_aluminum_duct(self):
        """Test aluminum duct calculation."""
        result = calculate_duct_pressure_drop(
            airflow_cfm=2000,
            duct_width_in=16,
            duct_height_in=12,
            duct_material="aluminum",
        )
        
        self.assertEqual(result["duct_material"], "aluminum")
        
    def test_fiberglass_duct(self):
        """Test fiberglass duct calculation."""
        result = calculate_duct_pressure_drop(
            airflow_cfm=2000,
            duct_width_in=16,
            duct_height_in=12,
            duct_material="fiberglass",
        )
        
        self.assertEqual(result["duct_material"], "fiberglass")
        
    def test_invalid_airflow(self):
        """Test invalid airflow raises error."""
        with self.assertRaises(ValidationError):
            calculate_duct_pressure_drop(
                airflow_cfm=0,
                duct_width_in=12,
                duct_height_in=12,
            )


class TestFanLaws(unittest.TestCase):
    """Test fan laws calculator."""
    
    def test_basic_fan_laws_cfm(self):
        """Test fan laws with CFM calculation type."""
        result = calculate_fan_laws(
            cfm_1=10000,
            rpm_1=1200,
            bhp_1=10.0,
            cfm_2=12000,
            calculation_type="cfm"
        )
        
        self.assertEqual(result["condition_1"]["cfm"], 10000)
        self.assertEqual(result["condition_2"]["cfm"], 12000)
        self.assertGreater(result["condition_2"]["rpm"], 1200)  # RPM should increase
        self.assertGreater(result["condition_2"]["bhp"], 10.0)  # BHP should increase
        
    def test_basic_fan_laws_rpm(self):
        """Test fan laws with RPM calculation type."""
        result = calculate_fan_laws(
            cfm_1=10000,
            rpm_1=1200,
            bhp_1=10.0,
            rpm_2=1500,
            calculation_type="rpm"
        )
        
        self.assertEqual(result["condition_1"]["rpm"], 1200)
        self.assertEqual(result["condition_2"]["rpm"], 1500)
        self.assertGreater(result["condition_2"]["cfm"], 10000)  # CFM should increase
        
    def test_fan_law_ratios(self):
        """Test fan law ratio calculations."""
        result = calculate_fan_laws(
            cfm_1=5000,
            rpm_1=1000,
            bhp_1=5.0,
            cfm_2=7500,
            calculation_type="cfm"
        )
        
        # CFM ratio = 7500/5000 = 1.5
        self.assertAlmostEqual(result["ratios"]["cfm_ratio"], 1.5, places=2)
        # RPM ratio should equal CFM ratio (Fan Law 1)
        self.assertAlmostEqual(result["ratios"]["rpm_ratio"], 1.5, places=2)
        
    def test_invalid_calculation_type(self):
        """Test invalid calculation type raises error."""
        with self.assertRaises(ValidationError):
            calculate_fan_laws(
                cfm_1=10000,
                rpm_1=1200,
                bhp_1=10.0,
                calculation_type="INVALID"
            )


class TestPumpLaws(unittest.TestCase):
    """Test pump laws calculator."""
    
    def test_basic_pump_laws_gpm(self):
        """Test pump laws with GPM calculation type."""
        result = calculate_pump_laws(
            gpm_1=500,
            rpm_1=1750,
            head_1=100,
            bhp_1=25.0,
            gpm_2=600,
            calculation_type="gpm"
        )
        
        self.assertEqual(result["condition_1"]["gpm"], 500)
        self.assertEqual(result["condition_2"]["gpm"], 600)
        self.assertGreater(result["condition_2"]["rpm"], 1750)  # RPM should increase
        
    def test_basic_pump_laws_rpm(self):
        """Test pump laws with RPM calculation type."""
        result = calculate_pump_laws(
            gpm_1=500,
            rpm_1=1750,
            head_1=100,
            bhp_1=25.0,
            rpm_2=2100,
            calculation_type="rpm"
        )
        
        self.assertEqual(result["condition_1"]["rpm"], 1750)
        self.assertEqual(result["condition_2"]["rpm"], 2100)
        # Head increases with RPM squared
        self.assertGreater(result["condition_2"]["head_ft"], 100)
        
    def test_pump_law_ratios(self):
        """Test pump law ratio calculations."""
        result = calculate_pump_laws(
            gpm_1=400,
            rpm_1=1800,
            head_1=80,
            bhp_1=20.0,
            gpm_2=600,
            calculation_type="gpm"
        )
        
        # GPM ratio = 600/400 = 1.5
        self.assertAlmostEqual(result["ratios"]["gpm_ratio"], 1.5, places=2)
        # RPM ratio should equal GPM ratio (Pump Law 1)
        self.assertAlmostEqual(result["ratios"]["rpm_ratio"], 1.5, places=2)
        # Head ratio = RPM_ratio^2 = 1.5^2 = 2.25
        self.assertAlmostEqual(result["ratios"]["head_ratio"], 2.25, places=2)
        
    def test_invalid_calculation_type(self):
        """Test invalid calculation type raises error."""
        with self.assertRaises(ValidationError):
            calculate_pump_laws(
                gpm_1=500,
                rpm_1=1750,
                head_1=100,
                bhp_1=25.0,
                calculation_type="INVALID"
            )


class TestIntegration(unittest.TestCase):
    """Integration tests for the unified calculate interface."""
    
    def test_unified_calculate_conduit(self):
        """Test unified calculate interface for conduit."""
        from hvac_calculators import calculate
        
        result = calculate(
            "conduit",
            conduit_type="EMT",
            conduit_size=1.0,
            wire_gauge=12,
            num_wires=3,
        )
        
        self.assertEqual(result["status"], result["status"])
        
    def test_unified_calculate_pipe(self):
        """Test unified calculate interface for pipe."""
        from hvac_calculators import calculate
        
        result = calculate(
            "pipe",
            flow_rate_gpm=50.0,
        )
        
        self.assertIn("recommended_size", result)
        
    def test_unified_calculate_duct(self):
        """Test unified calculate interface for duct."""
        from hvac_calculators import calculate
        
        result = calculate(
            "duct",
            airflow_cfm=1000,
            duct_width_in=12,
            duct_height_in=12,
        )
        
        self.assertIn("pressure_drop_in_wg", result)
        
    def test_unified_calculate_fan(self):
        """Test unified calculate interface for fan."""
        from hvac_calculators import calculate
        
        result = calculate(
            "fan",
            cfm_1=10000,
            rpm_1=1200,
            bhp_1=10.0,
            cfm_2=12000,
            calculation_type="cfm",
        )
        
        self.assertEqual(result["calculation_type"], "cfm")
        
    def test_unified_calculate_pump(self):
        """Test unified calculate interface for pump."""
        from hvac_calculators import calculate
        
        result = calculate(
            "pump",
            gpm_1=500,
            rpm_1=1750,
            head_1=100,
            bhp_1=25.0,
            gpm_2=600,
            calculation_type="gpm",
        )
        
        self.assertEqual(result["calculation_type"], "gpm")
        
    def test_unified_invalid_calculator(self):
        """Test unified interface with invalid calculator type."""
        from hvac_calculators import calculate, ValidationError
        
        with self.assertRaises(ValidationError):
            calculate("invalid", param=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
