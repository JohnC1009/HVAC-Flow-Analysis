"""Hot water coil node - air-side coil with hot water."""

from typing import Any, Dict, List

from hvac_flow.engine.water_state import WaterState
from hvac_flow.models.base_node import BaseNode, Port
from hvac_flow.exceptions import ParameterError


class HotWaterCoilNode(BaseNode):
    """Hot water heating coil with both air and water sides.
    
    Models a finned-tube coil where hot water transfers heat to air.
    """
    NODE_TYPE = "hot_water_coil"
    DISPLAY_NAME = "Hot Water Coil"

    def _init_ports(self) -> None:
        self.ports["air_inlet"] = Port(name="air_inlet", direction="inlet")
        self.ports["air_outlet"] = Port(name="air_outlet", direction="outlet")
        self.ports["water_inlet"] = Port(name="water_inlet", direction="inlet")
        self.ports["water_outlet"] = Port(name="water_outlet", direction="outlet")

    def _init_parameters(self) -> None:
        self.parameters = {
            "leaving_db": 105.0,
            "entering_water_temp": 180.0,
            "water_flow_gpm": 50.0,
            "water_pressure_drop_ft": 8.0,
        }

    def _init_boundary_conditions(self) -> None:
        self.boundary_conditions = {
            "sensible_load_btuh": None,
            "water_flow_max_gpm": None,
        }

    def compute(self, calc) -> None:
        air_inlet = self.ports["air_inlet"]
        entering_air = air_inlet.air_state
        if entering_air is None:
            raise ParameterError(
                f"[{self.name}] Air inlet state not available",
                node_id=self.id, node_name=self.name
            )
        
        air_mass_flow = air_inlet.mass_flow
        if not air_mass_flow or air_mass_flow <= 0:
            raise ParameterError(
                f"[{self.name}] Air mass flow is zero",
                node_id=self.id, node_name=self.name
            )

        ldb = self.parameters["leaving_db"]
        if ldb <= entering_air.dry_bulb:
            raise ParameterError(
                f"[{self.name}] Leaving DB must be > entering DB",
                node_id=self.id, node_name=self.name
            )

        leaving_air = calc.from_db_w(
            ldb, entering_air.humidity_ratio,
            label=f"{self.name} Air Out"
        )

        sensible_load = air_mass_flow * (leaving_air.enthalpy - entering_air.enthalpy) * 60

        # Water side
        entering_water_temp = self.parameters["entering_water_temp"]
        water_flow_gpm = self.parameters["water_flow_gpm"]
        water_mass_flow = water_flow_gpm * 8.34
        water_temp_drop = sensible_load / (water_mass_flow * 1.0 * 60)
        leaving_water_temp = entering_water_temp - water_temp_drop

        entering_water = WaterState(
            temperature=entering_water_temp,
            flow_rate=water_flow_gpm,
            pressure=self.parameters["water_pressure_drop_ft"] * 0.433,
            label=f"{self.name} Water In"
        )
        leaving_water = WaterState(
            temperature=leaving_water_temp,
            flow_rate=water_flow_gpm,
            pressure=0,
            label=f"{self.name} Water Out"
        )

        self.ports["air_outlet"].air_state = leaving_air
        self.ports["air_outlet"].mass_flow = air_mass_flow
        
        self.results = {
            "air_outlet_state": leaving_air,
            "sensible_load_btuh": sensible_load,
            "entering_water": entering_water,
            "leaving_water": leaving_water,
            "water_temp_drop_f": water_temp_drop,
            "water_flow_gpm": water_flow_gpm,
        }

    def get_param_definitions(self) -> List[Dict[str, Any]]:
        return [
            {"name": "leaving_db", "type": "float", "min": 50, "max": 200,
             "unit": "°F", "tooltip": "Leaving air dry-bulb"},
            {"name": "entering_water_temp", "type": "float", "min": 100, "max": 250,
             "unit": "°F", "tooltip": "Entering hot water temperature"},
            {"name": "water_flow_gpm", "type": "float", "min": 1, "max": 5000,
             "unit": "gpm", "tooltip": "Hot water flow rate"},
            {"name": "water_pressure_drop_ft", "type": "float", "min": 0, "max": 100,
             "unit": "ft", "tooltip": "Water-side pressure drop"},
        ]

    def get_boundary_definitions(self) -> List[Dict[str, Any]]:
        return [
            {"name": "sensible_load_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum heating capacity"},
            {"name": "water_flow_max_gpm", "type": "float",
             "min": 0, "max": 5000, "unit": "gpm",
             "tooltip": "Maximum water flow"},
        ]
