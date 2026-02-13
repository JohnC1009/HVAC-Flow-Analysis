"""Tests for ControlLoop serialization and solver integration (bypass control)."""

import pytest

from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.models.connector import Connector
from hvac_flow.models.source_node import SourceNode
from hvac_flow.models.air_sink import AirSinkNode
from hvac_flow.models.enthalpy_wheel import EnthalpyWheelNode
from hvac_flow.solver.control_loop import ControlLoop
from hvac_flow.solver.flow_solver import FlowSolver

calc = PsychroCalc()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _connect(graph, src_node, src_port, tgt_node, tgt_port):
    """Create and register a Connector between two nodes already in the graph."""
    c = Connector(
        source_node_id=src_node.id,
        source_port_name=src_port,
        target_node_id=tgt_node.id,
        target_port_name=tgt_port,
    )
    graph.add_connector(c)
    return c


# ── Tests ────────────────────────────────────────────────────────────────────


def test_control_loop_serialization():
    """Round-trip to_dict / from_dict must preserve every serialized field."""
    loop = ControlLoop(
        name="test",
        enabled=True,
        sensor_node_id="node-abc",
        sensor_port_name="supply_out",
        sensor_property="dry_bulb",
        setpoint=55.0,
        actuator_node_id="node-xyz",
        actuator_parameter="bypass_fraction",
        actuator_min=0.0,
        actuator_max=1.0,
        tolerance=0.5,
        max_iterations=25,
    )

    data = loop.to_dict()
    restored = ControlLoop.from_dict(data)

    assert restored.name == loop.name
    assert restored.enabled == loop.enabled
    assert restored.sensor_node_id == loop.sensor_node_id
    assert restored.sensor_port_name == loop.sensor_port_name
    assert restored.sensor_property == loop.sensor_property
    assert restored.setpoint == pytest.approx(loop.setpoint)
    assert restored.actuator_node_id == loop.actuator_node_id
    assert restored.actuator_parameter == loop.actuator_parameter
    assert restored.actuator_min == pytest.approx(loop.actuator_min)
    assert restored.actuator_max == pytest.approx(loop.actuator_max)
    assert restored.tolerance == pytest.approx(loop.tolerance)
    assert restored.max_iterations == loop.max_iterations


def test_bypass_control_converges():
    """An enthalpy wheel with a bypass-fraction control loop should converge
    to a target supply_out dry-bulb of 82 F.

    Layout:
        OA source (95 F, 0.40 RH, 10000 CFM) -> wheel supply_in
        Exhaust source (75 F, 0.50 RH, 10000 CFM) -> wheel exhaust_in
        wheel supply_out -> supply sink
        wheel exhaust_out -> exhaust sink

    Control loop modulates wheel.bypass_fraction so that
    wheel.supply_out DB hits 82 F +/- 0.5 F.
    """
    graph = FlowGraph()

    oa_source = SourceNode(name="OA Source")
    oa_source.parameters["dry_bulb"] = 95.0
    oa_source.parameters["relative_humidity"] = 0.40
    oa_source.parameters["airflow_cfm"] = 10000.0

    exh_source = SourceNode(name="Exhaust Source")
    exh_source.parameters["dry_bulb"] = 75.0
    exh_source.parameters["relative_humidity"] = 0.50
    exh_source.parameters["airflow_cfm"] = 10000.0

    wheel = EnthalpyWheelNode(name="ERV Wheel")
    supply_sink = AirSinkNode(name="Supply Sink")
    exhaust_sink = AirSinkNode(name="Exhaust Sink")

    for node in [oa_source, exh_source, wheel, supply_sink, exhaust_sink]:
        graph.add_node(node)

    _connect(graph, oa_source, "outlet", wheel, "supply_in")
    _connect(graph, exh_source, "outlet", wheel, "exhaust_in")
    _connect(graph, wheel, "supply_out", supply_sink, "inlet")
    _connect(graph, wheel, "exhaust_out", exhaust_sink, "inlet")

    # Set up the control loop
    cl = ControlLoop(
        name="Bypass DB Control",
        enabled=True,
        sensor_node_id=wheel.id,
        sensor_port_name="supply_out",
        sensor_property="dry_bulb",
        setpoint=82.0,
        actuator_node_id=wheel.id,
        actuator_parameter="bypass_fraction",
        actuator_min=0.0,
        actuator_max=1.0,
        tolerance=0.5,
        max_iterations=30,
    )

    solver = FlowSolver(graph, calc)
    solver.control_loops.append(cl)

    ok = solver.solve()
    assert ok is True, f"Solver returned errors: {solver.errors}"

    # The control loop should have converged
    assert cl.converged is True, (
        f"Control loop did not converge after {cl.iterations_used} iterations "
        f"(final error={cl.final_error:.2f})"
    )

    # Verify the supply_out DB is within tolerance of the 82 F setpoint
    supply_out_state = wheel.ports["supply_out"].air_state
    assert supply_out_state is not None
    assert supply_out_state.dry_bulb == pytest.approx(82.0, abs=0.5), (
        f"Expected supply_out DB ~ 82.0 F, got {supply_out_state.dry_bulb:.2f} F"
    )
