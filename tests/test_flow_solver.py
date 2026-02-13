"""Tests for the FlowSolver — DAG traversal, cycle-breaking, and error handling."""

import pytest

from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.models.connector import Connector
from hvac_flow.models.source_node import SourceNode
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.air_sink import AirSinkNode
from hvac_flow.models.enthalpy_wheel import EnthalpyWheelNode
from hvac_flow.models.zone_process import ZoneProcessNode
from hvac_flow.solver.flow_solver import FlowSolver

calc = PsychroCalc()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_source(dry_bulb=95.0, rh=0.40, cfm=10000.0, name="OA Source"):
    """Create a SourceNode with the given conditions."""
    src = SourceNode(name=name)
    src.parameters["dry_bulb"] = dry_bulb
    src.parameters["relative_humidity"] = rh
    src.parameters["airflow_cfm"] = cfm
    return src


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


def test_simple_pipeline():
    """Source -> CoolingCoil -> AirSink should solve in a single pass."""
    graph = FlowGraph()

    source = _make_source(95.0, 0.40, 10000.0)
    coil = CoolingCoilNode(name="CC-1")
    sink = AirSinkNode(name="Exhaust")

    graph.add_node(source)
    graph.add_node(coil)
    graph.add_node(sink)

    _connect(graph, source, "outlet", coil, "inlet")
    _connect(graph, coil, "outlet", sink, "inlet")

    solver = FlowSolver(graph, calc)
    ok = solver.solve()

    assert ok is True, f"Solver returned errors: {solver.errors}"
    assert solver.errors == []
    assert len(solver.all_states) > 0


def test_cycle_breaking_erv():
    """Source -> EnthalpyWheel -> CoolingCoil -> Zone -> (return feeds wheel exhaust) -> AirSink.

    The zone return_air port feeds back into the wheel's exhaust_in port,
    creating a cycle.  The solver should break it automatically, and the
    wheel should pre-cool the outdoor air so supply_out DB < 95.
    """
    graph = FlowGraph()

    source = _make_source(95.0, 0.40, 10000.0, name="OA")
    wheel = EnthalpyWheelNode(name="ERV Wheel")
    coil = CoolingCoilNode(name="CC-1")
    zone = ZoneProcessNode(name="Zone")
    sink = AirSinkNode(name="Exhaust")

    graph.add_node(source)
    graph.add_node(wheel)
    graph.add_node(coil)
    graph.add_node(zone)
    graph.add_node(sink)

    # Forward path: source -> wheel supply_in -> supply_out -> coil -> zone
    _connect(graph, source, "outlet", wheel, "supply_in")
    _connect(graph, wheel, "supply_out", coil, "inlet")
    _connect(graph, coil, "outlet", zone, "supply_air")

    # Feedback: zone return_air -> wheel exhaust_in  (creates the cycle)
    _connect(graph, zone, "return_air", wheel, "exhaust_in")

    # Exhaust outlet goes to sink
    _connect(graph, wheel, "exhaust_out", sink, "inlet")

    solver = FlowSolver(graph, calc)
    ok = solver.solve()

    assert ok is True, f"Solver returned errors: {solver.errors}"

    # The wheel should pre-cool OA: supply_out DB must be below outdoor 95 F
    supply_out_state = wheel.ports["supply_out"].air_state
    assert supply_out_state is not None
    assert supply_out_state.dry_bulb < 95.0, (
        f"Expected wheel supply_out DB < 95, got {supply_out_state.dry_bulb:.1f}"
    )

    # Zone return_air state should exist (it feeds the exhaust side)
    return_state = zone.ports["return_air"].air_state
    assert return_state is not None


def test_solver_error_missing_connection():
    """A source and a cooling coil with NO connector should fail validation."""
    graph = FlowGraph()

    source = _make_source()
    coil = CoolingCoilNode(name="CC-1")

    graph.add_node(source)
    graph.add_node(coil)

    # Deliberately do NOT connect them.

    solver = FlowSolver(graph, calc)
    ok = solver.solve()

    assert ok is False
    assert len(solver.errors) > 0


def test_no_cycle_fast_path():
    """Source -> CoolingCoil -> AirSink with no cycles and no control loops
    should succeed via the single-pass DAG fast path.
    """
    graph = FlowGraph()

    source = _make_source(95.0, 0.40, 10000.0)
    coil = CoolingCoilNode(name="CC-1")
    sink = AirSinkNode(name="Discharge")

    graph.add_node(source)
    graph.add_node(coil)
    graph.add_node(sink)

    _connect(graph, source, "outlet", coil, "inlet")
    _connect(graph, coil, "outlet", sink, "inlet")

    solver = FlowSolver(graph, calc)
    # Ensure no control loops are attached
    assert solver.control_loops == []

    ok = solver.solve()

    assert ok is True, f"Solver returned errors: {solver.errors}"
    assert solver.errors == []
    assert len(solver.all_states) > 0

    # Verify the coil actually cooled the air
    coil_out = coil.ports["outlet"].air_state
    assert coil_out is not None
    assert coil_out.dry_bulb < 95.0
