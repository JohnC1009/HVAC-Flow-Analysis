"""Flow solver — propagates air states through the equipment graph."""

from typing import List

from hvac_flow.engine.air_state import AirState
from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.flow_graph import FlowGraph


class FlowSolver:
    """Traverses the flow graph in topological order, computing each node."""

    def __init__(self, graph: FlowGraph, calc: PsychroCalc):
        self.graph = graph
        self.calc = calc
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.all_states: List[AirState] = []

    def solve(self) -> bool:
        """Run a full solve pass.

        Returns True on success, False if errors occurred.
        After solving, self.all_states contains every resolved AirState
        (for plotting on the psychrometric chart).
        """
        self.errors.clear()
        self.warnings.clear()
        self.all_states.clear()

        # Validate
        validation = self.graph.validate()
        if validation:
            self.errors = validation
            return False

        # Topological traversal
        try:
            order = self.graph.topological_order()
        except ValueError as e:
            self.errors.append(str(e))
            return False

        for node in order:
            try:
                self._propagate_inlets(node)
                node.compute(self.calc)
                self._collect_states(node)
            except Exception as e:
                self.errors.append(f"Error computing '{node.name}': {e}")
                return False

        return True

    def _propagate_inlets(self, node):
        """Copy upstream outlet states through connectors into inlet ports."""
        for port in node.inlet_ports:
            connector = self.graph.get_connector_to(node.id, port.name)
            if connector is None:
                continue
            upstream_node = self.graph.nodes.get(connector.source_node_id)
            if upstream_node is None:
                continue
            upstream_port = upstream_node.ports.get(connector.source_port_name)
            if upstream_port is None or upstream_port.air_state is None:
                self.warnings.append(
                    f"Upstream port '{connector.source_port_name}' on "
                    f"'{upstream_node.name}' has no air state."
                )
                continue
            state = connector.apply_duct_loss(
                upstream_port.air_state, upstream_port.mass_flow, self.calc
            )
            port.air_state = state
            port.mass_flow = upstream_port.mass_flow

    def _collect_states(self, node):
        """Gather all resolved outlet air states for the psychrometric chart."""
        for port in node.outlet_ports:
            if port.air_state is not None:
                self.all_states.append(port.air_state)
