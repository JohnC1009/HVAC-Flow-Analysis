"""Unit tests for FlowGraph and connectivity."""

import unittest

from hvac_flow.models.base_node import Port
from hvac_flow.models.connector import Connector
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.fan import FanNode
from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.models.heating_coil import HeatingCoilNode
from hvac_flow.models.mixing_box import MixingBoxNode
from hvac_flow.models.source_node import SourceNode


class TestFlowGraphBasics(unittest.TestCase):
    """Test basic FlowGraph operations."""

    def setUp(self):
        """Create a fresh graph for each test."""
        self.graph = FlowGraph()

    def test_add_node(self):
        """Test adding nodes to the graph."""
        node = CoolingCoilNode(name="Test Coil")
        self.graph.add_node(node)
        self.assertEqual(len(self.graph.nodes), 1)
        self.assertIn(node.id, self.graph.nodes)

    def test_remove_node(self):
        """Test removing nodes from the graph."""
        node = CoolingCoilNode(name="Test Coil")
        self.graph.add_node(node)
        self.graph.remove_node(node.id)
        self.assertEqual(len(self.graph.nodes), 0)

    def test_add_connector(self):
        """Test adding connectors between nodes."""
        node1 = CoolingCoilNode(name="Coil 1")
        node2 = FanNode(name="Fan 1")
        self.graph.add_node(node1)
        self.graph.add_node(node2)

        connector = Connector(
            source_node_id=node1.id,
            source_port_name="outlet",
            target_node_id=node2.id,
            target_port_name="inlet"
        )
        self.graph.add_connector(connector)

        self.assertEqual(len(self.graph.connectors), 1)
        self.assertIn(connector.id, self.graph.connectors)

    def test_remove_connector(self):
        """Test removing connectors."""
        node1 = CoolingCoilNode(name="Coil 1")
        node2 = FanNode(name="Fan 1")
        self.graph.add_node(node1)
        self.graph.add_node(node2)

        connector = Connector(
            source_node_id=node1.id,
            source_port_name="outlet",
            target_node_id=node2.id,
            target_port_name="inlet"
        )
        self.graph.add_connector(connector)
        self.graph.remove_connector(connector.id)

        self.assertEqual(len(self.graph.connectors), 0)
        # Port connections should be cleared
        self.assertIsNone(node1.ports["outlet"].connected_to)
        self.assertIsNone(node2.ports["inlet"].connected_to)


class TestFlowGraphQueries(unittest.TestCase):
    """Test graph query operations."""

    def setUp(self):
        """Create a simple flow: Source -> Coil -> Fan."""
        self.graph = FlowGraph()
        self.source = SourceNode(name="OA Intake")
        self.coil = CoolingCoilNode(name="Cooling Coil")
        self.fan = FanNode(name="Supply Fan")

        self.graph.add_node(self.source)
        self.graph.add_node(self.coil)
        self.graph.add_node(self.fan)

        # Connect: Source -> Coil
        conn1 = Connector(
            source_node_id=self.source.id,
            source_port_name="outlet",
            target_node_id=self.coil.id,
            target_port_name="inlet"
        )
        self.graph.add_connector(conn1)

        # Connect: Coil -> Fan
        conn2 = Connector(
            source_node_id=self.coil.id,
            source_port_name="outlet",
            target_node_id=self.fan.id,
            target_port_name="inlet"
        )
        self.graph.add_connector(conn2)

    def test_get_source_nodes(self):
        """Test identifying source nodes (no connected inlets)."""
        sources = self.graph.get_source_nodes()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].id, self.source.id)

    def test_get_connector_to(self):
        """Test finding connector feeding a specific port."""
        conn = self.graph.get_connector_to(self.coil.id, "inlet")
        self.assertIsNotNone(conn)
        self.assertEqual(conn.source_node_id, self.source.id)

        # Check fan inlet
        conn2 = self.graph.get_connector_to(self.fan.id, "inlet")
        self.assertIsNotNone(conn2)
        self.assertEqual(conn2.source_node_id, self.coil.id)

    def test_get_connectors_from(self):
        """Test finding all connectors leaving a node."""
        conns = self.graph.get_connectors_from(self.coil.id)
        self.assertEqual(len(conns), 1)
        self.assertEqual(conns[0].target_node_id, self.fan.id)

    def test_get_upstream(self):
        """Test finding upstream node and port."""
        upstream = self.graph.get_upstream(self.coil.id, "inlet")
        self.assertIsNotNone(upstream)
        self.assertEqual(upstream[0].id, self.source.id)
        self.assertEqual(upstream[1], "outlet")


class TestFlowGraphTopologicalSort(unittest.TestCase):
    """Test topological ordering of the graph."""

    def setUp(self):
        """Create a simple flow: Source -> Coil -> Fan."""
        self.graph = FlowGraph()
        self.source = SourceNode(name="OA Intake")
        self.coil = CoolingCoilNode(name="Cooling Coil")
        self.fan = FanNode(name="Supply Fan")

        self.graph.add_node(self.source)
        self.graph.add_node(self.coil)
        self.graph.add_node(self.fan)

        # Connect: Source -> Coil
        conn1 = Connector(
            source_node_id=self.source.id,
            source_port_name="outlet",
            target_node_id=self.coil.id,
            target_port_name="inlet"
        )
        self.graph.add_connector(conn1)

        # Connect: Coil -> Fan
        conn2 = Connector(
            source_node_id=self.coil.id,
            source_port_name="outlet",
            target_node_id=self.fan.id,
            target_port_name="inlet"
        )
        self.graph.add_connector(conn2)

    def test_topological_order(self):
        """Test that nodes are ordered correctly."""
        order = self.graph.topological_order()
        self.assertEqual(len(order), 3)

        # Source should be first, fan should be last
        ids = [n.id for n in order]
        self.assertEqual(ids[0], self.source.id)
        self.assertEqual(ids[2], self.fan.id)

    def test_topological_order_cycle_detection(self):
        """Test that cycles are detected and rejected."""
        # Create a cycle: Fan -> Source
        cycle_conn = Connector(
            source_node_id=self.fan.id,
            source_port_name="outlet",
            target_node_id=self.source.id,
            target_port_name="inlet"
        )
        self.graph.add_connector(cycle_conn)

        with self.assertRaises(ValueError) as context:
            self.graph.topological_order()
        self.assertIn("cycle", str(context.exception).lower())


class TestFlowGraphValidation(unittest.TestCase):
    """Test graph validation."""

    def setUp(self):
        self.graph = FlowGraph()

    def test_validate_empty_graph(self):
        """Test validation of empty graph."""
        errors = self.graph.validate()
        self.assertEqual(len(errors), 1)
        self.assertIn("empty", errors[0].lower())

    def test_validate_unconnected_inlet(self):
        """Test detection of unconnected required inlet."""
        coil = CoolingCoilNode(name="Coil")
        self.graph.add_node(coil)

        errors = self.graph.validate()
        self.assertTrue(any("inlet" in e.lower() for e in errors))
        self.assertTrue(any("not connected" in e.lower() for e in errors))

    def test_validate_unconnected_outlet(self):
        """Test warning for unconnected outlet on non-sink nodes."""
        source = SourceNode(name="Source")
        self.graph.add_node(source)

        errors = self.graph.validate()
        # Source has outlet but it's not connected
        self.assertTrue(any("outlet" in e.lower() for e in errors))


class TestFlowGraphComplexTopologies(unittest.TestCase):
    """Test more complex HVAC system topologies."""

    def test_mixing_box_topology(self):
        """Test a system with a mixing box (two inlets, one outlet)."""
        graph = FlowGraph()

        oa_source = SourceNode(name="Outdoor Air")
        ra_source = SourceNode(name="Return Air")
        mixer = MixingBoxNode(name="Mixing Box")
        coil = CoolingCoilNode(name="Cooling Coil")

        graph.add_node(oa_source)
        graph.add_node(ra_source)
        graph.add_node(mixer)
        graph.add_node(coil)

        # Connect OA -> Mixer primary
        conn1 = Connector(
            source_node_id=oa_source.id,
            source_port_name="outlet",
            target_node_id=mixer.id,
            target_port_name="primary"
        )
        graph.add_connector(conn1)

        # Connect RA -> Mixer secondary
        conn2 = Connector(
            source_node_id=ra_source.id,
            source_port_name="outlet",
            target_node_id=mixer.id,
            target_port_name="secondary"
        )
        graph.add_connector(conn2)

        # Connect Mixer -> Coil
        conn3 = Connector(
            source_node_id=mixer.id,
            source_port_name="mixed",
            target_node_id=coil.id,
            target_port_name="inlet"
        )
        graph.add_connector(conn3)

        # Should have 2 sources
        sources = graph.get_source_nodes()
        self.assertEqual(len(sources), 2)

        # Topological order should work
        order = graph.topological_order()
        self.assertEqual(len(order), 4)

    def test_parallel_paths(self):
        """Test a system with parallel flow paths."""
        graph = FlowGraph()

        source = SourceNode(name="Source")
        coil1 = CoolingCoilNode(name="Coil 1")
        coil2 = CoolingCoilNode(name="Coil 2")
        fan = FanNode(name="Fan")

        graph.add_node(source)
        graph.add_node(coil1)
        graph.add_node(coil2)
        graph.add_node(fan)

        # Source splits to both coils
        conn1 = Connector(
            source_node_id=source.id,
            source_port_name="outlet",
            target_node_id=coil1.id,
            target_port_name="inlet"
        )
        conn2 = Connector(
            source_node_id=source.id,
            source_port_name="outlet",
            target_node_id=coil2.id,
            target_port_name="inlet"
        )
        graph.add_connector(conn1)
        graph.add_connector(conn2)

        # Both coils go to fan (would need a mixing node in reality,
        # but this tests parallel path detection)
        conn3 = Connector(
            source_node_id=coil1.id,
            source_port_name="outlet",
            target_node_id=fan.id,
            target_port_name="inlet"
        )
        graph.add_connector(conn3)

        # This creates a complex topology - source should still be identified
        sources = graph.get_source_nodes()
        self.assertEqual(len(sources), 1)


if __name__ == "__main__":
    unittest.main()
