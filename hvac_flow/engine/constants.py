"""Physical constants and unit system definitions for HVAC calculations."""

from enum import Enum


class UnitSystem(Enum):
    IP = "IP"  # Fahrenheit, lb, Btu, ft^3
    SI = "SI"  # Celsius, kg, kJ, m^3


# Standard atmospheric pressure at sea level
STD_ATM_PRESSURE_IP = 14.696  # psi
STD_ATM_PRESSURE_SI = 101325  # Pa

# Standard air density
STD_AIR_DENSITY_IP = 0.075  # lb_da / ft^3 (at 70F, 14.696 psi)
STD_AIR_DENSITY_SI = 1.204  # kg_da / m^3 (at 20C, 101325 Pa)

# Specific heat of dry air
CP_AIR_IP = 0.24   # Btu/(lb·°F)
CP_AIR_SI = 1.006  # kJ/(kg·°C)

# Latent heat of vaporization / adsorption (h_fg) at typical HVAC conditions
H_FG_IP = 1061.0  # Btu/lb_water

# Conversion: 1 HP = 2545 Btu/hr
HP_TO_BTUH = 2545.0

# Conversion: 1 ton refrigeration = 12000 Btu/hr
TON_TO_BTUH = 12000.0
