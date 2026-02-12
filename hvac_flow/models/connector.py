"""Connector model — represents ductwork between two equipment ports."""

import uuid
from dataclasses import dataclass, field

from hvac_flow.engine.constants import CP_AIR_IP


@dataclass
class Connector:
    """A duct segment connecting one node's outlet port to another's inlet port."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_node_id: str = ""
    source_port_name: str = ""
    target_node_id: str = ""
    target_port_name: str = ""

    # Optional duct heat gain/loss modelling
    model_duct_losses: bool = False
    duct_ua: float = 0.0       # Btu/(hr·°F) overall UA value
    ambient_temp: float = 85.0  # °F surrounding temperature

    def apply_duct_loss(self, state, mass_flow, calc):
        """Apply sensible heat gain/loss through the duct (humidity ratio constant).

        Returns a new AirState (or the original if not modelling losses).
        """
        if not self.model_duct_losses or self.duct_ua == 0.0:
            return state
        q = self.duct_ua * (self.ambient_temp - state.dry_bulb)
        dt = q / (mass_flow * 60 * CP_AIR_IP) if mass_flow else 0.0
        new_db = state.dry_bulb + dt
        return calc.from_db_w(new_db, state.humidity_ratio)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_node_id": self.source_node_id,
            "source_port_name": self.source_port_name,
            "target_node_id": self.target_node_id,
            "target_port_name": self.target_port_name,
            "model_duct_losses": self.model_duct_losses,
            "duct_ua": self.duct_ua,
            "ambient_temp": self.ambient_temp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Connector":
        return cls(
            id=data["id"],
            source_node_id=data["source_node_id"],
            source_port_name=data["source_port_name"],
            target_node_id=data["target_node_id"],
            target_port_name=data["target_port_name"],
            model_duct_losses=data.get("model_duct_losses", False),
            duct_ua=data.get("duct_ua", 0.0),
            ambient_temp=data.get("ambient_temp", 85.0),
        )
