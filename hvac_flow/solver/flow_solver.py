"""Flow solver — propagates air states through the equipment graph."""

from typing import Dict, List, Optional

from hvac_flow.engine.air_state import AirState
from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.exceptions import CyclicGraphError, DisconnectedGraphError, SolverError
from hvac_flow.models.base_node import BaseNode
from hvac_flow.models.flow_graph import FlowGraph


class FlowSolver:
    """Traverses the flow graph in topological order, computing each node.

    After a successful ``solve()`` call:
    * ``self.all_states`` — every resolved outlet AirState (for the chart).
    * ``self.node_errors`` — per-node computation error messages.
    * ``self.node_warnings`` — per-node boundary-condition warnings.
    * ``self.errors`` / ``self.warnings`` — aggregate lists.
    """

    def __init__(self, graph: FlowGraph, calc: PsychroCalc) -> None:
        self.graph: FlowGraph = graph
        self.calc: PsychroCalc = calc
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.all_states: List[AirState] = []
        self.node_errors: Dict[str, List[str]] = {}   # node_id -> errors
        self.node_warnings: Dict[str, List[str]] = {}  # node_id -> warnings

    def solve(self) -> bool:
        """Run a full solve pass.

        Returns True on success, False if errors occurred.
        After solving, self.all_states contains every resolved AirState
        (for plotting on the psychrometric chart).

        Raises:
            CyclicGraphError: If the graph contains a cycle.
            DisconnectedGraphError: If required nodes are disconnected.
        """
        self.errors.clear()
        self.warnings.clear()
        self.all_states.clear()
        self.node_errors.clear()
        self.node_warnings.clear()

        # Clear previous capacity warnings on all nodes
        for node in self.graph.nodes.values():
            node.capacity_warnings.clear()

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
            raise CyclicGraphError(str(e)) from e

        for node in order:
            try:
                self._propagate_inlets(node)
                node.compute(self.calc)
                self._check_boundary_conditions(node)
                self._collect_states(node)
            except Exception as e:
                err_msg = str(e)
                # If the error message already includes the node name
                # (from our enhanced node-level checks), use it directly.
                if err_msg.startswith(f"[{node.name}]"):
                    self.errors.append(err_msg)
                else:
                    self.errors.append(
                        f"[{node.name}] Error: {err_msg}"
                    )
                self.node_errors.setdefault(node.id, []).append(err_msg)
                raise SolverError(err_msg, node_id=node.id, node_name=node.name) from e

        return True

    def _propagate_inlets(self, node: BaseNode) -> None:
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
                msg = (
                    f"[{node.name}] Upstream port "
                    f"'{connector.source_port_name}' on "
                    f"'{upstream_node.name}' has no air state."
                )
                self.warnings.append(msg)
                self.node_warnings.setdefault(node.id, []).append(msg)
                continue
            state = connector.apply_duct_loss(
                upstream_port.air_state, upstream_port.mass_flow, self.calc
            )
            port.air_state = state
            port.mass_flow = upstream_port.mass_flow

    def _check_boundary_conditions(self, node: BaseNode) -> None:
        """Run boundary-condition checks and collect any warnings."""
        bc_warnings = node.check_boundary_conditions()
        if bc_warnings:
            self.warnings.extend(bc_warnings)
            self.node_warnings.setdefault(node.id, []).extend(bc_warnings)

    def _collect_states(self, node: BaseNode) -> None:
        """Gather all resolved outlet air states for the psychrometric chart."""
        for port in node.outlet_ports:
            if port.air_state is not None:
                self.all_states.append(port.air_state)

    def get_state_by_label(self, label: str) -> Optional[AirState]:
        """Find an AirState by its label.
        
        Args:
            label: The label to search for.
            
        Returns:
            The matching AirState or None.
        """
        for state in self.all_states:
            if state.label == label:
                return state
        return None
