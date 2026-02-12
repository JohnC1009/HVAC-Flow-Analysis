"""Abstract base class for all equipment nodes in the flow graph."""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class Port:
    """An inlet or outlet connection point on a node."""
    name: str
    direction: str  # "inlet" or "outlet"
    air_state: Any = None  # AirState once resolved
    mass_flow: Optional[float] = None  # lb_da/min [IP] or kg_da/s [SI]
    connected_to: Optional[str] = None  # Connector ID


class BaseNode(ABC):
    """Abstract equipment node in the flow graph.

    Subclasses must implement _init_ports, _init_parameters, and compute.

    Boundary conditions (optional):
        Equipment nodes can define optional capacity limits in
        ``self.boundary_conditions``.  When boundary conditions are provided
        the solver compares the *required* capacity (computed during
        ``compute()``) against the limits and records warnings for any node
        whose required capacity exceeds its boundary.  When no boundary
        conditions are set the solver simply reports the required capacities
        in ``self.results``.
    """

    NODE_TYPE: str = ""
    DISPLAY_NAME: str = ""

    def __init__(self, name: str = ""):
        self.id: str = str(uuid.uuid4())
        self.name: str = name or self.DISPLAY_NAME
        self.ports: Dict[str, Port] = {}
        self.parameters: Dict[str, Any] = {}
        self.results: Dict[str, Any] = {}
        self.boundary_conditions: Dict[str, Any] = {}
        self.capacity_warnings: List[str] = []
        self.position: tuple = (0.0, 0.0)

        self._init_ports()
        self._init_parameters()
        self._init_boundary_conditions()

    @abstractmethod
    def _init_ports(self):
        """Create Port objects for this node type."""
        ...

    @abstractmethod
    def _init_parameters(self):
        """Define user-editable parameters with defaults."""
        ...

    @abstractmethod
    def compute(self, calc) -> None:
        """Compute outlet air state(s) from inlet state(s) and parameters.

        Args:
            calc: PsychroCalc instance for psychrometric lookups.
        """
        ...

    def _init_boundary_conditions(self):
        """Initialise default (empty) boundary conditions.

        Subclasses override to populate ``self.boundary_conditions`` with
        relevant capacity limits.  An empty dict means "no limits — report
        required capacities only".
        """
        pass

    def check_boundary_conditions(self) -> List[str]:
        """Compare computed results against boundary conditions.

        Returns a list of warning strings for any limit that is exceeded.
        If no boundary conditions are set the list is empty but
        ``self.results`` will still contain the required capacities for the
        user to review.
        """
        self.capacity_warnings.clear()
        if not self.boundary_conditions:
            return self.capacity_warnings

        for key, limit in self.boundary_conditions.items():
            if limit is None:
                continue
            required = self.results.get(key)
            if required is None:
                continue
            if abs(required) > abs(limit):
                self.capacity_warnings.append(
                    f"[{self.name}] {key.replace('_', ' ').title()}: "
                    f"required {required:,.1f} exceeds limit {limit:,.1f}"
                )
        return self.capacity_warnings

    def get_boundary_definitions(self) -> List[Dict[str, Any]]:
        """Return metadata for boundary-condition parameters.

        Same format as ``get_param_definitions``.  Subclasses override to
        expose editable capacity limits in the property panel.
        """
        return []

    @property
    def inlet_ports(self) -> List[Port]:
        return [p for p in self.ports.values() if p.direction == "inlet"]

    @property
    def outlet_ports(self) -> List[Port]:
        return [p for p in self.ports.values() if p.direction == "outlet"]

    def get_param_definitions(self) -> List[Dict[str, Any]]:
        """Return metadata describing each parameter for the property editor.

        Each entry: {name, type, default, min, max, unit, choices, tooltip}.
        Subclasses should override to provide rich metadata.
        """
        return []

    def to_dict(self) -> dict:
        """Serialize this node to a JSON-compatible dict."""
        d = {
            "type": self.NODE_TYPE,
            "id": self.id,
            "name": self.name,
            "position": list(self.position),
            "parameters": dict(self.parameters),
        }
        # Only persist boundary conditions if at least one has a non-None value
        if any(v is not None for v in self.boundary_conditions.values()):
            d["boundary_conditions"] = dict(self.boundary_conditions)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "BaseNode":
        """Deserialize a node from a dict."""
        node = cls(name=data.get("name", ""))
        node.id = data["id"]
        node.position = tuple(data.get("position", (0, 0)))
        node.parameters.update(data.get("parameters", {}))
        node.boundary_conditions.update(data.get("boundary_conditions", {}))
        return node
