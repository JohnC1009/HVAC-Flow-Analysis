"""Tests for CFM tracking and pressure drop features across all device types."""

import pytest

from hvac_flow.engine.constants import FAN_CONSTANT_IP, CP_AIR_IP, HP_TO_BTUH
from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.models.source_node import SourceNode
from hvac_flow.models.fan import FanNode
from hvac_flow.models.return_fan import ReturnFanNode
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.heating_coil import HeatingCoilNode
from hvac_flow.models.zone_process import ZoneProcessNode
from hvac_flow.models.mixing_box import MixingBoxNode
from hvac_flow.models.duct_split import DuctSplitNode
from hvac_flow.models.enthalpy_wheel import EnthalpyWheelNode
from hvac_flow.models.sensible_heat_recovery import SensibleHeatRecoveryNode
from hvac_flow.models.desiccant_wheel import DesiccantWheelNode
from hvac_flow.models.indirect_evap_cooler import IndirectEvapCoolerNode
from hvac_flow.models.adiabatic_humidifier import AdiabaticHumidifierNode
from hvac_flow.models.steam_humidifier import SteamHumidifierNode
from hvac_flow.models.runaround_loop import RunaroundLoopNode
from hvac_flow.models.connector import Connector
from hvac_flow.models.air_sink import AirSinkNode
from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.solver.flow_solver import FlowSolver

calc = PsychroCalc()


# ── helpers ──────────────────────────────────────────────────────────

def _state_95_40():
    return calc.from_db_rh(95.0, 0.40, label="OA")

def _state_55_90():
    return calc.from_db_rh(55.0, 0.90, label="Supply")

def _state_75_50():
    return calc.from_db_rh(75.0, 0.50, label="Return")

def _make_source(db=95.0, rh=0.40, cfm=10000.0, name="OA"):
    src = SourceNode(name=name)
    src.parameters["dry_bulb"] = db
    src.parameters["relative_humidity"] = rh
    src.parameters["airflow_cfm"] = cfm
    return src

def _connect(graph, src_node, src_port, tgt_node, tgt_port):
    c = Connector(
        source_node_id=src_node.id,
        source_port_name=src_port,
        target_node_id=tgt_node.id,
        target_port_name=tgt_port,
    )
    graph.add_connector(c)
    return c


# ── Source node CFM ──────────────────────────────────────────────────

def test_source_reports_cfm():
    src = _make_source(cfm=10000.0)
    src.compute(calc)
    assert "cfm" in src.results
    assert src.results["cfm"] == 10000.0
    assert "density_lb_ft3" in src.results
    assert src.results["density_lb_ft3"] > 0


# ── Fan TSP mode ────────────────────────────────────────────────────

def test_fan_tsp_mode():
    """TSP mode should derive BHP from CFM and total static pressure."""
    fan = FanNode(name="SF-1")
    fan.parameters["input_mode"] = "tsp"
    fan.parameters["total_static_pressure_iw"] = 4.0
    fan.parameters["fan_efficiency"] = 0.65
    fan.parameters["motor_efficiency"] = 0.90

    state = _state_95_40()
    mass_flow = 750.0  # lb_da/min
    fan.ports["inlet"].air_state = state
    fan.ports["inlet"].mass_flow = mass_flow

    fan.compute(calc)

    cfm = mass_flow * state.specific_volume
    expected_bhp = cfm * 4.0 / (FAN_CONSTANT_IP * 0.65)

    assert "bhp" in fan.results
    assert fan.results["bhp"] == pytest.approx(expected_bhp, rel=0.01)
    assert fan.results["entering_cfm"] == pytest.approx(cfm, rel=0.01)
    assert fan.results["leaving_cfm"] > 0
    assert fan.results["total_static_pressure_iw"] == 4.0
    assert fan.ports["outlet"].air_state.dry_bulb > state.dry_bulb


def test_fan_bhp_mode_reports_cfm():
    """BHP mode should still report CFM."""
    fan = FanNode(name="SF-1")
    fan.parameters["input_mode"] = "bhp"
    fan.parameters["bhp"] = 15.0

    state = _state_95_40()
    fan.ports["inlet"].air_state = state
    fan.ports["inlet"].mass_flow = 750.0

    fan.compute(calc)

    assert "entering_cfm" in fan.results
    assert "leaving_cfm" in fan.results
    assert fan.results["entering_cfm"] > 0
    assert fan.results["leaving_cfm"] > fan.results["entering_cfm"]  # warmer air = more volume


def test_return_fan_tsp_mode():
    """Return fan TSP mode should work the same as supply fan."""
    fan = ReturnFanNode(name="RF-1")
    fan.parameters["input_mode"] = "tsp"
    fan.parameters["total_static_pressure_iw"] = 2.0
    fan.parameters["fan_efficiency"] = 0.65

    state = _state_75_50()
    fan.ports["inlet"].air_state = state
    fan.ports["inlet"].mass_flow = 750.0

    fan.compute(calc)

    assert "bhp" in fan.results
    assert fan.results["bhp"] > 0
    assert "entering_cfm" in fan.results


# ── Cooling coil CFM + pressure drop ────────────────────────────────

def test_cooling_coil_cfm_and_pressure():
    coil = CoolingCoilNode(name="CC-1")
    coil.parameters["pressure_drop_iw"] = 1.5

    state = _state_95_40()
    coil.ports["inlet"].air_state = state
    coil.ports["inlet"].mass_flow = 750.0

    coil.compute(calc)

    assert "entering_cfm" in coil.results
    assert "leaving_cfm" in coil.results
    assert coil.results["pressure_drop_iw"] == 1.5
    # Cooled air is denser, so leaving CFM < entering CFM
    assert coil.results["leaving_cfm"] < coil.results["entering_cfm"]


# ── Heating coil CFM + pressure drop ────────────────────────────────

def test_heating_coil_cfm_and_pressure():
    coil = HeatingCoilNode(name="HC-1")
    coil.parameters["pressure_drop_iw"] = 0.5

    state = _state_55_90()
    coil.ports["inlet"].air_state = state
    coil.ports["inlet"].mass_flow = 750.0

    coil.compute(calc)

    assert coil.results["pressure_drop_iw"] == 0.5
    assert coil.results["entering_cfm"] > 0
    # Heated air expands
    assert coil.results["leaving_cfm"] > coil.results["entering_cfm"]


# ── Zone process CFM ────────────────────────────────────────────────

def test_zone_process_cfm():
    zone = ZoneProcessNode(name="Zone")
    zone.parameters["sensible_load_btuh"] = 120000
    zone.parameters["latent_load_btuh"] = 30000
    zone.parameters["pressure_drop_iw"] = 0.25

    state = _state_55_90()
    zone.ports["supply_air"].air_state = state
    zone.ports["supply_air"].mass_flow = 750.0

    zone.compute(calc)

    assert "supply_cfm" in zone.results
    assert "return_cfm" in zone.results
    assert zone.results["pressure_drop_iw"] == 0.25
    # Return air is warmer, so more volume
    assert zone.results["return_cfm"] > zone.results["supply_cfm"]


# ── Mixing box CFM ──────────────────────────────────────────────────

def test_mixing_box_cfm():
    mb = MixingBoxNode(name="MB")
    mb.parameters["pressure_drop_iw"] = 0.75

    oa = _state_95_40()
    ra = _state_75_50()
    mb.ports["primary"].air_state = oa
    mb.ports["primary"].mass_flow = 200.0
    mb.ports["secondary"].air_state = ra
    mb.ports["secondary"].mass_flow = 550.0

    mb.compute(calc)

    assert "primary_cfm" in mb.results
    assert "secondary_cfm" in mb.results
    assert "mixed_cfm" in mb.results
    assert mb.results["pressure_drop_iw"] == 0.75


# ── Duct split CFM ──────────────────────────────────────────────────

def test_duct_split_cfm():
    ds = DuctSplitNode(name="Split")
    ds.parameters["split_fraction"] = 0.60
    ds.parameters["pressure_drop_iw"] = 0.1

    state = _state_55_90()
    ds.ports["inlet"].air_state = state
    ds.ports["inlet"].mass_flow = 750.0

    ds.compute(calc)

    assert "inlet_cfm" in ds.results
    assert "outlet_a_cfm" in ds.results
    assert "outlet_b_cfm" in ds.results
    total = ds.results["outlet_a_cfm"] + ds.results["outlet_b_cfm"]
    assert total == pytest.approx(ds.results["inlet_cfm"], rel=0.001)
    assert ds.results["pressure_drop_iw"] == 0.1


# ── Two-stream devices CFM + pressure drop ──────────────────────────

def test_enthalpy_wheel_cfm_and_pressure():
    wheel = EnthalpyWheelNode(name="ERV")
    wheel.parameters["supply_pressure_drop_iw"] = 1.0
    wheel.parameters["exhaust_pressure_drop_iw"] = 0.8

    s_in = _state_95_40()
    e_in = _state_75_50()
    wheel.ports["supply_in"].air_state = s_in
    wheel.ports["supply_in"].mass_flow = 750.0
    wheel.ports["exhaust_in"].air_state = e_in
    wheel.ports["exhaust_in"].mass_flow = 750.0

    wheel.compute(calc)

    assert wheel.results["supply_pressure_drop_iw"] == 1.0
    assert wheel.results["exhaust_pressure_drop_iw"] == 0.8
    assert wheel.results["supply_in_cfm"] > 0
    assert wheel.results["exhaust_in_cfm"] > 0


def test_sensible_hr_cfm_and_pressure():
    hr = SensibleHeatRecoveryNode(name="SHR")
    hr.parameters["supply_pressure_drop_iw"] = 0.6
    hr.parameters["exhaust_pressure_drop_iw"] = 0.5

    s_in = _state_95_40()
    e_in = _state_75_50()
    hr.ports["supply_in"].air_state = s_in
    hr.ports["supply_in"].mass_flow = 750.0
    hr.ports["exhaust_in"].air_state = e_in
    hr.ports["exhaust_in"].mass_flow = 750.0

    hr.compute(calc)

    assert hr.results["supply_pressure_drop_iw"] == 0.6
    assert hr.results["supply_in_cfm"] > 0


def test_desiccant_wheel_cfm_and_pressure():
    dw = DesiccantWheelNode(name="DW")
    dw.parameters["process_pressure_drop_iw"] = 1.2
    dw.parameters["regen_pressure_drop_iw"] = 0.9

    p_in = _state_95_40()
    r_in = calc.from_db_rh(200.0, 0.05, label="Regen")
    dw.ports["process_in"].air_state = p_in
    dw.ports["process_in"].mass_flow = 750.0
    dw.ports["regen_in"].air_state = r_in
    dw.ports["regen_in"].mass_flow = 250.0

    dw.compute(calc)

    assert dw.results["process_pressure_drop_iw"] == 1.2
    assert dw.results["regen_pressure_drop_iw"] == 0.9
    assert dw.results["process_in_cfm"] > 0


def test_indirect_evap_cooler_cfm_and_pressure():
    iec = IndirectEvapCoolerNode(name="IEC")
    iec.parameters["primary_pressure_drop_iw"] = 0.4
    iec.parameters["secondary_pressure_drop_iw"] = 0.3

    p_in = _state_95_40()
    s_in = _state_75_50()
    iec.ports["primary_in"].air_state = p_in
    iec.ports["primary_in"].mass_flow = 750.0
    iec.ports["secondary_in"].air_state = s_in
    iec.ports["secondary_in"].mass_flow = 750.0

    iec.compute(calc)

    assert iec.results["primary_pressure_drop_iw"] == 0.4
    assert iec.results["primary_in_cfm"] > 0


def test_runaround_loop_cfm_and_pressure():
    ral = RunaroundLoopNode(name="RAL")
    ral.parameters["supply_pressure_drop_iw"] = 0.7
    ral.parameters["exhaust_pressure_drop_iw"] = 0.6

    s_in = _state_95_40()
    e_in = _state_75_50()
    ral.ports["supply_in"].air_state = s_in
    ral.ports["supply_in"].mass_flow = 750.0
    ral.ports["exhaust_in"].air_state = e_in
    ral.ports["exhaust_in"].mass_flow = 750.0

    ral.compute(calc)

    assert ral.results["supply_pressure_drop_iw"] == 0.7
    assert ral.results["supply_in_cfm"] > 0


# ── Humidifier CFM + pressure drop ──────────────────────────────────

def test_adiabatic_humidifier_cfm_and_pressure():
    hum = AdiabaticHumidifierNode(name="EvapHum")
    hum.parameters["pressure_drop_iw"] = 0.3

    state = calc.from_db_rh(80.0, 0.30, label="Dry")
    hum.ports["inlet"].air_state = state
    hum.ports["inlet"].mass_flow = 750.0

    hum.compute(calc)

    assert hum.results["pressure_drop_iw"] == 0.3
    assert hum.results["entering_cfm"] > 0
    assert hum.results["leaving_cfm"] > 0


def test_steam_humidifier_cfm_and_pressure():
    sh = SteamHumidifierNode(name="SteamHum")
    sh.parameters["pressure_drop_iw"] = 0.15

    state = calc.from_db_rh(70.0, 0.20, label="Dry")
    sh.ports["inlet"].air_state = state
    sh.ports["inlet"].mass_flow = 750.0

    sh.compute(calc)

    assert sh.results["pressure_drop_iw"] == 0.15
    assert sh.results["entering_cfm"] > 0


# ── Connector pressure drop ─────────────────────────────────────────

def test_connector_pressure_drop_serialization():
    c = Connector(
        source_node_id="a",
        source_port_name="outlet",
        target_node_id="b",
        target_port_name="inlet",
        pressure_drop_iw=0.5,
    )
    d = c.to_dict()
    assert d["pressure_drop_iw"] == 0.5

    c2 = Connector.from_dict(d)
    assert c2.pressure_drop_iw == 0.5


def test_connector_pressure_drop_default():
    c = Connector.from_dict({
        "id": "test",
        "source_node_id": "a",
        "source_port_name": "outlet",
        "target_node_id": "b",
        "target_port_name": "inlet",
    })
    assert c.pressure_drop_iw == 0.0


# ── Solver pressure summary ─────────────────────────────────────────

def test_solver_pressure_summary():
    """Solver should collect pressure drops from all nodes and connectors."""
    graph = FlowGraph()

    source = _make_source(95.0, 0.40, 10000.0)
    coil = CoolingCoilNode(name="CC-1")
    coil.parameters["pressure_drop_iw"] = 2.0
    sink = AirSinkNode(name="Exhaust")

    graph.add_node(source)
    graph.add_node(coil)
    graph.add_node(sink)

    c1 = _connect(graph, source, "outlet", coil, "inlet")
    c1.pressure_drop_iw = 0.5
    _connect(graph, coil, "outlet", sink, "inlet")

    solver = FlowSolver(graph, calc)
    ok = solver.solve()
    assert ok is True

    ps = solver.pressure_summary
    assert ps["total_node_pressure_drop_iw"] == pytest.approx(2.0, abs=0.01)
    assert ps["total_connector_pressure_drop_iw"] == pytest.approx(0.5, abs=0.01)
    assert ps["total_system_pressure_drop_iw"] == pytest.approx(2.5, abs=0.01)


# ── Fan TSP validation ──────────────────────────────────────────────

def test_fan_tsp_zero_fan_efficiency_raises():
    fan = FanNode(name="BadFan")
    fan.parameters["input_mode"] = "tsp"
    fan.parameters["fan_efficiency"] = 0.0

    state = _state_95_40()
    fan.ports["inlet"].air_state = state
    fan.ports["inlet"].mass_flow = 750.0

    with pytest.raises(ValueError, match="Fan efficiency must be > 0"):
        fan.compute(calc)
