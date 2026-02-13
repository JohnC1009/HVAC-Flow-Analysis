"""Tests for ProjectIO save/load round-trip and backward compatibility."""

import json

import pytest

from hvac_flow.models.project import Project
from hvac_flow.models.source_node import SourceNode
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.connector import Connector
from hvac_flow.solver.control_loop import ControlLoop
from hvac_flow.serialization.project_io import ProjectIO


# ── Tests ────────────────────────────────────────────────────────────────────


def test_save_load_roundtrip(tmp_path):
    """Save a project with a source, cooling coil, and connector, then reload.

    The loaded project must preserve the project name, node count,
    connector count, and individual node parameters.
    """
    project = Project()
    project.name = "Roundtrip Test"

    source = SourceNode(name="OA")
    source.parameters["dry_bulb"] = 100.0
    source.parameters["relative_humidity"] = 0.35
    source.parameters["airflow_cfm"] = 5000.0

    coil = CoolingCoilNode(name="CC-1")
    coil.parameters["leaving_db"] = 52.0
    coil.parameters["leaving_rh"] = 0.92

    project.graph.add_node(source)
    project.graph.add_node(coil)

    connector = Connector(
        source_node_id=source.id,
        source_port_name="outlet",
        target_node_id=coil.id,
        target_port_name="inlet",
    )
    project.graph.add_connector(connector)

    filepath = str(tmp_path / "test_project.json")
    ProjectIO.save(project, filepath)
    loaded = ProjectIO.load(filepath)

    assert loaded.name == "Roundtrip Test"
    assert len(loaded.graph.nodes) == 2
    assert len(loaded.graph.connectors) == 1

    # Verify the source node parameters survived the round-trip
    loaded_source = loaded.graph.nodes[source.id]
    assert loaded_source.parameters["dry_bulb"] == pytest.approx(100.0)
    assert loaded_source.parameters["relative_humidity"] == pytest.approx(0.35)
    assert loaded_source.parameters["airflow_cfm"] == pytest.approx(5000.0)

    # Verify the coil parameters survived as well
    loaded_coil = loaded.graph.nodes[coil.id]
    assert loaded_coil.parameters["leaving_db"] == pytest.approx(52.0)
    assert loaded_coil.parameters["leaving_rh"] == pytest.approx(0.92)


def test_save_load_with_control_loops(tmp_path):
    """A project with a ControlLoop should persist and restore it correctly."""
    project = Project()
    project.name = "Control Loop Project"

    source = SourceNode(name="OA")
    coil = CoolingCoilNode(name="CC-1")

    project.graph.add_node(source)
    project.graph.add_node(coil)

    connector = Connector(
        source_node_id=source.id,
        source_port_name="outlet",
        target_node_id=coil.id,
        target_port_name="inlet",
    )
    project.graph.add_connector(connector)

    cl = ControlLoop(
        name="DAT Control",
        enabled=True,
        sensor_node_id=coil.id,
        sensor_port_name="outlet",
        sensor_property="dry_bulb",
        setpoint=55.0,
        actuator_node_id=coil.id,
        actuator_parameter="leaving_db",
        actuator_min=45.0,
        actuator_max=65.0,
        tolerance=0.3,
        max_iterations=25,
    )
    project.control_loops.append(cl)

    filepath = str(tmp_path / "project_with_loops.json")
    ProjectIO.save(project, filepath)
    loaded = ProjectIO.load(filepath)

    assert len(loaded.control_loops) == 1

    loaded_cl = loaded.control_loops[0]
    assert loaded_cl.name == "DAT Control"
    assert loaded_cl.enabled is True
    assert loaded_cl.sensor_node_id == coil.id
    assert loaded_cl.sensor_port_name == "outlet"
    assert loaded_cl.sensor_property == "dry_bulb"
    assert loaded_cl.setpoint == pytest.approx(55.0)
    assert loaded_cl.actuator_node_id == coil.id
    assert loaded_cl.actuator_parameter == "leaving_db"
    assert loaded_cl.actuator_min == pytest.approx(45.0)
    assert loaded_cl.actuator_max == pytest.approx(65.0)
    assert loaded_cl.tolerance == pytest.approx(0.3)
    assert loaded_cl.max_iterations == 25


def test_load_v1_without_control_loops(tmp_path):
    """A v1.0 project file that has no 'control_loops' key should load
    successfully with an empty control_loops list.
    """
    # Manually build a minimal v1.0-style JSON (no control_loops key)
    source = SourceNode(name="OA")
    coil = CoolingCoilNode(name="CC-1")

    connector = Connector(
        source_node_id=source.id,
        source_port_name="outlet",
        target_node_id=coil.id,
        target_port_name="inlet",
    )

    v1_data = {
        "version": "1.0",
        "name": "Legacy Project",
        "unit_system": "IP",
        "pressure": 14.696,
        "altitude_ft": 0.0,
        "nodes": [source.to_dict(), coil.to_dict()],
        "connectors": [connector.to_dict()],
        # Intentionally no "control_loops" key — simulating v1.0 format
    }

    filepath = str(tmp_path / "v1_project.json")
    with open(filepath, "w") as f:
        json.dump(v1_data, f, indent=2)

    loaded = ProjectIO.load(filepath)

    assert loaded.name == "Legacy Project"
    assert len(loaded.graph.nodes) == 2
    assert len(loaded.graph.connectors) == 1
    assert loaded.control_loops == []
