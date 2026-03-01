"""JSON-based save/load for HVAC Flow Analysis projects."""

import json

from hvac_flow.engine.constants import UnitSystem
from hvac_flow.models.project import Project
from hvac_flow.models.connector import Connector
from hvac_flow.models import NodeFactory


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

        node_type_map = NodeFactory.get_types()
        for nd in data.get("nodes", []):
            cls = node_type_map.get(nd["type"])
            if cls is None:
                continue
            node = cls.from_dict(nd)
            project.graph.add_node(node)

        for cd in data.get("connectors", []):
            connector = Connector.from_dict(cd)
            project.graph.add_connector(connector)

        return project
