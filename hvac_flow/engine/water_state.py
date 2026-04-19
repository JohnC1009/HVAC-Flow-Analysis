"""Immutable representation of a water/fluid state point."""

from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class WaterState:
    """Fully resolved state of water or water-glycol mixture.

    Used for hydronic system modeling (chilled water, hot water, condenser water).
    Immutable: each equipment node produces a new WaterState.
    """
    temperature: float       # °F [IP] or °C [SI]
    flow_rate: float         # gpm [IP] or L/s [SI]
    pressure: float          # psi [IP] or kPa [SI]
    # For glycol mixtures
    glycol_percentage: float = 0.0  # 0.0 = pure water, 0.5 = 50% glycol
    
    # Computed properties (at standard conditions if not specified)
    density: Optional[float] = None      # lb/ft³ [IP] or kg/m³ [SI]
    specific_heat: Optional[float] = None  # Btu/(lb·°F) [IP] or kJ/(kg·°C) [SI]
    
    label: Optional[str] = None

    def with_label(self, label: str) -> "WaterState":
        """Return a copy with a new label."""
        return replace(self, label=label)

    def get_density(self) -> float:
        """Return density, using stored value or calculating from temperature."""
        if self.density is not None:
            return self.density
        # Approximate density of water
        if self.glycol_percentage > 0:
            # Ethylene glycol mixture (simplified)
            return 62.4 * (1 - 0.1 * self.glycol_percentage)
        return 62.4  # lb/ft³ at 60°F

    def get_specific_heat(self) -> float:
        """Return specific heat, using stored value or estimating from mixture."""
        if self.specific_heat is not None:
            return self.specific_heat
        if self.glycol_percentage > 0:
            # Ethylene glycol: ~0.65 Btu/(lb·°F) vs water 1.0
            return 1.0 - (0.35 * self.glycol_percentage)
        return 1.0  # Btu/(lb·°F) for water

    def get_mass_flow(self) -> float:
        """Calculate mass flow rate in lb/min [IP] or kg/s [SI]."""
        density = self.get_density()  # lb/ft³
        # gpm * 8.34 lb/gal * (1 ft³/7.48 gal) = lb/min
        return self.flow_rate * density / 7.48 * 7.48  # Simplified: gpm * 8.34 * (60/7.48)

    def calculate_heat_transfer(self, other: "WaterState") -> float:
        """Calculate heat transfer between this state and another (Btu/hr)."""
        mass_flow = self.get_mass_flow()  # lb/min
        cp = self.get_specific_heat()  # Btu/(lb·°F)
        delta_t = abs(self.temperature - other.temperature)
        # Q = m_dot * cp * delta_t * 60 min/hr
        return mass_flow * cp * delta_t * 60

    def summary_ip(self) -> str:
        """Human-readable summary in IP units."""
        glycol_str = f" ({self.glycol_percentage*100:.0f}% glycol)" if self.glycol_percentage > 0 else ""
        return (
            f"T: {self.temperature:.1f}°F{glycol_str}  "
            f"Flow: {self.flow_rate:.1f} gpm  "
            f"P: {self.pressure:.1f} psi"
        )
