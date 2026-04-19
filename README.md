# HVAC Flow Analysis

A Python-based psychrometric analysis tool for HVAC air handling systems. Design, simulate, and evaluate air-side HVAC configurations with an intuitive visual interface.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **Visual Flow Editor**: Drag-and-drop interface for building air handling systems
- **Psychrometric Calculations**: Full ASHRAE-compliant psychrometric analysis using psychrolib
- **Equipment Library**: 20+ HVAC components including:
  - Coils (cooling, heating)
  - Fans and pumps
  - Mixing boxes with economizer control
  - Heat recovery devices (sensible, enthalpy, runaround, desiccant)
  - Humidifiers (steam, adiabatic)
  - Air sources and sinks
  - Duct splits and zone processes
- **System Validation**: Automatic detection of unusual configurations and energy inefficiencies
- **Boundary Conditions**: Set capacity limits and get warnings when exceeded
- **Export/Import**: Save and load projects as JSON files

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Quick Install

```bash
# Clone the repository
git clone https://github.com/JohnC1009/HVAC-Flow-Analysis.git
cd HVAC-Flow-Analysis

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

- **PyQt5** (>=5.15) - GUI framework
- **psychrolib** (>=2.5.0) - Psychrometric calculations
- **matplotlib** (>=3.5) - Chart plotting
- **numpy** (>=1.21) - Numerical operations

## Quick Start

### Running the Application

```bash
python main.py
```

### Building Your First System

1. **Start the application** - The main window opens with a blank canvas
2. **Add equipment** - Drag components from the toolbox onto the canvas:
   - Start with a **Source** (outdoor air)
   - Add a **Cooling Coil**
   - Add a **Fan**
   - End with an **Air Sink** (zone)
3. **Connect components** - Click and drag between outlet and inlet ports
4. **Configure parameters** - Select a node and edit properties in the panel:
   - Set outdoor air to 95°F, 40% RH
   - Set cooling coil leaving temperature to 55°F
   - Set fan BHP to 15 HP
5. **Solve** - The system automatically calculates:
   - Cooling loads (total, sensible, latent)
   - Fan heat gain
   - Air states at each point
   - Psychrometric chart visualization

### Example: Simple AHU

```python
from hvac_flow.engine.psychro_calc import PsychroCalc
from hvac_flow.engine.constants import UnitSystem
from hvac_flow.models.source_node import SourceNode
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.fan import FanNode
from hvac_flow.models.air_sink import AirSinkNode
from hvac_flow.models.connector import Connector
from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.solver.flow_solver import FlowSolver

# Create calculator
calc = PsychroCalc(unit_system=UnitSystem.IP)

# Create nodes
source = SourceNode(name="OA Intake")
source.parameters["dry_bulb"] = 95.0
source.parameters["relative_humidity"] = 0.40
source.parameters["mass_flow"] = 2000.0

coil = CoolingCoilNode(name="Cooling Coil")
coil.parameters["leaving_db"] = 55.0
coil.parameters["leaving_mode"] = "rh"
coil.parameters["leaving_rh"] = 0.90

fan = FanNode(name="Supply Fan")
fan.parameters["input_mode"] = "bhp"
fan.parameters["bhp"] = 15.0
fan.parameters["motor_efficiency"] = 0.90

sink = AirSinkNode(name="Zone")

# Build graph
graph = FlowGraph()
for node in [source, coil, fan, sink]:
    graph.add_node(node)

# Connect nodes
graph.add_connector(Connector(
    source_node_id=source.id, source_port_name="outlet",
    target_node_id=coil.id, target_port_name="inlet"
))
graph.add_connector(Connector(
    source_node_id=coil.id, source_port_name="outlet",
    target_node_id=fan.id, target_port_name="inlet"
))
graph.add_connector(Connector(
    source_node_id=fan.id, source_port_name="outlet",
    target_node_id=sink.id, target_port_name="inlet"
))

# Solve
solver = FlowSolver(graph, calc)
if solver.solve():
    print(f"Cooling Load: {coil.results['total_load_tons']:.1f} tons")
    print(f"Fan Heat: {fan.results['fan_heat_btuh']:.0f} Btu/hr")
else:
    print("Errors:", solver.errors)
```

## Project Structure

```
HVAC-Flow-Analysis/
├── main.py                      # Application entry point
├── requirements.txt             # Python dependencies
├── hvac_flow/
│   ├── __init__.py
│   ├── engine/                  # Core calculation engine
│   │   ├── air_state.py         # Air state dataclass
│   │   ├── psychro_calc.py      # Psychrometric calculations
│   │   └── constants.py         # Physical constants
│   ├── models/                  # Equipment models
│   │   ├── base_node.py         # Abstract base class
│   │   ├── flow_graph.py        # System graph
│   │   ├── connector.py         # Duct connections
│   │   ├── source_node.py       # Air sources
│   │   ├── air_sink.py          # Air sinks
│   │   ├── cooling_coil.py      # Cooling coils
│   │   ├── heating_coil.py      # Heating coils
│   │   ├── fan.py               # Fans
│   │   ├── mixing_box.py        # Mixing boxes with economizer
│   │   ├── sensible_heat_recovery.py
│   │   ├── enthalpy_wheel.py
│   │   ├── runaround_loop.py
│   │   ├── desiccant_wheel.py
│   │   ├── steam_humidifier.py
│   │   ├── adiabatic_humidifier.py
│   │   ├── indirect_evap_cooler.py
│   │   ├── duct_split.py
│   │   ├── zone_process.py
│   │   └── project.py
│   ├── solver/                  # Flow solver
│   │   └── flow_solver.py       # Topological solver
│   ├── validation/              # System validation
│   │   └── system_validator.py  # Configuration checks
│   ├── gui/                     # User interface
│   │   ├── main_window.py
│   │   ├── canvas/
│   │   ├── property_panel.py
│   │   ├── toolbox_panel.py
│   │   ├── psychro_chart_widget.py
│   │   └── dialogs/
│   └── serialization/           # Save/load
│       └── project_io.py
└── tests/                       # Unit tests
    ├── test_air_state.py
    ├── test_psychro_calc.py
    ├── test_flow_graph.py
    ├── test_nodes.py
    ├── test_flow_solver.py
    └── test_system_validation.py
```

## Equipment Library

### Air Handling Components

| Component | Description | Key Parameters |
|-----------|-------------|----------------|
| **Source** | Outdoor/return air inlet | DB, RH, Mass flow |
| **Cooling Coil** | Sensible and latent cooling | Leaving DB, Leaving RH/W |
| **Heating Coil** | Sensible heating | Leaving DB |
| **Fan** | Air movement with heat gain | BHP or temp rise, efficiency |
| **Mixing Box** | OA/RA mixing with economizer | OA fraction, economizer mode |
| **Air Sink** | Zone or exhaust | (receives air state) |

### Heat Recovery

| Component | Description | Key Parameters |
|-----------|-------------|----------------|
| **Sensible Heat Recovery** | Plate/fixed heat exchanger | Effectiveness |
| **Enthalpy Wheel** | Total energy recovery | Sensible & latent effectiveness |
| **Runaround Loop** | Coil-to-coil heat recovery | Effectiveness |
| **Desiccant Wheel** | Dehumidification | Moisture removal, effectiveness |

### Other Equipment

| Component | Description | Key Parameters |
|-----------|-------------|----------------|
| **Steam Humidifier** | Isothermal humidification | Humidity ratio setpoint |
| **Adiabatic Humidifier** | Evaporative cooling | Effectiveness, efficiency |
| **Indirect Evap Cooler** | Sensible cooling without moisture | Effectiveness |
| **Duct Split** | Parallel flow paths | Split fractions |
| **Zone Process** | Simplified load model | Sensible/latent loads |

## System Validation

The tool automatically checks for:

- **Energy Waste**: Cooling followed by heating
- **Missing Heat Recovery**: 100% OA systems without heat recovery
- **Freeze Protection**: Cold climates without preheat
- **Economizer Utilization**: Not using free cooling when available
- **Unusual Configurations**: Multiple mixing boxes, excessive coils
- **Pressure Drops**: Too many components in series

Enable validation:

```python
from hvac_flow.validation.system_validator import SystemValidator

validator = SystemValidator()
warnings = validator.validate_configuration(graph)
for warning in warnings:
    print(warning)
```

## Running Tests

```bash
# Run all tests
python -m unittest discover tests/

# Run specific test file
python -m unittest tests.test_nodes

# Run with verbose output
python -m unittest discover tests/ -v
```

## Boundary Conditions

Set capacity limits on equipment to get warnings when exceeded:

```python
# Set coil capacity limit
coil.boundary_conditions["total_load_btuh"] = 100000.0

# Solve - warnings will be generated if exceeded
solver.solve()
if coil.capacity_warnings:
    for warning in coil.capacity_warnings:
        print(warning)
```

## Economizer Modes

The mixing box supports three economizer control strategies:

1. **Fixed**: Constant OA fraction (no economizer)
2. **Temperature**: Modulate OA to maintain setpoint, lockout above high limit
3. **Enthalpy**: Use enthalpy comparison for more efficient control

```python
mixer.parameters["economizer_mode"] = "temperature"
mixer.parameters["min_oa_fraction"] = 0.15
mixer.parameters["econ_high_limit_db"] = 75.0
mixer.parameters["supply_setpoint_db"] = 55.0
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Psychrometric calculations powered by [psychrolib](https://github.com/psychrometrics/psychrolib)
- GUI built with [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)
- Chart plotting with [matplotlib](https://matplotlib.org/)

## Support

For issues, questions, or feature requests, please open an issue on GitHub.
