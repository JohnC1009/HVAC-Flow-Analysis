# HVAC Flow Analysis — Software Design Document

**Version:** 1.1
**Date:** February 2026
**Application:** Steady-state psychrometric analysis of HVAC air-handling systems

---

## 1. Purpose

HVAC Flow Analysis is a desktop application for modeling air-handling unit (AHU) configurations as directed graphs of equipment nodes connected by ductwork. The tool propagates moist-air state points through the system, computing thermodynamic transformations at each device, and displays results on a psychrometric chart.

Primary use cases:
- AHU design evaluation and comparison
- Energy recovery device sizing (enthalpy wheels, plate exchangers, runaround loops)
- Economizer strategy analysis (fixed, temperature, enthalpy modes)
- Zone load verification (supply air temperature delta, CFM requirements)
- System pressure drop budgeting for fan selection
- Control loop convergence analysis (setpoint-actuator feedback)

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py (PyQt5)                          │
│                     MainWindow / GUI Layer                       │
├─────────┬──────────────┬───────────────┬────────────────────────┤
│ Canvas  │  Property    │  Psychro      │  Toolbox               │
│ (Scene/ │  Panel       │  Chart        │  Panel                 │
│  View)  │              │  Widget       │                        │
├─────────┴──────────────┴───────────────┴────────────────────────┤
│                    Serialization Layer                           │
│                   (project_io.py / JSON)                         │
├─────────────────────────────────────────────────────────────────┤
│                      Solver Layer                                │
│         FlowSolver (DAG / Cycle-breaking / Control loops)        │
├──────────────────────────┬──────────────────────────────────────┤
│      Models Layer        │         Engine Layer                  │
│  BaseNode + 16 devices   │  PsychroCalc (psychrolib facade)     │
│  FlowGraph, Connector    │  AirState (immutable dataclass)      │
│  Project, ControlLoop    │  Constants (IP/SI units)             │
└──────────────────────────┴──────────────────────────────────────┘
```

**Layers** (bottom-up):

| Layer | Package | Responsibility |
|-------|---------|----------------|
| **Engine** | `hvac_flow.engine` | Psychrometric calculations via psychrolib; immutable `AirState` data model; physical constants |
| **Models** | `hvac_flow.models` | Equipment node classes, flow graph topology, connectors, project container |
| **Solver** | `hvac_flow.solver` | Graph traversal, cycle-breaking iteration, control loop bisection, pressure accumulation |
| **Serialization** | `hvac_flow.serialization` | JSON save/load of projects (nodes, connectors, control loops) |
| **GUI** | `hvac_flow.gui` | PyQt5 desktop interface: canvas, property editor, psychrometric chart, toolbox |

---

## 3. Package Structure

```
hvac_flow/
├── engine/
│   ├── __init__.py
│   ├── air_state.py              # AirState frozen dataclass
│   ├── constants.py              # UnitSystem enum, physical constants
│   └── psychro_calc.py           # PsychroCalc facade over psychrolib
├── models/
│   ├── __init__.py
│   ├── base_node.py              # BaseNode ABC, Port dataclass
│   ├── connector.py              # Connector (duct segment)
│   ├── flow_graph.py             # FlowGraph (directed graph)
│   ├── project.py                # Project container
│   ├── source_node.py            # SourceNode (air entry point)
│   ├── air_sink.py               # AirSinkNode (exhaust termination)
│   ├── fan.py                    # FanNode (supply fan)
│   ├── return_fan.py             # ReturnFanNode
│   ├── cooling_coil.py           # CoolingCoilNode
│   ├── heating_coil.py           # HeatingCoilNode
│   ├── zone_process.py           # ZoneProcessNode (room/space)
│   ├── mixing_box.py             # MixingBoxNode (economizer)
│   ├── duct_split.py             # DuctSplitNode
│   ├── enthalpy_wheel.py         # EnthalpyWheelNode (ERV)
│   ├── sensible_heat_recovery.py # SensibleHeatRecoveryNode
│   ├── desiccant_wheel.py        # DesiccantWheelNode
│   ├── indirect_evap_cooler.py   # IndirectEvapCoolerNode
│   ├── adiabatic_humidifier.py   # AdiabaticHumidifierNode
│   ├── steam_humidifier.py       # SteamHumidifierNode
│   └── runaround_loop.py         # RunaroundLoopNode
├── solver/
│   ├── __init__.py
│   ├── control_loop.py           # ControlLoop dataclass
│   └── flow_solver.py            # FlowSolver (main solver engine)
├── serialization/
│   ├── __init__.py
│   └── project_io.py             # ProjectIO (JSON save/load)
└── gui/
    ├── __init__.py
    ├── main_window.py            # MainWindow (top-level QMainWindow)
    ├── property_panel.py         # Parameter editor panel
    ├── toolbox_panel.py          # Device palette / toolbox
    ├── psychro_chart_widget.py   # Psychrometric chart (matplotlib)
    ├── dialogs/
    │   └── __init__.py
    └── canvas/
        ├── __init__.py
        ├── flow_scene.py         # QGraphicsScene for the flow diagram
        ├── flow_view.py          # QGraphicsView
        ├── node_item.py          # Visual representation of nodes
        ├── connector_item.py     # Visual representation of connectors
        └── port_item.py          # Visual representation of ports
```

---

## 4. Engine Layer

### 4.1 AirState (`air_state.py`)

An immutable, fully-resolved psychrometric state point. Every property is always populated — there are no partial states.

```python
@dataclass(frozen=True)
class AirState:
    dry_bulb: float          # °F [IP] or °C [SI]
    humidity_ratio: float    # lb_w/lb_da [IP] or kg_w/kg_da [SI]
    relative_humidity: float # 0.0 – 1.0
    wet_bulb: float          # °F [IP] or °C [SI]
    dew_point: float         # °F [IP] or °C [SI]
    enthalpy: float          # Btu/lb_da [IP] or kJ/kg_da [SI]
    specific_volume: float   # ft³/lb_da [IP] or m³/kg_da [SI]
    pressure: float          # psi [IP] or Pa [SI]
    label: Optional[str]     # Tracing label
```

Design rationale: Immutability ensures that state points cannot be accidentally modified as they propagate through the graph. Each device produces a fresh `AirState`.

### 4.2 PsychroCalc (`psychro_calc.py`)

Facade over the `psychrolib` library. This is the **only module** that imports psychrolib directly, isolating the dependency.

**Factory methods** (each returns a fully-resolved `AirState`):

| Method | Input Pair | Use Case |
|--------|-----------|----------|
| `from_db_rh(db, rh)` | Dry-bulb + RH | Source nodes, general purpose |
| `from_db_wb(db, wb)` | Dry-bulb + Wet-bulb | Alternate source input |
| `from_db_dp(db, dp)` | Dry-bulb + Dew-point | Alternate source input |
| `from_db_w(db, w)` | Dry-bulb + Humidity ratio | Most device computations |
| `from_enthalpy_w(h, w)` | Enthalpy + Humidity ratio | Mixing calculations |

**Error handling:** All factory methods wrap psychrolib calls in try/except, re-raising with contextual messages (input values, node name). Pre-checks reject negative humidity ratios before psychrolib is called.

**Utility methods:**
- `get_saturation_humidity_ratio(db)` — Saturation W at a given DB
- `get_moist_air_density(state)` — Density for CFM-to-mass-flow conversion
- `get_humidity_ratio_from_rh(db, rh)` — W from DB+RH pair
- `get_humidity_ratio_from_twetbulb(db, wb)` — W from DB+WB pair

### 4.3 Constants (`constants.py`)

| Constant | IP Value | Description |
|----------|---------|-------------|
| `STD_ATM_PRESSURE_IP` | 14.696 psi | Sea-level atmospheric pressure |
| `STD_AIR_DENSITY_IP` | 0.075 lb_da/ft³ | Standard air density at 70°F |
| `CP_AIR_IP` | 0.24 Btu/(lb·°F) | Specific heat of dry air |
| `HP_TO_BTUH` | 2545.0 | Horsepower to Btu/hr conversion |
| `TON_TO_BTUH` | 12000.0 | Ton of refrigeration to Btu/hr |
| `FAN_CONSTANT_IP` | 6356.0 | Fan law constant (CFM × inWG to HP) |

The `UnitSystem` enum (`IP` / `SI`) controls which unit set psychrolib uses.

---

## 5. Models Layer

### 5.1 BaseNode (`base_node.py`)

Abstract base class for all equipment. Defines the contract every device must fulfill.

**Identity & metadata:**
- `id: str` — UUID, unique within a project
- `name: str` — User-visible name
- `NODE_TYPE: str` — Machine-readable type key (e.g., `"cooling_coil"`)
- `DISPLAY_NAME: str` — Human-readable default name
- `position: tuple` — Canvas coordinates (x, y)

**Core abstractions:**
- `ports: Dict[str, Port]` — Named inlet/outlet connection points
- `parameters: Dict[str, Any]` — User-editable configuration
- `results: Dict[str, Any]` — Computed outputs (populated by `compute()`)
- `boundary_conditions: Dict[str, Any]` — Optional capacity limits

**Abstract methods every device must implement:**

| Method | Purpose |
|--------|---------|
| `_init_ports()` | Create inlet/outlet `Port` objects |
| `_init_parameters()` | Define parameters with defaults |
| `compute(calc)` | Transform inlet state(s) to outlet state(s) |

**Optional overrides:**

| Method | Purpose |
|--------|---------|
| `_init_boundary_conditions()` | Define capacity limits (e.g., max cooling tons) |
| `get_iterable_inlet()` | Return port name for cycle-breaking (two-stream devices) |
| `get_param_definitions()` | Metadata for GUI property editor |
| `get_boundary_definitions()` | Metadata for boundary-condition editor |
| `check_boundary_conditions()` | Compare results against limits, return warnings |

**Port dataclass:**
```python
@dataclass
class Port:
    name: str
    direction: str           # "inlet" or "outlet"
    air_state: Any = None    # AirState once resolved
    mass_flow: float = None  # lb_da/min [IP]
    connected_to: str = None # Connector ID
```

**Serialization:** `to_dict()` / `from_dict()` for JSON persistence.

### 5.2 Equipment Nodes — Device Catalog

#### 5.2.1 Single-Stream Devices

These devices have one inlet and one outlet. Air passes through; the device modifies its thermodynamic state.

| Device | NODE_TYPE | Ports | Key Parameters | Thermodynamic Process |
|--------|-----------|-------|----------------|----------------------|
| **SourceNode** | `source` | outlet | `input_mode`, `dry_bulb`, `relative_humidity`/`wet_bulb`/`dew_point`, `airflow_cfm` | Defines entering conditions and volumetric flow; converts CFM to mass flow via density |
| **AirSinkNode** | `air_sink` | inlet | (none) | Terminal node; absorbs flow, produces no output |
| **FanNode** | `fan` | inlet, outlet | `input_mode` (bhp/temp_rise/tsp), `bhp`, `motor_efficiency`, `fan_efficiency`, `temp_rise`, `total_static_pressure_iw` | Sensible heat addition: W constant, DB rises |
| **ReturnFanNode** | `return_fan` | inlet, outlet | (same as FanNode) | Same thermodynamics, for return/exhaust path |
| **CoolingCoilNode** | `cooling_coil` | inlet, outlet | `leaving_db`, `leaving_mode` (rh/w), `leaving_rh`, `leaving_w`, `pressure_drop_iw` | Cools and dehumidifies to fixed leaving condition |
| **HeatingCoilNode** | `heating_coil` | inlet, outlet | `leaving_db`, `pressure_drop_iw` | Sensible heating only; W unchanged |
| **ZoneProcessNode** | `zone_process` | supply_air, return_air | `input_mode` (loads/shr_total), `sensible_load_btuh`, `latent_load_btuh`, `total_load_btuh`, `sensible_heat_ratio`, `pressure_drop_iw` | Adds sensible heat (ΔDB) and latent heat (ΔW) to model room load |
| **AdiabaticHumidifierNode** | `adiabatic_humidifier` | inlet, outlet | `saturation_efficiency`, `pressure_drop_iw` | Constant wet-bulb process: DB drops, W rises, h ≈ constant |
| **SteamHumidifierNode** | `steam_humidifier` | inlet, outlet | `control_mode` (target_rh/target_w/steam_rate), `target_rh`, `target_w`, `steam_rate_lb_hr`, `pressure_drop_iw` | Isothermal humidification: DB constant, W rises |

**Fan input modes:**

| Mode | Input | Derived Quantities |
|------|-------|--------------------|
| `bhp` | Brake horsepower | heat = BHP × 2545 / η_motor; ΔT = heat / (ṁ × 60 × Cp) |
| `temp_rise` | Direct temperature rise (°F) | heat = ṁ × 60 × Cp × ΔT |
| `tsp` | Total static pressure (inWG) | BHP = CFM × TSP / (6356 × η_fan); then same as bhp mode |

**Zone process formulas:**
```
ΔT = Q_sensible / (ṁ × 60 × Cp)         → return_db = supply_db + ΔT
ΔW = Q_latent / (ṁ × 60 × h_fg)          → return_w  = supply_w + ΔW
```

#### 5.2.2 Multi-Stream Devices

These devices have two airstreams (supply + exhaust, primary + secondary, etc.) that exchange energy.

| Device | NODE_TYPE | Supply Ports | Exhaust/Secondary Ports | Key Parameters |
|--------|-----------|-------------|------------------------|----------------|
| **MixingBoxNode** | `mixing_box` | primary (in), secondary (in), mixed (out) | — | `primary_fraction`, `economizer_mode`, `min_oa_fraction`, `econ_high_limit_db`, `econ_high_limit_h`, `supply_setpoint_db`, `pressure_drop_iw` |
| **DuctSplitNode** | `duct_split` | inlet | outlet_a, outlet_b | `split_fraction`, `pressure_drop_iw` |
| **EnthalpyWheelNode** | `enthalpy_wheel` | supply_in, supply_out | exhaust_in, exhaust_out | `sensible_effectiveness`, `latent_effectiveness`, `bypass_fraction`, per-stream `pressure_drop_iw` |
| **SensibleHeatRecoveryNode** | `sensible_hr` | supply_in, supply_out | exhaust_in, exhaust_out | `sensible_effectiveness`, `device_type`, `bypass_fraction`, per-stream `pressure_drop_iw` |
| **DesiccantWheelNode** | `desiccant_wheel` | process_in, process_out | regen_in, regen_out | `dehumidification_effectiveness`, `heat_carryover_fraction`, per-stream `pressure_drop_iw` |
| **IndirectEvapCoolerNode** | `indirect_evap_cooler` | primary_in, primary_out | secondary_in, secondary_out | `wet_bulb_effectiveness`, per-stream `pressure_drop_iw` |
| **RunaroundLoopNode** | `runaround_loop` | supply_in, supply_out | exhaust_in, exhaust_out | `sensible_effectiveness`, `glycol_concentration_pct`, `glycol_flow_gpm`, per-stream `pressure_drop_iw` |

**Economizer modes (MixingBoxNode):**

| Mode | Logic |
|------|-------|
| `fixed` | Uses `primary_fraction` directly |
| `temperature` | OA lockout above `econ_high_limit_db`; otherwise modulates OA fraction to reach `supply_setpoint_db` |
| `enthalpy` | OA lockout above `econ_high_limit_h` or if OA enthalpy > RA enthalpy; otherwise modulates to setpoint |

**Bypass dampers (EnthalpyWheelNode, SensibleHeatRecoveryNode):**

When `bypass_fraction > 0`, only `(1 - bypass_fraction)` of supply air passes through the wheel. The wheel outlet is then mixed with the bypassed air. The exhaust-side effectiveness is reduced by the `through_fraction` multiplier to maintain energy balance.

#### 5.2.3 Common Device Features

**CFM reporting:** Every device computes actual CFM at local conditions:
```python
cfm = mass_flow × specific_volume   # lb_da/min × ft³/lb_da = ft³/min
```
Both entering and leaving CFM are included in `results` (they differ because specific volume changes with temperature/humidity).

**Pressure drop:** Every device includes a `pressure_drop_iw` parameter (inches water gauge, default 0.0). Two-stream devices have per-stream pressure drops. Fans have `total_static_pressure_iw` representing the pressure the fan must deliver.

**Boundary conditions:** Optional capacity limits that generate warnings (not errors) when exceeded. Examples:
- Cooling coil: max cooling tons
- Fan: max fan heat (Btu/hr)
- Enthalpy wheel: max recovery capacity

### 5.3 Connector (`connector.py`)

Represents a duct segment connecting one node's outlet port to another's inlet port.

```python
@dataclass
class Connector:
    id: str                          # UUID
    source_node_id: str              # Upstream node
    source_port_name: str            # Upstream port
    target_node_id: str              # Downstream node
    target_port_name: str            # Downstream port
    model_duct_losses: bool = False  # Enable heat gain/loss
    duct_ua: float = 0.0            # Btu/(hr·°F) overall UA
    ambient_temp: float = 85.0      # °F surrounding temperature
    pressure_drop_iw: float = 0.0   # inWG friction + fitting losses
```

**Duct heat gain/loss:** When `model_duct_losses` is enabled, the connector applies a sensible temperature change based on the UA value and ambient temperature. Humidity ratio is unchanged (no moisture transfer through duct walls).

### 5.4 FlowGraph (`flow_graph.py`)

Directed graph container holding nodes and connectors.

**Key operations:**

| Method | Purpose |
|--------|---------|
| `add_node(node)` | Register a node |
| `remove_node(node_id)` | Remove node and all its connectors |
| `add_connector(connector)` | Register a connector and update port references |
| `remove_connector(connector_id)` | Remove connector and clear port references |
| `topological_order()` | Kahn's algorithm; returns partial list if cycles exist |
| `get_source_nodes()` | Nodes with no connected inlets (graph roots) |
| `get_connector_to(node_id, port)` | Find connector feeding a specific inlet |
| `get_connectors_from(node_id)` | All connectors leaving a node |
| `validate()` | Check for disconnected ports; does NOT check for cycles |

**Cycle tolerance:** The graph does not reject cycles. Cycles are legal and handled by the solver via tear-edge iteration.

### 5.5 Project (`project.py`)

Top-level container holding all project state:

```python
class Project:
    graph: FlowGraph
    unit_system: UnitSystem       # IP or SI
    pressure: float               # Atmospheric pressure
    altitude_ft: float            # Site altitude
    name: str                     # Project name
    control_loops: List[ControlLoop]  # Optional setpoint controllers
```

---

## 6. Solver Layer

### 6.1 FlowSolver (`flow_solver.py`)

The solver propagates air states through the equipment graph. It supports three modes of operation, selected automatically based on graph topology and control loop configuration.

**Post-solve state:**

| Attribute | Type | Content |
|-----------|------|---------|
| `all_states` | `List[AirState]` | Every resolved outlet state (for psychrometric chart) |
| `errors` | `List[str]` | Fatal errors that prevented solving |
| `warnings` | `List[str]` | Non-fatal boundary condition and convergence warnings |
| `node_errors` | `Dict[str, List[str]]` | Per-node error messages |
| `node_warnings` | `Dict[str, List[str]]` | Per-node warnings |
| `pressure_summary` | `Dict[str, Any]` | Aggregated pressure drops |

#### 6.1.1 Mode 1: Single-Pass DAG

**Trigger:** No cycles detected, no active control loops.

**Algorithm:**
1. Topological sort via Kahn's algorithm
2. For each node in dependency order:
   a. Propagate upstream outlet states through connectors to inlet ports (applying duct losses if modeled)
   b. Call `node.compute(calc)`
   c. Check boundary conditions
   d. Collect outlet states for psychrometric chart
3. Compute pressure summary

#### 6.1.2 Mode 2: Cycle-Breaking Iteration

**Trigger:** Graph contains feedback loops (e.g., zone return air feeding back to an ERV exhaust inlet).

**Algorithm:**
1. **Detect cycles:** Run Kahn's algorithm; nodes not visited are in a cycle
2. **Find tear edges:** For each stuck node, check `get_iterable_inlet()`. Tear the connector feeding that port
3. **Seed initial guess:** Set torn inlet to 75°F / 50% RH / 750 lb_da/min
4. **Iterate** (up to 30 iterations):
   a. Execute forward pass (Mode 1) treating torn edges as pre-set
   b. Check convergence: `|ΔDB| ≤ 0.1°F` AND `|ΔW| ≤ 0.0001 lb_w/lb_da`
   c. Update torn inlet from actual upstream output
   d. Repeat until converged

#### 6.1.3 Mode 3: Control Loop Bisection

**Trigger:** One or more active `ControlLoop` objects attached.

**Algorithm:**
1. **Direction detection** (iterations 0–1):
   - Iteration 0: Set actuator to `actuator_min`, solve, read sensor
   - Iteration 1: Set actuator to `actuator_max`, solve, read sensor
   - Compare sensor values to determine slope sign
   - Validate setpoint is within achievable range
2. **Bisection** (iteration 2+):
   - Set actuator to midpoint `(lo + hi) / 2`
   - Solve and read sensor
   - If `|sensor - setpoint| ≤ tolerance`: converged
   - Otherwise update bisection bounds based on slope direction
3. Cycles and control loops can operate simultaneously

#### 6.1.4 Pressure Summary

After a successful solve, the solver collects all `pressure_drop_iw` values from node results and connector parameters:

```python
pressure_summary = {
    "nodes": {node_id: {"name": ..., "pressure_drop_iw": ...}, ...},
    "connectors": {conn_id: {"pressure_drop_iw": ...}, ...},
    "total_node_pressure_drop_iw": float,
    "total_connector_pressure_drop_iw": float,
    "total_system_pressure_drop_iw": float,
}
```

### 6.2 ControlLoop (`control_loop.py`)

Declarative specification of a setpoint-actuator feedback pair:

```python
@dataclass
class ControlLoop:
    name: str
    enabled: bool
    sensor_node_id: str          # Node to read
    sensor_port_name: str        # Port on that node
    sensor_property: str         # "dry_bulb" | "humidity_ratio" | "relative_humidity" | "enthalpy"
    setpoint: float              # Target value
    actuator_node_id: str        # Node to adjust
    actuator_parameter: str      # Parameter name (e.g., "bypass_fraction")
    actuator_min: float          # Lower bound (default 0.0)
    actuator_max: float          # Upper bound (default 1.0)
    tolerance: float             # Absolute convergence tolerance
    max_iterations: int          # Iteration limit
    # Post-solve state:
    converged: bool
    iterations_used: int
    final_error: float
    final_actuator_value: float
```

---

## 7. Serialization Layer

### 7.1 ProjectIO (`project_io.py`)

JSON-based save/load. File format version is `"1.1"`.

**Save structure:**
```json
{
  "version": "1.1",
  "name": "Project Name",
  "unit_system": "IP",
  "pressure": 14.696,
  "altitude_ft": 0.0,
  "nodes": [
    {
      "type": "source",
      "id": "uuid-...",
      "name": "OA Source",
      "position": [100, 200],
      "parameters": {"dry_bulb": 95.0, ...}
    }
  ],
  "connectors": [
    {
      "id": "uuid-...",
      "source_node_id": "...",
      "source_port_name": "outlet",
      "target_node_id": "...",
      "target_port_name": "inlet",
      "pressure_drop_iw": 0.5
    }
  ],
  "control_loops": [
    {
      "name": "ERV bypass",
      "sensor_node_id": "...",
      ...
    }
  ]
}
```

**Backward compatibility:** Loading a v1.0 file (no `control_loops` key) produces an empty control loop list. New parameters added to devices (e.g., `pressure_drop_iw`) use default values when absent from saved data via `dict.get()` with defaults.

**Node type registry:**
```python
NODE_TYPE_MAP = {
    "source": SourceNode,
    "cooling_coil": CoolingCoilNode,
    "heating_coil": HeatingCoilNode,
    "fan": FanNode,
    "return_fan": ReturnFanNode,
    "enthalpy_wheel": EnthalpyWheelNode,
    "mixing_box": MixingBoxNode,
    "zone_process": ZoneProcessNode,
    "duct_split": DuctSplitNode,
    "steam_humidifier": SteamHumidifierNode,
    "adiabatic_humidifier": AdiabaticHumidifierNode,
    "sensible_hr": SensibleHeatRecoveryNode,
    "runaround_loop": RunaroundLoopNode,
    "indirect_evap_cooler": IndirectEvapCoolerNode,
    "desiccant_wheel": DesiccantWheelNode,
    "air_sink": AirSinkNode,
}
```

---

## 8. GUI Layer

### 8.1 Architecture

The GUI is built with PyQt5 and organized into four main areas:

| Component | Module | Role |
|-----------|--------|------|
| **MainWindow** | `main_window.py` | Top-level window; menu bar, toolbar, layout management |
| **Flow Canvas** | `canvas/flow_scene.py`, `flow_view.py` | Interactive flow diagram editor (QGraphicsScene/View) |
| **Node Items** | `canvas/node_item.py`, `port_item.py` | Visual representations of equipment nodes and ports |
| **Connector Items** | `canvas/connector_item.py` | Visual representations of duct connections |
| **Property Panel** | `property_panel.py` | Parameter editor for selected node (driven by `get_param_definitions()`) |
| **Toolbox Panel** | `toolbox_panel.py` | Palette of available device types for drag-and-drop |
| **Psychro Chart** | `psychro_chart_widget.py` | Matplotlib-based psychrometric chart displaying `solver.all_states` |

### 8.2 Application Entry Point

```python
# main.py
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle("HVAC Flow Analysis — Psychrometric Tool")
    window.resize(1400, 900)
    window.show()
    sys.exit(app.exec_())
```

---

## 9. Data Flow

### 9.1 Computation Pipeline

```
User builds graph (GUI or programmatic)
        │
        ▼
FlowSolver.solve()
        │
        ├──► Validate graph (check connections)
        │
        ├──► Determine solve strategy (DAG / cycles / control loops)
        │
        ├──► For each node in topological order:
        │    ├──► Propagate upstream states through connectors
        │    │    └──► Apply duct losses if modeled
        │    ├──► node.compute(calc)
        │    │    ├──► Read inlet port states
        │    │    ├──► Apply thermodynamic transformations
        │    │    ├──► Compute CFM from mass_flow × specific_volume
        │    │    └──► Write outlet port states + results
        │    └──► Check boundary conditions
        │
        ├──► [If cycles: iterate with tear edges until convergence]
        │
        ├──► [If control loops: bisection on actuators until setpoint met]
        │
        ├──► Compute pressure summary
        │
        └──► Return success/failure + all_states for chart
```

### 9.2 Mass Flow Propagation

Mass flow originates at `SourceNode` and propagates downstream:

```
SourceNode:  mass_flow = airflow_cfm × moist_air_density(state)
Single-stream devices:  outlet.mass_flow = inlet.mass_flow  (conserved)
DuctSplit:   outlet_a.mass_flow = inlet.mass_flow × split_fraction
             outlet_b.mass_flow = inlet.mass_flow × (1 - split_fraction)
MixingBox:   mixed.mass_flow = primary.mass_flow + secondary.mass_flow
Two-stream:  each stream preserves its own mass_flow independently
```

### 9.3 CFM vs Mass Flow

The system uses **mass flow** (lb_da/min) as the fundamental quantity because it is conserved through temperature and humidity changes. **CFM** (actual volumetric flow at local conditions) is derived:

```
CFM = mass_flow × specific_volume
    = (lb_da/min) × (ft³/lb_da)
    = ft³/min
```

CFM changes through the system as air density varies with temperature and humidity. Each device reports both entering and leaving CFM in its results.

---

## 10. Key Engineering Formulas

### 10.1 Sensible Heat

```
Q_sensible = ṁ × 60 × Cp × ΔT    [Btu/hr]
  where: ṁ = mass flow [lb_da/min]
         Cp = 0.24 Btu/(lb·°F)
         ΔT = temperature change [°F]
```

### 10.2 Latent Heat

```
Q_latent = ṁ × 60 × h_fg × ΔW    [Btu/hr]
  where: h_fg = 1061 Btu/lb_water (heat of vaporization)
         ΔW = humidity ratio change [lb_w/lb_da]
```

### 10.3 Fan Power

```
BHP = CFM × TSP / (6356 × η_fan)  [HP]
  where: TSP = total static pressure [inWG]
         η_fan = fan total efficiency

Heat to air = BHP × 2545 / η_motor  [Btu/hr]
  (assumes motor in airstream; all electrical energy becomes heat)
```

### 10.4 Heat Recovery Effectiveness

```
Q_recovered = ε × C_min × (T_hot - T_cold)    [Btu/hr]
  where: ε = effectiveness (0–1)
         C_min = min(ṁ_supply, ṁ_exhaust) × 60 × Cp
```

### 10.5 Mixing

```
h_mixed = f × h_primary + (1-f) × h_secondary   [Btu/lb_da]
W_mixed = f × W_primary + (1-f) × W_secondary    [lb_w/lb_da]
  where: f = outdoor air fraction
```

---

## 11. Error Handling Strategy

### 11.1 Hierarchy

| Level | Source | Handling |
|-------|--------|----------|
| **Psychrolib errors** | Invalid thermodynamic inputs | Caught in PsychroCalc, re-raised with context |
| **Node compute errors** | Missing inputs, invalid parameters | Caught by solver, stored in `node_errors` |
| **Validation errors** | Disconnected ports | Reported before solve attempt |
| **Boundary warnings** | Capacity limits exceeded | Non-fatal, stored in `node_warnings` |
| **Convergence warnings** | Control loops or cycles not converged | Non-fatal, stored in `warnings` |

### 11.2 Humidity Ratio Safety

Several devices can algebraically produce invalid humidity ratios:
- **ZoneProcessNode:** Negative latent load → clamped to `max(W, 0)`
- **DesiccantWheelNode:** Extreme dehumidification → clamped to `[0, W_sat]`
- **PsychroCalc:** Pre-check rejects `W < 0` before calling psychrolib

---

## 12. Testing

### 12.1 Test Suite Structure

```
tests/
├── test_psychro_calc.py          # 10 tests: factory methods, error handling
├── test_zone_process.py          #  3 tests: loads mode, SHR mode, W clamping
├── test_enthalpy_wheel.py        #  5 tests: nominal, bypass 0/0.5/1.0, iterable inlet
├── test_sensible_hr.py           #  4 tests: nominal, bypass, W unchanged
├── test_desiccant_wheel.py       #  3 tests: nominal, W clamping, iterable inlet
├── test_control_loop.py          #  2 tests: serialization, convergence
├── test_flow_solver.py           #  4 tests: pipeline, cycle-breaking, errors, DAG fast path
├── test_serialization.py         #  3 tests: roundtrip, control loops, v1 compat
└── test_cfm_pressure_drop.py     # 20 tests: CFM at every device, pressure drops,
                                  #           fan TSP mode, connector serialization,
                                  #           solver pressure summary
```

**Total: 54 tests** — all passing.

### 12.2 Test Patterns

- **Unit tests:** Create a device, manually set inlet ports, call `compute()`, assert outlet values
- **Integration tests:** Build a multi-node graph, solve, verify end-to-end results
- **Invariant tests:** Verify W unchanged through sensible-only devices, mass flow conserved
- **Edge case tests:** Negative humidity clamping, zero efficiency, missing connections

---

## 13. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `PyQt5` | ≥ 5.15 | Desktop GUI framework |
| `psychrolib` | ≥ 2.5.0 | ASHRAE-standard psychrometric calculations |
| `matplotlib` | ≥ 3.5 | Psychrometric chart rendering |
| `numpy` | ≥ 1.21 | Numerical support for matplotlib |
| `pytest` | (dev) | Test framework |

---

## 14. Current Limitations

| Area | Status | Notes |
|------|--------|-------|
| **Pressure drop calculation** | User-input only | No automatic duct sizing, friction factor calculation, or fan curve matching |
| **Part-load performance** | Not modeled | Equipment capacities are fixed, not modulated by load |
| **Transient/dynamic analysis** | Not supported | Solver is steady-state only |
| **VAV systems** | Not modeled | No variable-volume terminal units |
| **Water/glycol psychrometrics** | Not modeled | Only moist air is tracked |
| **ASHRAE 62.1 ventilation** | Not automated | CFM/person calculations are manual |
| **Acoustic analysis** | Not supported | No sound power or noise criteria |
| **SI unit support** | Partial | Constants defined; device code is IP-focused |

---

## 15. Extension Points

The architecture is designed for straightforward extension:

1. **New device types:** Subclass `BaseNode`, implement `_init_ports()`, `_init_parameters()`, `compute()`, and add the `NODE_TYPE` to `NODE_TYPE_MAP` in `project_io.py`

2. **New control strategies:** The `ControlLoop` dataclass is generic — any `sensor_property` on any port can drive any `actuator_parameter` on any node

3. **New psychrometric inputs:** Add factory methods to `PsychroCalc` (e.g., `from_db_enthalpy`)

4. **Fan curves:** Extend `FanNode` with a curve-fit function that maps CFM to static pressure, replacing the constant-TSP model

5. **System pressure path analysis:** Extend `_compute_pressure_summary()` to walk individual flow paths from source to sink, comparing path totals against fan TSP
