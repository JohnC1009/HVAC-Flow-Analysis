# HVAC Engineering Calculators

A professional web-based suite of HVAC engineering calculators built with Python (Flask) and modern HTML/CSS/JavaScript.

## Features

Five engineering calculators following industry standards:

1. **Conduit Fill Calculator (NEC)** - National Electrical Code compliance for electrical conduit fill calculations
2. **Pipe Sizing Calculator (ASHRAE)** - ASHRAE standards for hydronic pipe sizing
3. **Duct Pressure Drop Calculator (SMACNA)** - SMACNA standards for ductwork pressure loss calculations
4. **Fan Laws Calculator (AMCA)** - AMCA fan affinity laws for airflow system design
5. **Pump Laws Calculator (Hydraulic Institute)** - Pump affinity laws for hydronic system design

## Installation

### Requirements

- Python 3.8+
- Flask

### Setup

```bash
# Install dependencies
pip install flask

# Run the application
python app.py
```

The web interface will be available at `http://localhost:5000`

## Project Structure

```
hvac_calculators_web/
├── app.py                      # Flask application with API endpoints
├── hvac_calculators/
│   ├── __init__.py             # Backend calculation logic (5 calculators)
│   └── tests.py                # Unit tests for backend logic
├── templates/
│   └── index.html              # Main HTML template
├── static/
│   ├── style.css               # Stylesheet
│   └── app.js                  # Frontend JavaScript
├── test_integration.py         # End-to-end integration tests
└── README.md                   # This file
```

## API Endpoints

All endpoints accept POST requests with JSON payloads and return JSON responses.

### Conduit Fill
```bash
POST /api/calculate/conduit
{
  "conduit_type": "EMT",
  "conduit_size": 1.0,
  "wire_gauge": 12,
  "num_wires": 3,
  "insulation_type": "THHN"
}
```

### Pipe Sizing
```bash
POST /api/calculate/pipe
{
  "flow_rate_gpm": 50.0,
  "pipe_material": "CU",
  "max_velocity_fps": 8.0,
  "max_pressure_drop": 4.0
}
```

### Duct Pressure Drop
```bash
POST /api/calculate/duct
{
  "airflow_cfm": 1000,
  "duct_width_in": 12,
  "duct_height_in": 12,
  "duct_material": "galvanized",
  "length_ft": 100
}
```

### Fan Laws
```bash
POST /api/calculate/fan
{
  "cfm_1": 10000,
  "rpm_1": 1200,
  "bhp_1": 10.0,
  "calculation_type": "cfm",
  "cfm_2": 12000
}
```

### Pump Laws
```bash
POST /api/calculate/pump
{
  "gpm_1": 500,
  "rpm_1": 1750,
  "head_1": 100,
  "bhp_1": 25.0,
  "calculation_type": "gpm",
  "gpm_2": 600
}
```

## Testing

### Unit Tests (Backend)
```bash
python -m hvac_calculators.tests
```

### Integration Tests (Full Stack)
```bash
python test_integration.py
```

## Usage

1. Open `http://localhost:5000` in your web browser
2. Select a calculator tab
3. Enter the required parameters
4. Click "Calculate" to see results
5. Results display compliance status and engineering recommendations

## Standards & References

- **NEC** - National Electrical Code (NFPA 70)
- **ASHRAE** - American Society of Heating, Refrigerating and Air-Conditioning Engineers
- **SMACNA** - Sheet Metal and Air Conditioning Contractors' National Association
- **AMCA** - Air Movement and Control Association
- **HI** - Hydraulic Institute

## License

MIT License

## Author

HVAC Engineering Tools - 2026
