# Implementation Plan

## Overview

Six workstreams, ordered by dependency. Estimated ~15 new/modified files.

---

## 1. Psychrolib Error Handling (`psychro_calc.py`)

**Problem:** All six factory methods call psychrolib bare. Invalid inputs
(negative W, supersaturated conditions, DB below dew point) produce raw
`ValueError` with cryptic messages like `"Humidity ratio is negative"`.

**Changes to `hvac_flow/engine/psychro_calc.py`:**

Wrap each factory method's psychrolib calls in try/except ValueError, re-raising
with a clear message that names the method, the inputs, and what went wrong:

```python
def from_db_w(self, dry_bulb, hum_ratio, label=None):
    if hum_ratio < 0:
        raise ValueError(
            f"Humidity ratio cannot be negative (got {hum_ratio:.6f}). "
            f"Check upstream calculations for DB={dry_bulb:.1f}."
        )
    try:
        rh = psychrolib.GetRelHumFromHumRatio(...)
        ...
    except ValueError as e:
        raise ValueError(
            f"Cannot construct air state from DB={dry_bulb:.1f}, "
            f"W={hum_ratio:.6f}: {e}"
        ) from e
```

Apply to: `from_db_rh`, `from_db_wb`, `from_db_dp`, `from_db_w`,
`from_enthalpy_w`. Add a pre-check for `hum_ratio < 0` on the W-based methods.

---

## 2. Bounds-Check Humidity Ratios

**Problem:** `desiccant_wheel.py` and `zone_process.py` compute W values
algebraically. Extreme inputs can push W negative or above saturation, which
then crashes psychrolib.

**Changes:**

### `hvac_flow/models/desiccant_wheel.py` (after line 59)
After computing `process_out_w`, clamp to `[0, W_sat]`:
```python
process_out_w = max(process_out_w, 0.0)
w_sat = calc.get_saturation_humidity_ratio(process_out_db)
if process_out_w > w_sat:
    process_out_w = w_sat
    # (optionally log a warning)
```
Same for `regen_out_w` (after line 75).

### `hvac_flow/models/zone_process.py` (after line 62)
After computing `return_w`:
```python
return_w = max(return_w, 0.0)
```

---

## 3. Inline Import Fix (`indirect_evap_cooler.py`)

**Problem:** `CP_AIR_IP` is imported inside `compute()` at line 59.

**Fix:** Move `from hvac_flow.engine.constants import CP_AIR_IP` to the
top of the file (after line 8), remove line 59.

---

## 4. Bypass Dampers on Enthalpy Wheel and Sensible Heat Recovery

Add a `bypass_fraction` parameter (0.0–1.0) to both wheel nodes. At 0.0 the
behavior is identical to today. At 0.3, 30% of supply air bypasses the wheel
and remixes with the processed stream.

### `hvac_flow/models/enthalpy_wheel.py`

**Parameter addition** (in `_init_parameters`):
```python
"bypass_fraction": 0.0,  # 0 = all air through wheel, 1 = full bypass
```

**Compute changes** (replacing lines 43–67):
```python
bypass = self.parameters["bypass_fraction"]
through_fraction = 1.0 - bypass

# --- Wheel physics on through-flow portion (unchanged math) ---
supply_out_db = s_in.dry_bulb + eps_s * (e_in.dry_bulb - s_in.dry_bulb)
supply_out_w  = s_in.humidity_ratio + eps_l * (e_in.humidity_ratio - s_in.humidity_ratio)
wheel_out = calc.from_db_w(supply_out_db, supply_out_w, ...)

# --- Mix wheel outlet with bypassed air ---
if bypass > 0.0:
    mixed_w = through_fraction * wheel_out.humidity_ratio + bypass * s_in.humidity_ratio
    mixed_h = through_fraction * wheel_out.enthalpy + bypass * s_in.enthalpy
    supply_out = calc.from_enthalpy_w(mixed_h, mixed_w, label=...)
else:
    supply_out = wheel_out

# Exhaust side: effectiveness applies to the through-flow only,
# but energy balance must account for the reduced supply flow through the wheel.
# The exhaust side sees the full exhaust flow regardless of bypass.
exhaust_out_db = e_in.dry_bulb - eps_s * through_fraction * (e_in.dry_bulb - s_in.dry_bulb)
exhaust_out_w  = e_in.humidity_ratio - eps_l * through_fraction * (e_in.humidity_ratio - s_in.humidity_ratio)
exhaust_out = calc.from_db_w(exhaust_out_db, exhaust_out_w, ...)
```

The exhaust side correction is important: when only 70% of supply air goes
through the wheel, the exhaust side recovers less energy. The `through_fraction`
multiplier on the delta accounts for the reduced heat exchange.

**New result field:**
```python
"bypass_fraction": bypass,
```

**Param definitions update:** Add bypass_fraction entry.

### `hvac_flow/models/sensible_heat_recovery.py`

Same pattern but simpler — only DB changes, W stays constant on both sides.

**Parameter addition:**
```python
"bypass_fraction": 0.0,
```

**Compute changes:**
```python
bypass = self.parameters["bypass_fraction"]
through_fraction = 1.0 - bypass

supply_out_db = s_in.dry_bulb + eps * (e_in.dry_bulb - s_in.dry_bulb)
wheel_out = calc.from_db_w(supply_out_db, s_in.humidity_ratio, ...)

if bypass > 0.0:
    mixed_db = through_fraction * supply_out_db + bypass * s_in.dry_bulb
    supply_out = calc.from_db_w(mixed_db, s_in.humidity_ratio, label=...)
else:
    supply_out = wheel_out

exhaust_out_db = e_in.dry_bulb - eps * through_fraction * (e_in.dry_bulb - s_in.dry_bulb)
exhaust_out = calc.from_db_w(exhaust_out_db, e_in.humidity_ratio, ...)
```

---

## 5. Control Loop Framework

### 5a. Data Model — `hvac_flow/solver/control_loop.py` (new file)

```python
@dataclass
class ControlLoop:
    """A setpoint-actuator pair that the solver iterates to converge."""

    name: str                    # e.g., "ERV bypass control"
    enabled: bool = True

    # What to control (sensor)
    sensor_node_id: str = ""     # Node whose output we read
    sensor_port_name: str = ""   # Port on that node
    sensor_property: str = ""    # "dry_bulb", "humidity_ratio", "relative_humidity", "enthalpy"

    # Target value
    setpoint: float = 0.0       # Target value for the sensor property

    # What to adjust (actuator)
    actuator_node_id: str = ""   # Node whose parameter we adjust
    actuator_parameter: str = "" # Parameter name on that node (e.g., "bypass_fraction")

    # Actuator bounds (hard clamp from boundary conditions fallback)
    actuator_min: float = 0.0
    actuator_max: float = 1.0

    # Convergence
    tolerance: float = 0.5      # Absolute tolerance on sensor value
    max_iterations: int = 20

    # State (populated after solve)
    converged: bool = False
    iterations_used: int = 0
    final_error: float = 0.0
    final_actuator_value: float = 0.0

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> "ControlLoop": ...
```

### 5b. Solver Changes — `hvac_flow/solver/flow_solver.py`

Add an optional `control_loops` list to FlowSolver:

```python
class FlowSolver:
    def __init__(self, graph, calc):
        ...
        self.control_loops: List[ControlLoop] = []

    def solve(self) -> bool:
        # If no enabled control loops, single-pass as before
        if not any(cl.enabled for cl in self.control_loops):
            return self._solve_once()

        # Iterative solve with control loops
        return self._solve_with_controls()

    def _solve_once(self) -> bool:
        """Current single-pass logic, extracted."""
        ...  # Existing code from solve()

    def _solve_with_controls(self) -> bool:
        """Outer loop: bisection on each control loop's actuator."""
        active_loops = [cl for cl in self.control_loops if cl.enabled]
        max_outer = max(cl.max_iterations for cl in active_loops)

        # Initialize bisection bounds for each loop
        for cl in active_loops:
            cl._lo = cl.actuator_min
            cl._hi = cl.actuator_max
            cl.converged = False

        for iteration in range(max_outer):
            # Set actuator values (bisection midpoint)
            for cl in active_loops:
                if cl.converged:
                    continue
                mid = (cl._lo + cl._hi) / 2.0
                node = self.graph.nodes[cl.actuator_node_id]
                node.parameters[cl.actuator_parameter] = mid

            # Run single pass
            if not self._solve_once():
                return False

            # Check convergence and update bisection bounds
            all_converged = True
            for cl in active_loops:
                if cl.converged:
                    continue
                sensor_val = self._read_sensor(cl)
                error = sensor_val - cl.setpoint
                cl.final_error = error
                cl.iterations_used = iteration + 1
                mid = self.graph.nodes[cl.actuator_node_id].parameters[cl.actuator_parameter]
                cl.final_actuator_value = mid

                if abs(error) <= cl.tolerance:
                    cl.converged = True
                    continue

                all_converged = False
                # Bisection: if sensor > setpoint, we need MORE of the actuator
                # (direction depends on the actuator-sensor relationship)
                # Determine direction by sign: increasing actuator should
                # generally decrease the sensor for bypass (more bypass = lower temp)
                if error > 0:
                    cl._lo = mid  # Need more bypass
                else:
                    cl._hi = mid  # Need less bypass

            if all_converged:
                break

        return True

    def _read_sensor(self, cl: ControlLoop) -> float:
        """Read the sensor value from the solved graph."""
        node = self.graph.nodes[cl.sensor_node_id]
        port = node.ports[cl.sensor_port_name]
        state = port.air_state
        return getattr(state, cl.sensor_property)
```

**Design notes on bisection direction:**

The bisection above assumes increasing the actuator *increases* the sensor
reading. This is correct for some actuator-sensor pairs but wrong for others.
To handle this generically, the first two iterations will determine the
direction (sign of d(sensor)/d(actuator)) and flip the bisection logic
accordingly. This avoids the user having to specify direction.

Specifically: on iteration 0, evaluate at actuator_min. On iteration 1,
evaluate at actuator_max. Compare sensor values to determine the slope sign.
Then bisect accordingly.

### 5c. Project Integration

**`hvac_flow/models/project.py`:** Add `control_loops: List[ControlLoop] = []`

**`hvac_flow/serialization/project_io.py`:**
- Save: include `"control_loops": [cl.to_dict() for cl in project.control_loops]`
- Load: deserialize control loops from JSON, attach to project
- Version bump to `"1.1"` (backward compatible: old files have no control_loops key)

### 5d. Convergence direction auto-detection

Replace the simple bisection logic with a two-probe direction-detection step:

```python
def _solve_with_controls(self):
    active_loops = [cl for cl in self.control_loops if cl.enabled]

    # Probe 1: solve at actuator_min
    for cl in active_loops:
        node = self.graph.nodes[cl.actuator_node_id]
        node.parameters[cl.actuator_parameter] = cl.actuator_min
    self._solve_once()
    for cl in active_loops:
        cl._sensor_at_min = self._read_sensor(cl)

    # Probe 2: solve at actuator_max
    for cl in active_loops:
        node = self.graph.nodes[cl.actuator_node_id]
        node.parameters[cl.actuator_parameter] = cl.actuator_max
    self._solve_once()
    for cl in active_loops:
        cl._sensor_at_max = self._read_sensor(cl)
        # Determine: does increasing actuator increase or decrease sensor?
        cl._increasing = cl._sensor_at_max > cl._sensor_at_min

    # Validate setpoint is reachable
    for cl in active_loops:
        lo_val = min(cl._sensor_at_min, cl._sensor_at_max)
        hi_val = max(cl._sensor_at_min, cl._sensor_at_max)
        if cl.setpoint < lo_val - cl.tolerance or cl.setpoint > hi_val + cl.tolerance:
            self.warnings.append(
                f"[Control: {cl.name}] Setpoint {cl.setpoint} is outside "
                f"achievable range [{lo_val:.1f}, {hi_val:.1f}]"
            )
            cl.converged = False
            cl._skip = True
        else:
            cl._skip = False

    # Bisection loop
    for cl in active_loops:
        cl._lo = cl.actuator_min
        cl._hi = cl.actuator_max

    for iteration in range(max(cl.max_iterations for cl in active_loops)):
        for cl in active_loops:
            if cl.converged or cl._skip:
                continue
            mid = (cl._lo + cl._hi) / 2.0
            node = self.graph.nodes[cl.actuator_node_id]
            node.parameters[cl.actuator_parameter] = mid

        if not self._solve_once():
            return False

        all_done = True
        for cl in active_loops:
            if cl.converged or cl._skip:
                continue
            sensor_val = self._read_sensor(cl)
            error = sensor_val - cl.setpoint
            mid = self.graph.nodes[cl.actuator_node_id].parameters[cl.actuator_parameter]
            cl.final_error = error
            cl.final_actuator_value = mid
            cl.iterations_used = iteration + 1

            if abs(error) <= cl.tolerance:
                cl.converged = True
                continue

            all_done = False
            # If increasing actuator increases sensor:
            #   sensor too high (error > 0) -> decrease actuator -> hi = mid
            #   sensor too low  (error < 0) -> increase actuator -> lo = mid
            if cl._increasing:
                if error > 0:
                    cl._hi = mid
                else:
                    cl._lo = mid
            else:
                if error > 0:
                    cl._lo = mid
                else:
                    cl._hi = mid

        if all_done:
            break

    return True
```

---

## 6. Tests

### New files:
- `tests/test_psychro_calc.py` — Error handling, edge cases, known-value checks
- `tests/test_enthalpy_wheel.py` — Nominal, bypass=0/0.5/1.0, energy balance
- `tests/test_sensible_hr.py` — Nominal, bypass, W-unchanged invariant
- `tests/test_desiccant_wheel.py` — Nominal, W-clamping, energy balance
- `tests/test_zone_process.py` — Both input modes, negative-W clamping
- `tests/test_indirect_evap.py` — Nominal, mass balance
- `tests/test_mixing_box.py` — Fixed, temperature, enthalpy economizer modes
- `tests/test_flow_solver.py` — Single-pass pipeline, multi-node graph, error propagation
- `tests/test_control_loop.py` — Convergence, unreachable setpoint warning, direction detection
- `tests/test_serialization.py` — Round-trip save/load including control loops

### Test patterns:
- Each node test creates the node, sets inlet ports manually, calls `compute(calc)`,
  and asserts outlet values within tolerance
- Energy balance tests: `|Q_supply + Q_exhaust| < tolerance` for two-stream devices
- Bypass tests: verify bypass=0.0 matches original behavior exactly
- Control loop tests: build a small 3-node graph (source → wheel → sink),
  attach a control loop, verify convergence within tolerance

---

## File Change Summary

| File | Action |
|------|--------|
| `hvac_flow/engine/psychro_calc.py` | Modify — wrap psychrolib calls |
| `hvac_flow/models/desiccant_wheel.py` | Modify — clamp W values |
| `hvac_flow/models/zone_process.py` | Modify — clamp W values |
| `hvac_flow/models/indirect_evap_cooler.py` | Modify — move inline import |
| `hvac_flow/models/enthalpy_wheel.py` | Modify — add bypass_fraction |
| `hvac_flow/models/sensible_heat_recovery.py` | Modify — add bypass_fraction |
| `hvac_flow/solver/control_loop.py` | **New** — ControlLoop dataclass |
| `hvac_flow/solver/flow_solver.py` | Modify — iterative solve |
| `hvac_flow/solver/__init__.py` | Modify — export ControlLoop |
| `hvac_flow/models/project.py` | Modify — add control_loops list |
| `hvac_flow/serialization/project_io.py` | Modify — persist control loops |
| `tests/test_psychro_calc.py` | **New** |
| `tests/test_enthalpy_wheel.py` | **New** |
| `tests/test_sensible_hr.py` | **New** |
| `tests/test_desiccant_wheel.py` | **New** |
| `tests/test_zone_process.py` | **New** |
| `tests/test_indirect_evap.py` | **New** |
| `tests/test_mixing_box.py` | **New** |
| `tests/test_flow_solver.py` | **New** |
| `tests/test_control_loop.py` | **New** |
| `tests/test_serialization.py` | **New** |

## Implementation Order

1. **Psychrolib error handling** (no dependencies)
2. **Bounds-check W values** (no dependencies)
3. **Inline import fix** (no dependencies)
4. **Bypass dampers** (depends on 1 for error handling)
5. **Control loop framework** (depends on 4 for bypass as first actuator)
6. **Tests** (depends on all above)

Steps 1-3 can be done in parallel. Step 4 depends on 1. Step 5 depends on 4.
Step 6 is last.
