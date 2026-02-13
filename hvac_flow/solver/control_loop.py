"""Control loop data model — setpoint-actuator pairs for iterative solving."""

from dataclasses import dataclass, field


@dataclass
class ControlLoop:
    """A setpoint-actuator pair that the solver iterates to converge.

    The solver reads a *sensor* (an air-state property on a specific port),
    compares it to the *setpoint*, and adjusts an *actuator* (a parameter
    on a specific node) using bisection until the error is within tolerance.

    Control loops are optional and stored per-project.
    """

    name: str = ""
    enabled: bool = True

    # Sensor — what we measure
    sensor_node_id: str = ""
    sensor_port_name: str = ""
    sensor_property: str = "dry_bulb"  # "dry_bulb", "humidity_ratio", "relative_humidity", "enthalpy"

    # Target
    setpoint: float = 0.0

    # Actuator — what we adjust
    actuator_node_id: str = ""
    actuator_parameter: str = ""  # e.g., "bypass_fraction"

    # Actuator bounds (hard clamps)
    actuator_min: float = 0.0
    actuator_max: float = 1.0

    # Convergence settings
    tolerance: float = 0.5
    max_iterations: int = 20

    # State populated after solve
    converged: bool = field(default=False, repr=False)
    iterations_used: int = field(default=0, repr=False)
    final_error: float = field(default=0.0, repr=False)
    final_actuator_value: float = field(default=0.0, repr=False)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "sensor_node_id": self.sensor_node_id,
            "sensor_port_name": self.sensor_port_name,
            "sensor_property": self.sensor_property,
            "setpoint": self.setpoint,
            "actuator_node_id": self.actuator_node_id,
            "actuator_parameter": self.actuator_parameter,
            "actuator_min": self.actuator_min,
            "actuator_max": self.actuator_max,
            "tolerance": self.tolerance,
            "max_iterations": self.max_iterations,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ControlLoop":
        return cls(
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
            sensor_node_id=data.get("sensor_node_id", ""),
            sensor_port_name=data.get("sensor_port_name", ""),
            sensor_property=data.get("sensor_property", "dry_bulb"),
            setpoint=data.get("setpoint", 0.0),
            actuator_node_id=data.get("actuator_node_id", ""),
            actuator_parameter=data.get("actuator_parameter", ""),
            actuator_min=data.get("actuator_min", 0.0),
            actuator_max=data.get("actuator_max", 1.0),
            tolerance=data.get("tolerance", 0.5),
            max_iterations=data.get("max_iterations", 20),
        )
