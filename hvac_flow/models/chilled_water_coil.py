"""Chilled water coil node - air-side coil with chilled water."""

from typing import Any, Dict, List, Optional

from hvac_flow.engine.constants import CP_AIR_IP
from hvac_flow.engine.water_state import WaterState
from hvac_flow.models.base_node import BaseNode, Port
from hvac_flow.exceptions import ParameterError


class ChilledWaterCoilNode(BaseNode):
    """Chilled water cooling coil with both air and water sides.
    
    Models a finned-tube coil where chilled water absorbs heat from air.
    Can operate in sensible-only or sensible+latent mode.
    """
    NODE_TYPE = "chilled_water_coil"
    DISPLAY_NAME = "Chilled Water Coil"

    def _init_ports(self) -> None:
        # Air side
        self.ports["air_inlet"] = Port(name="air_inlet", direction="inlet")
        self.ports["air_outlet"] = Port(name="air_outlet", direction="outlet")
        # Water side
        self.ports["water_inlet"] = Port(name="water_inlet", direction="inlet")
        self.ports["water_outlet"] = Port(name="water_outlet", direction="outlet")

    def _init_parameters(self) -> None:
        self.parameters = {
            # Air side
            "leaving_db": 55.0,        # Leaving dry-bulb temp
            "leaving_mode": "rh",       # "rh" or "w"
            "leaving_rh": 0.90,        # Leaving relative humidity
            "leaving_w": 0.008,        # Leaving humidity ratio
            "bypass_factor": 0.05,     # Coil bypass factor
            # Water side
            "entering_water_temp": 44.0,  # Entering chilled water temp
            "water_flow_gpm": 100.0,      # Water flow rate
            "water_pressure_drop_ft": 10.0,  # Pressure drop in feet of water
        }

    def _init_boundary_conditions(self) -> None:
        self.boundary_conditions = {
            "total_load_btuh": None,
            "sensible_load_btuh": None,
            "water_flow_max_gpm": None,
            "water_dp_max_ft": None,
        }

    def compute(self, calc) -> None:
        # Get air inlet state
        air_inlet = self.ports["air_inlet"]
        entering_air = air_inlet.air_state
        if entering_air is None:
            raise ParameterError(
                f"[{self.name}] Air inlet state is not available",
                node_id=self.id, node_name=self.name
            )
        
        air_mass_flow = air_inlet.mass_flow
        if not air_mass_flow or air_mass_flow <= 0:
            raise ParameterError(
                f"[{self.name}] Air mass flow is zero or missing",
                node_id=self.id, node_name=self.name
            )

        # Calculate leaving air state
        ldb = self.parameters["leaving_db"]
        if ldb >= entering_air.dry_bulb:
            raise ParameterError(
                f"[{self.name}] Leaving DB ({ldb:.1f}°F) >= entering DB "
                f"({entering_air.dry_bulb:.1f}°F)",
                node_id=self.id, node_name=self.name
            )

        if self.parameters["leaving_mode"] == "rh":
            leaving_air = calc.from_db_rh(
                ldb, self.parameters["leaving_rh"],
                label=f"{self.name} Air Out"
            )
        else:
            leaving_air = calc.from_db_w(
                ldb, self.parameters["leaving_w"],
                label=f"{self.name} Air Out"
            )

        # Calculate loads
        delta_h_total = entering_air.enthalpy - leaving_air.enthalpy
        delta_h_sensible = (entering_air.dry_bulb - leaving_air.dry_bulb) * CP_AIR_IP
        total_load = air_mass_flow * delta_h_total * 60
        sensible_load = air_mass_flow * delta_h_sensible * 60
        latent_load = total_load - sensible_load

        # Calculate water side
        entering_water_temp = self.parameters["entering_water_temp"]
        water_flow_gpm = self.parameters["water_flow_gpm"]
        
        # Q = m_dot * cp * delta_t
        # delta_t = Q / (m_dot * cp)
        water_mass_flow_lb_min = water_flow_gpm * 8.34  # lb/min
        water_cp = 1.0  # Btu/(lb·°F)
        water_temp_rise = total_load / (water_mass_flow_lb_min * water_cp * 60)
        leaving_water_temp = entering_water_temp + water_temp_rise

        # Create water states
        entering_water = WaterState(
            temperature=entering_water_temp,
            flow_rate=water_flow_gpm,
            pressure=self.parameters.get("water_pressure_drop_ft", 0) * 0.433,
            label=f"{self.name} Water In"
        )
        leaving_water = WaterState(
            temperature=leaving_water_temp,
            flow_rate=water_flow_gpm,
            pressure=0,  # After coil
            label=f"{self.name} Water Out"
        )

        # Set outputs
        self.ports["air_outlet"].air_state = leaving_air
        self.ports["air_outlet"].mass_flow = air_mass_flow
        # Store water states in results (ports don't have water_state attribute yet)
        self.results = {
            # Air side
            "air_outlet_state": leaving_air,
            "total_load_btuh": total_load,
            "sensible_load_btuh": sensible_load,
            "latent_load_btuh": latent_load,
            "total_load_tons": total_load / 12000.0,
            "shr": sensible_load / total_load if total_load else 0.0,
            # Water side
            "entering_water": entering_water,
            "leaving_water": leaving_water,
            "water_temp_rise_f": water_temp_rise,
            "water_flow_gpm": water_flow_gpm,
            "water_pressure_drop_ft": self.parameters["water_pressure_drop_ft"],
        }

    def get_param_definitions(self) -> List[Dict[str, Any]]:
        return [
            # Air side
            {"name": "leaving_db", "type": "float", "min": 35, "max": 100,
             "unit": "°F", "tooltip": "Leaving dry-bulb temperature"},
            {"name": "leaving_mode", "type": "choice",
             "choices": ["rh", "w"],
             "tooltip": "Specify leaving condition as RH or humidity ratio"},
            {"name": "leaving_rh", "type": "float", "min": 0.0, "max": 1.0,
             "unit": "fraction", "tooltip": "Leaving relative humidity"},
            {"name": "leaving_w", "type": "float", "min": 0.0, "max": 0.03,
             "unit": "lb/lb", "tooltip": "Leaving humidity ratio"},
            {"name": "bypass_factor", "type": "float", "min": 0.0, "max": 0.5,
             "unit": "fraction", "tooltip": "Coil bypass factor"},
            # Water side
            {"name": "entering_water_temp", "type": "float", "min": 32, "max": 60,
             "unit": "°F", "tooltip": "Entering chilled water temperature"},
            {"name": "water_flow_gpm", "type": "float", "min": 1, "max": 10000,
             "unit": "gpm", "tooltip": "Chilled water flow rate"},
            {"name": "water_pressure_drop_ft", "type": "float", "min": 0, "max": 100,
             "unit": "ft", "tooltip": "Water-side pressure drop"},
        ]

    def get_boundary_definitions(self) -> List[Dict[str, Any]]:
        return [
            {"name": "total_load_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum total cooling capacity"},
            {"name": "sensible_load_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum sensible cooling capacity"},
            {"name": "water_flow_max_gpm", "type": "float",
             "min": 0, "max": 10000, "unit": "gpm",
             "tooltip": "Maximum water flow rate"},
            {"name": "water_dp_max_ft", "type": "float",
             "min": 0, "max": 100, "unit": "ft",
             "tooltip": "Maximum pressure drop"},
        ]
