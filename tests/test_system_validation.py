"""Unit tests for unusual system configuration validation."""

import unittest

from hvac_flow.engine.constants import UnitSystem
from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.air_sink import AirSinkNode
from hvac_flow.models.connector import Connector
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.desiccant_wheel import DesiccantWheelNode
from hvac_flow.models.enthalpy_wheel import EnthalpyWheelNode
from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.models.heating_coil import HeatingCoilNode
from hvac_flow.models.mixing_box import MixingBoxNode
from hvac_flow.models.runaround_loop import RunaroundLoopNode
from hvac_flow.models.sensible_heat_recovery import SensibleHeatRecoveryNode
from hvac_flow.models.source_node import SourceNode
from hvac_flow.validation.system_validator import SystemValidator


class TestUnusualConfigurations(unittest.TestCase):
    """Test validation of unusual HVAC system configurations."""

    def setUp(self):
        self.graph = FlowGraph()
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)
        self.validator = SystemValidator()

    def test_heat_recovery_with_cooling(self):
        """Test system with heat recovery followed by cooling."""
        # Common in DOAS (Dedicated Outdoor Air Systems)
        oa = SourceNode(name="Outdoor Air")
        hr = SensibleHeatRecoveryNode(name="Heat Recovery")
        coil = CoolingCoilNode(name="Cooling Coil")
        sink = AirSinkNode(name="Zone")

        oa.parameters["dry_bulb"] = 95.0
        oa.parameters["relative_humidity"] = 0.50
        oa.parameters["mass_flow"] = 1000.0

        hr.parameters["effectiveness"] = 0.75

        coil.parameters["leaving_db"] = 55.0
        coil.parameters["leaving_mode"] = "rh"
        coil.parameters["leaving_rh"] = 0.90

        for node in [oa, hr, coil, sink]:
            self.graph.add_node(node)

        connections = [
            (oa, "outlet", hr, "inlet"),
            (hr, "outlet", coil, "inlet"),
            (coil, "outlet", sink, "inlet"),
        ]

        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            self.graph.add_connector(conn)

        # Should warn about potential for overcooling
        warnings = self.validator.validate_configuration(self.graph)
        self.assertTrue(any("heat recovery" in w.lower() for w in warnings))

    def test_series_cooling_heating(self):
        """Test validation of series cooling followed by heating."""
        source = SourceNode(name="Source")
        cool = CoolingCoilNode(name="Cooling Coil")
        heat = HeatingCoilNode(name="Reheat Coil")
        sink = AirSinkNode(name="Zone")

        source.parameters["dry_bulb"] = 75.0
        source.parameters["relative_humidity"] = 0.50
        source.parameters["mass_flow"] = 1000.0

        cool.parameters["leaving_db"] = 55.0
        cool.parameters["leaving_mode"] = "rh"
        cool.parameters["leaving_rh"] = 0.90

        heat.parameters["leaving_db"] = 75.0

        for node in [source, cool, heat, sink]:
            self.graph.add_node(node)

        connections = [
            (source, "outlet", cool, "inlet"),
            (cool, "outlet", heat, "inlet"),
            (heat, "outlet", sink, "inlet"),
        ]

        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            self.graph.add_connector(conn)

        # Should warn about energy waste
        warnings = self.validator.validate_configuration(self.graph)
        self.assertTrue(any("energy" in w.lower() or "waste" in w.lower() for w in warnings))

    def test_100_percent_outdoor_air(self):
        """Test validation of 100% OA system without heat recovery."""
        oa = SourceNode(name="Outdoor Air")
        coil = CoolingCoilNode(name="Cooling Coil")
        sink = AirSinkNode(name="Zone")

        oa.parameters["dry_bulb"] = 95.0
        oa.parameters["relative_humidity"] = 0.80  # Very humid
        oa.parameters["mass_flow"] = 5000.0  # High flow

        coil.parameters["leaving_db"] = 55.0
        coil.parameters["leaving_mode"] = "rh"
        coil.parameters["leaving_rh"] = 0.90

        for node in [oa, coil, sink]:
            self.graph.add_node(node)

        connections = [
            (oa, "outlet", coil, "inlet"),
            (coil, "outlet", sink, "inlet"),
        ]

        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            self.graph.add_connector(conn)

        # Should warn about high energy use
        warnings = self.validator.validate_configuration(self.graph)
        self.assertTrue(any("100%" in w or "outdoor air" in w.lower() for w in warnings))

    def test_multiple_mixing_boxes(self):
        """Test system with multiple mixing boxes (unusual)."""
        oa = SourceNode(name="Outdoor Air")
        mixer1 = MixingBoxNode(name="Mixing Box 1")
        coil = CoolingCoilNode(name="Cooling Coil")
        mixer2 = MixingBoxNode(name="Mixing Box 2")
        sink = AirSinkNode(name="Zone")

        # This is an unusual configuration
        for node in [oa, mixer1, coil, mixer2, sink]:
            self.graph.add_node(node)

        connections = [
            (oa, "outlet", mixer1, "primary"),
            (mixer1, "mixed", coil, "inlet"),
            (coil, "outlet", mixer2, "primary"),
            (mixer2, "mixed", sink, "inlet"),
        ]

        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            self.graph.add_connector(conn)

        # Should warn about multiple mixing boxes
        warnings = self.validator.validate_configuration(self.graph)
        self.assertTrue(any("multiple" in w.lower() and "mix" in w.lower() for w in warnings))

    def test_no_preheat_in_cold_climate(self):
        """Test warning for missing preheat in cold climate."""
        oa = SourceNode(name="Outdoor Air")
        mixer = MixingBoxNode(name="Mixing Box")
        coil = CoolingCoilNode(name="Cooling Coil")
        sink = AirSinkNode(name="Zone")

        # Very cold outdoor air
        oa.parameters["dry_bulb"] = -10.0
        oa.parameters["relative_humidity"] = 0.80
        oa.parameters["mass_flow"] = 1000.0

        mixer.parameters["economizer_mode"] = "fixed"
        mixer.parameters["primary_fraction"] = 0.20

        coil.parameters["leaving_db"] = 55.0
        coil.parameters["leaving_mode"] = "rh"
        coil.parameters["leaving_rh"] = 0.90

        for node in [oa, mixer, coil, sink]:
            self.graph.add_node(node)

        connections = [
            (oa, "outlet", mixer, "primary"),
            (mixer, "mixed", coil, "inlet"),
            (coil, "outlet", sink, "inlet"),
        ]

        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            self.graph.add_connector(conn)

        # Should warn about missing preheat
        warnings = self.validator.validate_configuration(self.graph)
        self.assertTrue(any("preheat" in w.lower() or "freeze" in w.lower() for w in warnings))

    def test_excessive_pressure_drops(self):
        """Test detection of excessive components in series."""
        source = SourceNode(name="Source")
        coil1 = CoolingCoilNode(name="Coil 1")
        coil2 = CoolingCoilNode(name="Coil 2")
        coil3 = CoolingCoilNode(name="Coil 3")
        sink = AirSinkNode(name="Zone")

        source.parameters["dry_bulb"] = 75.0
        source.parameters["relative_humidity"] = 0.50
        source.parameters["mass_flow"] = 1000.0

        for node in [source, coil1, coil2, coil3, sink]:
            self.graph.add_node(node)

        connections = [
            (source, "outlet", coil1, "inlet"),
            (coil1, "outlet", coil2, "inlet"),
            (coil2, "outlet", coil3, "inlet"),
            (coil3, "outlet", sink, "inlet"),
        ]

        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            self.graph.add_connector(conn)

        # Should warn about excessive pressure drops
        warnings = self.validator.validate_configuration(self.graph)
        self.assertTrue(any("pressure" in w.lower() or "multiple" in w.lower() for w in warnings))


class TestAdvancedHeatRecovery(unittest.TestCase):
    """Test advanced heat recovery configurations."""

    def setUp(self):
        self.graph = FlowGraph()
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)
        self.validator = SystemValidator()

    def test_runaround_loop(self):
        """Test runaround loop heat recovery system."""
        oa = SourceNode(name="Outdoor Air")
        ra = SourceNode(name="Return Air")
        runaround = RunaroundLoopNode(name="Runaround Loop")
        coil = CoolingCoilNode(name="Cooling Coil")
        sink = AirSinkNode(name="Zone")

        oa.parameters["dry_bulb"] = 95.0
        oa.parameters["relative_humidity"] = 0.50
        oa.parameters["mass_flow"] = 1000.0

        ra.parameters["dry_bulb"] = 75.0
        ra.parameters["relative_humidity"] = 0.50
        ra.parameters["mass_flow"] = 1000.0

        runaround.parameters["effectiveness"] = 0.60

        coil.parameters["leaving_db"] = 55.0
        coil.parameters["leaving_mode"] = "rh"
        coil.parameters["leaving_rh"] = 0.90

        for node in [oa, ra, runaround, coil, sink]:
            self.graph.add_node(node)

        # Runaround has two air streams
        connections = [
            (oa, "outlet", runaround, "supply_inlet"),
            (ra, "outlet", runaround, "exhaust_inlet"),
            (runaround, "supply_outlet", coil, "inlet"),
            (coil, "outlet", sink, "inlet"),
        ]

        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            self.graph.add_connector(conn)

        # Should validate successfully
        warnings = self.validator.validate_configuration(self.graph)
        # No critical warnings expected

    def test_desiccant_wheel(self):
        """Test desiccant wheel dehumidification system."""
        oa = SourceNode(name="Outdoor Air")
        desiccant = DesiccantWheelNode(name="Desiccant Wheel")
        coil = CoolingCoilNode(name="Cooling Coil")
        sink = AirSinkNode(name="Zone")

        oa.parameters["dry_bulb"] = 85.0
        oa.parameters["relative_humidity"] = 0.70  # High humidity
        oa.parameters["mass_flow"] = 1000.0

        desiccant.parameters["moisture_removal"] = 0.005  # lb/lb
        desiccant.parameters["sensible_effectiveness"] = 0.80

        coil.parameters["leaving_db"] = 55.0
        coil.parameters["leaving_mode"] = "rh"
        coil.parameters["leaving_rh"] = 0.90

        for node in [oa, desiccant, coil, sink]:
            self.graph.add_node(node)

        connections = [
            (oa, "outlet", desiccant, "inlet"),
            (desiccant, "outlet", coil, "inlet"),
            (coil, "outlet", sink, "inlet"),
        ]

        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            self.graph.add_connector(conn)

        # Should validate successfully
        warnings = self.validator.validate_configuration(self.graph)

    def test_enthalpy_wheel(self):
        """Test enthalpy wheel (total energy recovery)."""
        oa = SourceNode(name="Outdoor Air")
        ra = SourceNode(name="Return Air")
        wheel = EnthalpyWheelNode(name="Enthalpy Wheel")
        coil = CoolingCoilNode(name="Cooling Coil")
        sink = AirSinkNode(name="Zone")

        oa.parameters["dry_bulb"] = 95.0
        oa.parameters["relative_humidity"] = 0.60
        oa.parameters["mass_flow"] = 1000.0

        ra.parameters["dry_bulb"] = 75.0
        ra.parameters["relative_humidity"] = 0.50
        ra.parameters["mass_flow"] = 1000.0

        wheel.parameters["sensible_effectiveness"] = 0.75
        wheel.parameters["latent_effectiveness"] = 0.60

        coil.parameters["leaving_db"] = 55.0
        coil.parameters["leaving_mode"] = "rh"
        coil.parameters["leaving_rh"] = 0.90

        for node in [oa, ra, wheel, coil, sink]:
            self.graph.add_node(node)

        connections = [
            (oa, "outlet", wheel, "supply_inlet"),
            (ra, "outlet", wheel, "exhaust_inlet"),
            (wheel, "supply_outlet", coil, "inlet"),
            (coil, "outlet", sink, "inlet"),
        ]

        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            self.graph.add_connector(conn)

        warnings = self.validator.validate_configuration(self.graph)


class TestSystemEfficiencyWarnings(unittest.TestCase):
    """Test warnings about system efficiency."""

    def setUp(self):
        self.graph = FlowGraph()
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)
        self.validator = SystemValidator()

    def test_low_economizer_utilization(self):
        """Test warning when economizer is underutilized."""
        oa = SourceNode(name="Outdoor Air")
        ra = SourceNode(name="Return Air")
        mixer = MixingBoxNode(name="Mixing Box")
        coil = CoolingCoilNode(name="Cooling Coil")
        sink = AirSinkNode(name="Zone")

        # Cool outdoor air (good for economizing)
        oa.parameters["dry_bulb"] = 65.0
        oa.parameters["relative_humidity"] = 0.50
        oa.parameters["mass_flow"] = 200.0

        ra.parameters["dry_bulb"] = 75.0
        ra.parameters["relative_humidity"] = 0.50
        ra.parameters["mass_flow"] = 800.0

        # But using fixed mode with minimum OA
        mixer.parameters["economizer_mode"] = "fixed"
        mixer.parameters["primary_fraction"] = 0.20

        coil.parameters["leaving_db"] = 55.0
        coil.parameters["leaving_mode"] = "rh"
        coil.parameters["leaving_rh"] = 0.90

        for node in [oa, ra, mixer, coil, sink]:
            self.graph.add_node(node)

        connections = [
            (oa, "outlet", mixer, "primary"),
            (ra, "outlet", mixer, "secondary"),
            (mixer, "mixed", coil, "inlet"),
            (coil, "outlet", sink, "inlet"),
        ]

        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            self.graph.add_connector(conn)

        # Should warn about not using economizer when beneficial
        warnings = self.validator.validate_configuration(self.graph)
        self.assertTrue(any("economizer" in w.lower() for w in warnings))


if __name__ == "__main__":
    unittest.main()
