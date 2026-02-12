"""Fan node — adds sensible heat from motor/drive energy."""

from hvac_flow.engine.constants import CP_AIR_IP, HP_TO_BTUH
from hvac_flow.models.base_node import BaseNode, Port


class FanNode(BaseNode):
    NODE_TYPE = "fan"
    DISPLAY_NAME = "Supply Fan"

    def _init_ports(self):
        self.ports["inlet"] = Port(name="inlet", direction="inlet")
        self.ports["outlet"] = Port(name="outlet", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "input_mode": "bhp",
            "bhp": 15.0,
            "motor_efficiency": 0.90,
            "temp_rise": 2.0,
        }

    def _init_boundary_conditions(self):
        self.boundary_conditions = {
            "fan_heat_btuh": None,  # Max fan heat (Btu/hr)
        }

    def compute(self, calc) -> None:
        entering = self.ports["inlet"].air_state
        if entering is None:
            raise ValueError(
                f"[{self.name}] Inlet air state is not available — "
                f"check upstream connections."
            )
        mass_flow = self.ports["inlet"].mass_flow
        if not mass_flow or mass_flow <= 0:
            raise ValueError(
                f"[{self.name}] Inlet mass flow is zero or missing — "
                f"verify source node airflow."
            )

        if self.parameters["input_mode"] == "bhp":
            bhp = self.parameters["bhp"]
            eff = self.parameters["motor_efficiency"]
            if eff <= 0:
                raise ValueError(
                    f"[{self.name}] Motor efficiency must be > 0 "
                    f"(got {eff})."
                )
            heat_btuh = bhp * HP_TO_BTUH / eff
            temp_rise = heat_btuh / (mass_flow * 60 * CP_AIR_IP)
        else:
            temp_rise = self.parameters["temp_rise"]
            heat_btuh = mass_flow * 60 * CP_AIR_IP * temp_rise

        new_db = entering.dry_bulb + temp_rise
        leaving = calc.from_db_w(new_db, entering.humidity_ratio,
                                 label=f"{self.name} Out")

        self.ports["outlet"].air_state = leaving
        self.ports["outlet"].mass_flow = mass_flow
        self.results = {
            "outlet_state": leaving,
            "temp_rise_f": temp_rise,
            "fan_heat_btuh": heat_btuh,
        }

    def get_param_definitions(self):
        return [
            {"name": "input_mode", "type": "choice",
             "choices": ["bhp", "temp_rise"],
             "tooltip": "Specify fan heat via BHP or direct temperature rise"},
            {"name": "bhp", "type": "float", "min": 0, "max": 500,
             "unit": "HP", "tooltip": "Brake horsepower"},
            {"name": "motor_efficiency", "type": "float", "min": 0.5,
             "max": 1.0, "unit": "fraction", "tooltip": "Motor efficiency"},
            {"name": "temp_rise", "type": "float", "min": 0, "max": 20,
             "unit": "°F", "tooltip": "Direct temperature rise"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "fan_heat_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum fan heat dissipation (leave 0 for no limit)"},
        ]
