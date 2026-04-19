"""Unit tests for FlowSolver."""

import unittest

from hvac_flow.engine.constants import UnitSystem
from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.air_sink import AirSinkNode
from hvac_flow.models.connector import Connector
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.fan import FanNode
from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.models.heating_coil import HeatingCoilNode
from hvac_flow.models.mixing_box import MixingBoxNode
from hvac_flow.models.source_node import SourceNode
from hvac_flow.solver.flow_solver import FlowSolver


class TestFlowSolverBasic(unittest.TestCase):
    """Test basic FlowSolver functionality."""

    def setUp(self):
        """Create a simple AHU: Source -> Cooling Coil -> Fan -> Sink."""
        self.graph = FlowGraph()
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)

        # Create nodes
        self.source = SourceNode(name="OA Intake")
        self.coil = CoolingCoilNode(name="Cooling Coil")
        self.fan = FanNode(name="Supply Fan")
        self.sink = AirSinkNode(name="Zone")

        # Configure source
        self.source.parameters["dry_bulb"] = 95.0
        self.source.parameters["relative_humidity"] = 0.40
        self.source.parameters["mass_flow"] = 2000.0

        # Configure coil
        self.coil.parameters["leaving_db"] = 55.0
        self.coil.parameters["leaving_mode"] = "rh"
        self.coil.parameters["leaving_rh"] = 0.90

        # Configure fan
        self.fan.parameters["input_mode"] = "bhp"
        self.fan.parameters["bhp"] = 15.0
        self.fan.parameters["motor_efficiency"] = 0.90

        # Add to graph
        self.graph.add_node(self.source)
        self.graph.add_node(self.coil)
        self.graph.add_node(self.fan)
        self.graph.add_node(self.sink)

        # Connect
        conn1 = Connector(
            source_node_id=self.source.id, source_port_name="outlet",
            target_node_id=self.coil.id, target_port_name="inlet"
        )
        conn2 = Connector(
            source_node_id=self.coil.id, source_port_name="outlet",
            target_node_id=self.fan.id, target_port_name="inlet"
        )
        conn3 = Connector(
            source_node_id=self.fan.id, source_port_name="outlet",
            target_node_id=self.sink.id, target_port_name="inlet"
        )

        self.graph.add_connector(conn1)
        self.graph.add_connector(conn2)
        self.graph.add_connector(conn3)

        # Create solver
        self.solver = FlowSolver(self.graph, self.calc)

    def test_solve_success(self):
        """Test successful solve."""
        success = self.solver.solve()
        self.assertTrue(success)
        self.assertEqual(len(self.solver.errors), 0)

    def test_air_state_propagation(self):
        """Test that air states propagate through the system."""
        self.solver.solve()

        # Check that all nodes have computed
        self.assertIsNotNone(self.coil.ports["outlet"].air_state)
        self.assertIsNotNone(self.fan.ports["outlet"].air_state)

        # Coil should have cooled the air
        coil_outlet = self.coil.ports["outlet"].air_state
        self.assertEqual(coil_outlet.dry_bulb, 55.0)

        # Fan should have heated the air slightly
        fan_outlet = self.fan.ports["outlet"].air_state
        self.assertGreater(fan_outlet.dry_bulb, coil_outlet.dry_bulb)

    def test_mass_flow_propagation(self):
        """Test that mass flow propagates through the system."""
        self.solver.solve()

        # All nodes should have the same mass flow
        self.assertEqual(self.coil.ports["inlet"].mass_flow, 2000.0)
        self.assertEqual(self.coil.ports["outlet"].mass_flow, 2000.0)
        self.assertEqual(self.fan.ports["inlet"].mass_flow, 2000.0)
        self.assertEqual(self.fan.ports["outlet"].mass_flow, 2000.0)

    def test_all_states_collected(self):
        """Test that all outlet states are collected."""
        self.solver.solve()

        # Should have 3 outlet states (source, coil, fan)
        self.assertEqual(len(self.solver.all_states), 3)

    def test_node_results(self):
        """Test that node results are populated."""
        self.solver.solve()

        # Coil should have load results
        self.assertIn("total_load_btuh", self.coil.results)
        self.assertIn("sensible_load_btuh", self.coil.results)
        self.assertIn("latent_load_btuh", self.coil.results)

        # Fan should have heat results
        self.assertIn("fan_heat_btuh", self.fan.results)

    def test_clear_previous_results(self):
        """Test that previous results are cleared on new solve."""
        # First solve
        self.solver.solve()
        first_states = list(self.solver.all_states)

        # Modify and solve again
        self.source.parameters["dry_bulb"] = 85.0
        self.solver.solve()

        # Should have new states
        self.assertNotEqual(
            self.source.results["outlet_state"].dry_bulb,
            first_states[0].dry_bulb
        )


class TestFlowSolverWithMixing(unittest.TestCase):
    """Test solver with mixing box (economizer)."""

    def setUp(self):
        """Create: OA Source -> Mixer <- RA Source, Mixer -> Coil -> Fan -> Zone."""
        self.graph = FlowGraph()
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)

        # Create nodes
        self.oa_source = SourceNode(name="Outdoor Air")
        self.ra_source = SourceNode(name="Return Air")
        self.mixer = MixingBoxNode(name="Mixing Box")
        self.coil = CoolingCoilNode(name="Cooling Coil")
        self.fan = FanNode(name="Supply Fan")
        self.sink = AirSinkNode(name="Zone")

        # Configure sources
        self.oa_source.parameters["dry_bulb"] = 95.0
        self.oa_source.parameters["relative_humidity"] = 0.40
        self.oa_source.parameters["mass_flow"] = 400.0  # 20% of total

        self.ra_source.parameters["dry_bulb"] = 75.0
        self.ra_source.parameters["relative_humidity"] = 0.50
        self.ra_source.parameters["mass_flow"] = 1600.0  # 80% of total

        # Configure mixer
        self.mixer.parameters["economizer_mode"] = "fixed"
        self.mixer.parameters["primary_fraction"] = 0.20

        # Configure coil
        self.coil.parameters["leaving_db"] = 55.0
        self.coil.parameters["leaving_mode"] = "rh"
        self.coil.parameters["leaving_rh"] = 0.90

        # Configure fan
        self.fan.parameters["input_mode"] = "temp_rise"
        self.fan.parameters["temp_rise"] = 2.0

        # Add to graph
        for node in [self.oa_source, self.ra_source, self.mixer, self.coil,
                     self.fan, self.sink]:
            self.graph.add_node(node)

        # Connect
        connections = [
            (self.oa_source, "outlet", self.mixer, "primary"),
            (self.ra_source, "outlet", self.mixer, "secondary"),
            (self.mixer, "mixed", self.coil, "inlet"),
            (self.coil, "outlet", self.fan, "inlet"),
            (self.fan, "outlet", self.sink, "inlet"),
        ]

        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            self.graph.add_connector(conn)

        self.solver = FlowSolver(self.graph, self.calc)

    def test_mixing_solve(self):
        """Test solve with mixing box."""
        success = self.solver.solve()
        self.assertTrue(success)

    def test_mixed_air_temperature(self):
        """Test that mixed air temperature is calculated correctly."""
        self.solver.solve()

        mixed_state = self.mixer.ports["mixed"].air_state
        # Should be between OA (95°F) and RA (75°F)
        self.assertGreater(mixed_state.dry_bulb, 75.0)
        self.assertLess(mixed_state.dry_bulb, 95.0)

        # With 20% OA, should be closer to RA
        # Rough check: 0.2*95 + 0.8*75 = 79°F
        self.assertAlmostEqual(mixed_state.dry_bulb, 79.0, delta=3.0)

    def test_total_mass_flow(self):
        """Test that total mass flow is maintained."""
        self.solver.solve()

        # Mixer outlet should have combined flow
        self.assertEqual(self.mixer.ports["mixed"].mass_flow, 2000.0)

        # Downstream nodes should maintain this flow
        self.assertEqual(self.coil.ports["inlet"].mass_flow, 2000.0)
        self.assertEqual(self.fan.ports["outlet"].mass_flow, 2000.0)


class TestFlowSolverErrors(unittest.TestCase):
    """Test solver error handling."""

    def setUp(self):
        self.graph = FlowGraph()
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)

    def test_empty_graph(self):
        """Test error on empty graph."""
        solver = FlowSolver(self.graph, self.calc)
        success = solver.solve()
        self.assertFalse(success)
        self.assertTrue(any("empty" in e.lower() for e in solver.errors))

    def test_unconnected_inlet(self):
        """Test error on unconnected required inlet."""
        coil = CoolingCoilNode(name="Coil")
        self.graph.add_node(coil)

        solver = FlowSolver(self.graph, self.calc)
        success = solver.solve()
        self.assertFalse(success)
        self.assertTrue(any("inlet" in e.lower() for e in solver.errors))

    def test_missing_upstream_state(self):
        """Test handling of missing upstream air state."""
        source = SourceNode(name="Source")
        coil = CoolingCoilNode(name="Coil")

        # Don't configure source (no air state computed)
        self.graph.add_node(source)
        self.graph.add_node(coil)

        conn = Connector(
            source_node_id=source.id, source_port_name="outlet",
            target_node_id=coil.id, target_port_name="inlet"
        )
        self.graph.add_connector(conn)

        solver = FlowSolver(self.graph, self.calc)
        success = solver.solve()
        self.assertFalse(success)

    def test_cycle_detection(self):
        """Test detection of cycles in graph."""
        node1 = CoolingCoilNode(name="Coil 1")
        node2 = FanNode(name="Fan")

        self.graph.add_node(node1)
        self.graph.add_node(node2)

        # Create cycle: 1 -> 2 -> 1
        conn1 = Connector(
            source_node_id=node1.id, source_port_name="outlet",
            target_node_id=node2.id, target_port_name="inlet"
        )
        conn2 = Connector(
            source_node_id=node2.id, source_port_name="outlet",
            target_node_id=node1.id, target_port_name="inlet"
        )
        self.graph.add_connector(conn1)
        self.graph.add_connector(conn2)

        solver = FlowSolver(self.graph, self.calc)
        success = solver.solve()
        self.assertFalse(success)
        self.assertTrue(any("cycle" in e.lower() for e in solver.errors))


class TestFlowSolverBoundaryConditions(unittest.TestCase):
    """Test boundary condition checking in solver."""

    def setUp(self):
        """Create a simple system with limited capacity."""
        self.graph = FlowGraph()
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)

        self.source = SourceNode(name="OA")
        self.coil = CoolingCoilNode(name="Small Coil")

        # Configure for high load
        self.source.parameters["dry_bulb"] = 100.0
        self.source.parameters["relative_humidity"] = 0.50
        self.source.parameters["mass_flow"] = 5000.0

        self.coil.parameters["leaving_db"] = 55.0
        self.coil.parameters["leaving_mode"] = "rh"
        self.coil.parameters["leaving_rh"] = 0.90

        # Set low capacity boundary
        self.coil.boundary_conditions["total_load_btuh"] = 50000.0

        self.graph.add_node(self.source)
        self.graph.add_node(self.coil)

        conn = Connector(
            source_node_id=self.source.id, source_port_name="outlet",
            target_node_id=self.coil.id, target_port_name="inlet"
        )
        self.graph.add_connector(conn)

        self.solver = FlowSolver(self.graph, self.calc)

    def test_boundary_warning_generation(self):
        """Test that boundary warnings are generated."""
        self.solver.solve()

        # Should have warnings about exceeding capacity
        self.assertGreater(len(self.solver.warnings), 0)
        self.assertTrue(any("exceeds" in w.lower() for w in self.solver.warnings))

    def test_node_specific_warnings(self):
        """Test that warnings are tracked per node."""
        self.solver.solve()

        self.assertIn(self.coil.id, self.solver.node_warnings)
        self.assertGreater(len(self.solver.node_warnings[self.coil.id]), 0)


class TestFlowSolverDuctLosses(unittest.TestCase):
    """Test duct loss modeling in solver."""

    def setUp(self):
        self.graph = FlowGraph()
        self.calc = PsychroCalc(unit_system=UnitSystem.IP)

        self.source = SourceNode(name="OA")
        self.coil = CoolingCoilNode(name="Coil")

        self.source.parameters["dry_bulb"] = 95.0
        self.source.parameters["relative_humidity"] = 0.40
        self.source.parameters["mass_flow"] = 2000.0

        self.coil.parameters["leaving_db"] = 55.0
        self.coil.parameters["leaving_mode"] = "rh"
        self.coil.parameters["leaving_rh"] = 0.90

        self.graph.add_node(self.source)
        self.graph.add_node(self.coil)

        # Add connector with duct losses
        conn = Connector(
            source_node_id=self.source.id, source_port_name="outlet",
            target_node_id=self.coil.id, target_port_name="inlet",
            model_duct_losses=True,
            duct_ua=50.0,  # Btu/(hr·°F)
            ambient_temp=100.0  # Hot attic
        )
        self.graph.add_connector(conn)

        self.solver = FlowSolver(self.graph, self.calc)

    def test_duct_heat_gain(self):
        """Test that duct heat gain is applied."""
        self.solver.solve()

        # Air entering coil should be warmer than source due to duct gain
        entering_temp = self.coil.ports["inlet"].air_state.dry_bulb
        self.assertGreater(entering_temp, 95.0)


if __name__ == "__main__":
    unittest.main()
