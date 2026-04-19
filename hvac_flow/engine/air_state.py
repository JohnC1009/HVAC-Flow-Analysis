"""Immutable representation of a moist air state point."""

from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class AirState:
    """Fully resolved psychrometric state of moist air.

    All properties are always populated — no partial states.
    Immutable: each equipment node produces a new AirState.
    """
    dry_bulb: float          # °F [IP] or °C [SI]
    humidity_ratio: float    # lb_w/lb_da [IP] or kg_w/kg_da [SI]
    relative_humidity: float # 0.0 to 1.0
    wet_bulb: float          # °F [IP] or °C [SI]
    dew_point: float         # °F [IP] or °C [SI]
    enthalpy: float          # Btu/lb_da [IP] or kJ/kg_da [SI]
    specific_volume: float   # ft^3/lb_da [IP] or m^3/kg_da [SI]
    pressure: float          # psi [IP] or Pa [SI]
    label: Optional[str] = None

    def with_label(self, label: str) -> "AirState":
        """Return a copy with a new label."""
        return replace(self, label=label)

    def summary_ip(self) -> str:
        """Human-readable summary in IP units."""
        return (
            f"DB: {self.dry_bulb:.1f}°F  "
            f"WB: {self.wet_bulb:.1f}°F  "
            f"RH: {self.relative_humidity * 100:.1f}%  "
            f"W: {self.humidity_ratio:.4f} lb/lb  "
            f"h: {self.enthalpy:.2f} Btu/lb  "
            f"DP: {self.dew_point:.1f}°F"
        )

    def summary_si(self) -> str:
        """Human-readable summary in SI units."""
        return (
            f"DB: {self.dry_bulb:.1f}°C  "
            f"WB: {self.wet_bulb:.1f}°C  "
            f"RH: {self.relative_humidity * 100:.1f}%  "
            f"W: {self.humidity_ratio:.4f} kg/kg  "
            f"h: {self.enthalpy:.2f} kJ/kg  "
            f"DP: {self.dew_point:.1f}°C"
        )
