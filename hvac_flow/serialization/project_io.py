"""JSON-based save/load for HVAC Flow Analysis projects."""

import json

from hvac_flow.engine.constants import UnitSystem
from hvac_flow.models.project import Project
from hvac_flow.models.connector import Connector
from hvac_flow.models.source_node import SourceNode
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.heating_coil import HeatingCoilNode
from hvac_flow.models.fan import FanNode
from hvac_flow.models.enthalpy_wheel import EnthalpyWheelNode
from hvac_flow.models.mixing_box import MixingBoxNode


NODE_TYPE_MAP = {
    "source": SourceNode,
    "cooling_coil": CoolingCoilNode,
    "heating_coil": HeatingCoilNode,
    "fan": FanNode,
    "enthalpy_wheel": EnthalpyWheelNode,
    "mixing_box": MixingBoxNode,
}


class ProjectIO:
    """Serialize / deserialize a Project to/from JSON."""

    @staticmethod
    def save(project: Project, filepath: str) -> None:
        data = {
            "version": "1.0",
            "name": project.name,
            "unit_system": project.unit_system.value,
            "pressure": project.pressure,
            "altitude_ft": project.altitude_ft,
            "nodes": [n.to_dict() for n in project.graph.nodes.values()],
            "connectors": [c.to_dict() for c in project.graph.connectors.values()],
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load(filepath: str) -> Project:
        with open(filepath, "r") as f:
            data = json.load(f)

        project = Project()
        project.name = data.get("name", "Untitled")
        project.unit_system = UnitSystem(data.get("unit_system", "IP"))
        project.pressure = data.get("pressure", 14.696)
        project.altitude_ft = data.get("altitude_ft", 0.0)

        for nd in data.get("nodes", []):
            cls = NODE_TYPE_MAP.get(nd["type"])
            if cls is None:
                continue
            node = cls.from_dict(nd)
            project.graph.add_node(node)

        for cd in data.get("connectors", []):
            connector = Connector.from_dict(cd)
            project.graph.add_connector(connector)

        return project
