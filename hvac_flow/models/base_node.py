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
    """

    NODE_TYPE: str = ""
    DISPLAY_NAME: str = ""

    def __init__(self, name: str = ""):
        self.id: str = str(uuid.uuid4())
        self.name: str = name or self.DISPLAY_NAME
        self.ports: Dict[str, Port] = {}
        self.parameters: Dict[str, Any] = {}
        self.results: Dict[str, Any] = {}
        self.position: tuple = (0.0, 0.0)

        self._init_ports()
        self._init_parameters()

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
        return {
            "type": self.NODE_TYPE,
            "id": self.id,
            "name": self.name,
            "position": list(self.position),
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BaseNode":
        """Deserialize a node from a dict."""
        node = cls(name=data.get("name", ""))
        node.id = data["id"]
        node.position = tuple(data.get("position", (0, 0)))
        node.parameters.update(data.get("parameters", {}))
        return node
