"""Pump node for hydronic systems."""

from typing import Any, Dict, List, Optional

from hvac_flow.engine.water_state import WaterState
from hvac_flow.models.base_node import BaseNode, Port
from hvac_flow.exceptions import ParameterError


class PumpNode(BaseNode):
    """Centrifugal pump for water or glycol systems.
    
    Models pump power consumption and adds heat to the fluid.
    Supports constant speed and variable speed operation.
    """
    NODE_TYPE = "pump"
    DISPLAY_NAME = "Pump"

    def _init_ports(self) -> None:
        self.ports["inlet"] = Port(name="inlet", direction="inlet")
        self.ports["outlet"] = Port(name="outlet", direction="outlet")

    def _init_parameters(self) -> None:
        self.parameters = {
            "flow_rate_gpm": 100.0,
            "head_ft": 40.0,
            "efficiency": 0.75,
            "motor_efficiency": 0.90,
            "speed_percent": 100.0,  # For VFD simulation
            "variable_speed": False,
        }

    def _init_boundary_conditions(self) -> None:
        self.boundary_conditions = {
            "bhp_max": None,
            "flow_max_gpm": None,
        }

    def compute(self, calc) -> None:
        inlet = self.ports["inlet"]
        entering = inlet.air_state if hasattr(inlet, 'air_state') else None
        
        # For water pumps, we work with WaterState
        entering_water: Optional[WaterState] = None
        if hasattr(inlet, 'water_state'):
            entering_water = inlet.water_state
        
        # If no inlet state provided, create default
        if entering_water is None:
            entering_water = WaterState(
                temperature=44.0,
                flow_rate=self.parameters["flow_rate_gpm"],
                pressure=20.0
            )

        flow_gpm = self.parameters["flow_rate_gpm"]
        head_ft = self.parameters["head_ft"]
        pump_eff = self.parameters["efficiency"]
        motor_eff = self.parameters["motor_efficiency"]
        speed = self.parameters["speed_percent"] / 100.0

        if pump_eff <= 0 or motor_eff <= 0:
            raise ParameterError(
                f"[{self.name}] Efficiencies must be > 0",
                node_id=self.id, node_name=self.name
            )

        # Affinity laws for variable speed
        if self.parameters["variable_speed"] and speed < 1.0:
            flow_gpm = flow_gpm * speed
            head_ft = head_ft * (speed ** 2)

        # Brake horsepower: BHP = (GPM × Head) / (3960 × Efficiency)
        bhp = (flow_gmp * head_ft) / (3960 * pump_eff)
        
        # Motor power input
        motor_hp = bhp / motor_eff
        
        # Convert to kW for heat calculation
        motor_kw = motor_hp * 0.7457
        
        # Heat added to water (assume all inefficiency becomes heat)
        heat_to_water_kw = motor_kw * (1 - motor_eff)
        heat_to_water_btuh = heat_to_water_kw * 3412
        
        # Temperature rise
        water_mass_lb_min = flow_gpm * 8.34
        temp_rise = heat_to_water_btuh / (water_mass_lb_min * 60 * 1.0)

        leaving_water = WaterState(
            temperature=entering_water.temperature + temp_rise,
            flow_rate=flow_gpm,
            pressure=entering_water.pressure + (head_ft * 0.433),
            glycol_percentage=entering_water.glycol_percentage,
            label=f"{self.name} Out"
        )

        self.results = {
            "entering_water": entering_water,
            "leaving_water": leaving_water,
            "bhp": bhp,
            "motor_hp": motor_hp,
            "motor_kw": motor_kw,
            "heat_to_water_btuh": heat_to_water_btuh,
            "temp_rise_f": temp_rise,
            "flow_gpm": flow_gpm,
            "head_ft": head_ft,
        }

    def get_param_definitions(self) -> List[Dict[str, Any]]:
        return [
            {"name": "flow_rate_gpm", "type": "float", "min": 1, "max": 100000,
             "unit": "gpm", "tooltip": "Design flow rate"},
            {"name": "head_ft", "type": "float", "min": 1, "max": 500,
             "unit": "ft", "tooltip": "Pump head"},
            {"name": "efficiency", "type": "float", "min": 0.1, "max": 1.0,
             "unit": "fraction", "tooltip": "Pump hydraulic efficiency"},
            {"name": "motor_efficiency", "type": "float", "min": 0.5, "max": 1.0,
             "unit": "fraction", "tooltip": "Motor efficiency"},
            {"name": "variable_speed", "type": "choice",
             "choices": [True, False],
             "tooltip": "Variable frequency drive"},
            {"name": "speed_percent", "type": "float", "min": 10, "max": 100,
             "unit": "%", "tooltip": "Current speed (for VFD)"},
        ]

    def get_boundary_definitions(self) -> List[Dict[str, Any]]:
        return [
            {"name": "bhp_max", "type": "float",
             "min": 0, "max": 10000, "unit": "HP",
             "tooltip": "Maximum brake horsepower"},
            {"name": "flow_max_gpm", "type": "float",
             "min": 0, "max": 100000, "unit": "gpm",
             "tooltip": "Maximum flow rate"},
        ]
