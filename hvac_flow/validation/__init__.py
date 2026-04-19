"""System configuration validation for unusual HVAC designs.

This module provides validation logic to identify potential issues,
inefficiencies, or unusual configurations in HVAC air handling systems.
"""

from typing import List, Set, Dict, Any

from hvac_flow.models.base_node import BaseNode
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.desiccant_wheel import DesiccantWheelNode
from hvac_flow.models.enthalpy_wheel import EnthalpyWheelNode
from hvac_flow.models.fan import FanNode
from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.models.heating_coil import HeatingCoilNode
from hvac_flow.models.mixing_box import MixingBoxNode
from hvac_flow.models.runaround_loop import RunaroundLoopNode
from hvac_flow.models.sensible_heat_recovery import SensibleHeatRecoveryNode
from hvac_flow.models.source_node import SourceNode


class SystemValidator:
    """Validates HVAC system configurations for potential issues."""

    def __init__(self):
        self.warnings: List[str] = []

    def validate_configuration(self, graph: FlowGraph) -> List[str]:
        """Validate a complete system configuration.

        Returns a list of warning strings describing potential issues,
        inefficiencies, or unusual configurations.
        """
        self.warnings.clear()

        if not graph.nodes:
            return self.warnings

        # Run all validation checks
        self._check_energy_waste(graph)
        self._check_heat_recovery_usage(graph)
        self._check_outdoor_air_percentage(graph)
        self._check_multiple_mixing_boxes(graph)
        self._check_cold_climate_protection(graph)
        self._check_pressure_drops(graph)
        self._check_economizer_utilization(graph)
        self._check_unusual_sequences(graph)

        return self.warnings

    def _check_energy_waste(self, graph: FlowGraph) -> None:
        """Check for configurations that waste energy (e.g., cool then heat)."""
        # Get nodes in topological order
        try:
            order = graph.topological_order()
        except ValueError:
            return

        # Look for cooling followed by heating
        for i, node in enumerate(order):
            if isinstance(node, CoolingCoilNode):
                # Check if followed by heating
                for later_node in order[i+1:]:
                    if isinstance(later_node, HeatingCoilNode):
                        self.warnings.append(
                            f"[{node.name}] -> [{later_node.name}]: "
                            "Cooling followed by heating may waste energy. "
                            "Consider adjusting setpoints or using economizer."
                        )
                        break

    def _check_heat_recovery_usage(self, graph: FlowGraph) -> None:
        """Check for appropriate use of heat recovery."""
        has_heat_recovery = any(
            isinstance(n, (SensibleHeatRecoveryNode, EnthalpyWheelNode,
                          RunaroundLoopNode))
            for n in graph.nodes.values()
        )

        has_cooling = any(
            isinstance(n, CoolingCoilNode)
            for n in graph.nodes.values()
        )

        # Check outdoor air temperature
        oa_nodes = [n for n in graph.nodes.values()
                    if isinstance(n, SourceNode) and
                    n.parameters.get("dry_bulb", 75) > 85]

        if has_heat_recovery and has_cooling and oa_nodes:
            self.warnings.append(
                "Heat recovery with cooling detected. Ensure heat recovery "
                "is bypassed during cooling mode to avoid overheating."
            )

    def _check_outdoor_air_percentage(self, graph: FlowGraph) -> None:
        """Check for 100% outdoor air systems without heat recovery."""
        has_mixing = any(
            isinstance(n, MixingBoxNode)
            for n in graph.nodes.values()
        )

        has_heat_recovery = any(
            isinstance(n, (SensibleHeatRecoveryNode, EnthalpyWheelNode,
                          RunaroundLoopNode))
            for n in graph.nodes.values()
        )

        # Check for high OA flow
        oa_nodes = [n for n in graph.nodes.values() if isinstance(n, SourceNode)]
        total_oa_flow = sum(n.parameters.get("mass_flow", 0) for n in oa_nodes)

        if total_oa_flow > 2000 and not has_mixing and not has_heat_recovery:
            self.warnings.append(
                f"100% outdoor air system detected with {total_oa_flow:.0f} CFM "
                "and no heat recovery. Consider adding heat recovery to reduce "
                "energy consumption."
            )

    def _check_multiple_mixing_boxes(self, graph: FlowGraph) -> None:
        """Check for unusual configuration with multiple mixing boxes."""
        mixing_boxes = [
            n for n in graph.nodes.values()
            if isinstance(n, MixingBoxNode)
        ]

        if len(mixing_boxes) > 1:
            self.warnings.append(
                f"Multiple mixing boxes detected ({len(mixing_boxes)}). "
                "This is an unusual configuration. Ensure design intent is "
                "correct and all mixing boxes have proper return air connections."
            )

    def _check_cold_climate_protection(self, graph: FlowGraph) -> None:
        """Check for freeze protection in cold climates."""
        # Find outdoor air sources
        oa_nodes = [n for n in graph.nodes.values()
                    if isinstance(n, SourceNode)]

        # Check for very cold OA
        cold_oa = [n for n in oa_nodes
                   if n.parameters.get("dry_bulb", 75) < 35]

        if cold_oa:
            # Check for preheat
            has_preheat = any(
                isinstance(n, HeatingCoilNode)
                for n in graph.nodes.values()
            )

            # Check mixing box
            mixing_boxes = [n for n in graph.nodes.values()
                           if isinstance(n, MixingBoxNode)]

            if not has_preheat and not mixing_boxes:
                self.warnings.append(
                    f"Outdoor air at {cold_oa[0].parameters.get('dry_bulb')}°F "
                    "without preheat or mixing box. Risk of freeze-up. "
                    "Consider adding preheat coil or ensuring minimum OA damper "
                    "has freeze protection."
                )

    def _check_pressure_drops(self, graph: FlowGraph) -> None:
        """Check for excessive pressure drops from multiple components."""
        coil_count = sum(
            1 for n in graph.nodes.values()
            if isinstance(n, (CoolingCoilNode, HeatingCoilNode))
        )

        if coil_count > 2:
            self.warnings.append(
                f"Multiple heat exchangers in series ({coil_count} coils). "
                "This creates high pressure drop. Consider combining loads or "
                "using separate air handlers."
            )

    def _check_economizer_utilization(self, graph: FlowGraph) -> None:
        """Check if economizer is being used effectively."""
        mixing_boxes = [n for n in graph.nodes.values()
                       if isinstance(n, MixingBoxNode)]

        for mixer in mixing_boxes:
            mode = mixer.parameters.get("economizer_mode", "fixed")

            # Check OA conditions
            oa_connected = False
            for conn in graph.connectors.values():
                if conn.target_node_id == mixer.id and conn.target_port_name == "primary":
                    oa_connected = True
                    # Find the source
                    source = graph.nodes.get(conn.source_node_id)
                    if isinstance(source, SourceNode):
                        oa_temp = source.parameters.get("dry_bulb", 75)
                        ra_temp = 75  # Assume typical return

                        # If OA is cooler than RA but not using economizer
                        if oa_temp < ra_temp - 5 and mode == "fixed":
                            self.warnings.append(
                                f"[{mixer.name}] Outdoor air ({oa_temp}°F) is "
                                f"cooler than return air (~{ra_temp}°F) but "
                                "economizer is in fixed mode. Consider using "
                                "temperature or enthalpy economizer control."
                            )

    def _check_unusual_sequences(self, graph: FlowGraph) -> None:
        """Check for other unusual equipment sequences."""
        # Check for desiccant wheel without proper regeneration
        desiccant_wheels = [n for n in graph.nodes.values()
                           if isinstance(n, DesiccantWheelNode)]

        if desiccant_wheels:
            # Desiccant wheels need regeneration - check if system has heating
            has_regeneration_heat = any(
                isinstance(n, HeatingCoilNode)
                for n in graph.nodes.values()
            )

            if not has_regeneration_heat:
                self.warnings.append(
                    f"[{desiccant_wheels[0].name}] Desiccant wheel detected "
                    "without obvious regeneration heat source. Ensure "
                    "regeneration air stream is properly heated."
                )

    def get_recommendations(self, graph: FlowGraph) -> List[Dict[str, Any]]:
        """Get detailed recommendations for improving the system.

        Returns a list of dictionaries with keys:
        - type: 'warning', 'suggestion', 'info'
        - message: Human-readable description
        - affected_nodes: List of node IDs involved
        - potential_savings: Estimated energy savings if applicable
        """
        recommendations = []

        for warning in self.warnings:
            recommendations.append({
                "type": "warning",
                "message": warning,
                "affected_nodes": [],
                "potential_savings": None
            })

        return recommendations
