"""Directed graph of equipment nodes connected by ductwork connectors."""

from collections import deque
from typing import Dict, List, Optional, Tuple

from hvac_flow.models.base_node import BaseNode
from hvac_flow.models.connector import Connector


class FlowGraph:
    """Directed acyclic graph of BaseNode objects linked by Connectors."""

    def __init__(self):
        self.nodes: Dict[str, BaseNode] = {}
        self.connectors: Dict[str, Connector] = {}

    # ── Mutation ─────────────────────────────────────────────────────

    def add_node(self, node: BaseNode) -> None:
        self.nodes[node.id] = node

    def remove_node(self, node_id: str) -> None:
        # Remove all connectors touching this node
        to_remove = [
            c.id for c in self.connectors.values()
            if c.source_node_id == node_id or c.target_node_id == node_id
        ]
        for cid in to_remove:
            self.remove_connector(cid)
        del self.nodes[node_id]

    def add_connector(self, connector: Connector) -> None:
        self.connectors[connector.id] = connector
        # Update port references
        src = self.nodes[connector.source_node_id]
        tgt = self.nodes[connector.target_node_id]
        src.ports[connector.source_port_name].connected_to = connector.id
        tgt.ports[connector.target_port_name].connected_to = connector.id

    def remove_connector(self, connector_id: str) -> None:
        c = self.connectors.pop(connector_id, None)
        if c is None:
            return
        src = self.nodes.get(c.source_node_id)
        tgt = self.nodes.get(c.target_node_id)
        if src and c.source_port_name in src.ports:
            src.ports[c.source_port_name].connected_to = None
        if tgt and c.target_port_name in tgt.ports:
            tgt.ports[c.target_port_name].connected_to = None

    # ── Queries ──────────────────────────────────────────────────────

    def get_source_nodes(self) -> List[BaseNode]:
        """Nodes with no connected inlet ports (graph roots)."""
        result = []
        for node in self.nodes.values():
            has_connected_inlet = any(
                p.connected_to is not None for p in node.inlet_ports
            )
            if not has_connected_inlet:
                result.append(node)
        return result

    def get_connector_to(self, node_id: str,
                         port_name: str) -> Optional[Connector]:
        """Find the connector feeding a specific inlet port."""
        for c in self.connectors.values():
            if c.target_node_id == node_id and c.target_port_name == port_name:
                return c
        return None

    def get_connectors_from(self, node_id: str) -> List[Connector]:
        """Find all connectors leaving a node."""
        return [c for c in self.connectors.values()
                if c.source_node_id == node_id]

    def get_upstream(self, node_id: str,
                     port_name: str) -> Optional[Tuple[BaseNode, str]]:
        """Return (upstream_node, outlet_port_name) for a given inlet port."""
        c = self.get_connector_to(node_id, port_name)
        if c is None:
            return None
        return self.nodes.get(c.source_node_id), c.source_port_name

    # ── Topological sort (Kahn's algorithm) ──────────────────────────

    def topological_order(self) -> List[BaseNode]:
        """Return nodes in dependency order (upstream before downstream).

        If the graph contains a cycle the returned list will be shorter
        than ``len(self.nodes)`` (only the acyclic portion is included).
        Callers that need to detect this can compare lengths.
        """
        # Build in-degree map based on connected inlet ports
        in_degree: Dict[str, int] = {nid: 0 for nid in self.nodes}
        for c in self.connectors.values():
            in_degree[c.target_node_id] += 1

        queue = deque(
            nid for nid, deg in in_degree.items() if deg == 0
        )
        order = []
        while queue:
            nid = queue.popleft()
            order.append(self.nodes[nid])
            for c in self.get_connectors_from(nid):
                in_degree[c.target_node_id] -= 1
                if in_degree[c.target_node_id] == 0:
                    queue.append(c.target_node_id)

        return order

    # ── Validation ───────────────────────────────────────────────────

    def validate(self) -> List[str]:
        """Return a list of validation error strings (empty = valid).

        Each error message is prefixed with ``[NodeName]`` so the user
        can quickly identify *which* node has the problem.
        """
        errors = []
        if not self.nodes:
            errors.append("Graph is empty — add at least one node.")
            return errors

        for node in self.nodes.values():
            for port in node.inlet_ports:
                if port.connected_to is None:
                    # Only error if the node isn't a source type
                    if node.inlet_ports:
                        errors.append(
                            f"[{node.name}] Inlet port '{port.name}' "
                            f"is not connected."
                        )

            # Check for outlet ports that should be connected
            for port in node.outlet_ports:
                if port.connected_to is None:
                    # Not necessarily an error, but warn for non-sink nodes
                    from hvac_flow.models.air_sink import AirSinkNode
                    if not isinstance(node, AirSinkNode):
                        has_any_connected_outlet = any(
                            p.connected_to is not None
                            for p in node.outlet_ports
                        )
                        if not has_any_connected_outlet:
                            errors.append(
                                f"[{node.name}] No outlet ports are "
                                f"connected — node output is unused."
                            )
                            break  # Only report once per node

        # Note: cycle detection is NOT performed here.  The FlowSolver
        # handles cycles via tear-edge iteration, so a cyclic graph is
        # valid as long as the cycle passes through an iterable inlet.
        return errors
