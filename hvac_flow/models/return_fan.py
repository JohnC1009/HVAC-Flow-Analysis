"""Return / exhaust fan node — same thermodynamics as supply fan, for return or exhaust paths."""

from hvac_flow.engine.constants import CP_AIR_IP, HP_TO_BTUH, FAN_CONSTANT_IP
from hvac_flow.models.base_node import BaseNode, Port


class ReturnFanNode(BaseNode):
    NODE_TYPE = "return_fan"
    DISPLAY_NAME = "Return / Exhaust Fan"

    def _init_ports(self):
        self.ports["inlet"] = Port(name="inlet", direction="inlet")
        self.ports["outlet"] = Port(name="outlet", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "input_mode": "bhp",         # "bhp", "temp_rise", or "tsp"
            "bhp": 7.5,
            "motor_efficiency": 0.90,
            "fan_efficiency": 0.65,
            "temp_rise": 1.0,
            "total_static_pressure_iw": 2.0,
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

        cfm = mass_flow * entering.specific_volume
        mode = self.parameters["input_mode"]

        if mode == "bhp":
            bhp = self.parameters["bhp"]
            eff = self.parameters["motor_efficiency"]
            if eff <= 0:
                raise ValueError(
                    f"[{self.name}] Motor efficiency must be > 0 "
                    f"(got {eff})."
                )
            heat_btuh = bhp * HP_TO_BTUH / eff
            temp_rise = heat_btuh / (mass_flow * 60 * CP_AIR_IP)
        elif mode == "tsp":
            tsp = self.parameters["total_static_pressure_iw"]
            fan_eff = self.parameters["fan_efficiency"]
            motor_eff = self.parameters["motor_efficiency"]
            if fan_eff <= 0:
                raise ValueError(
                    f"[{self.name}] Fan efficiency must be > 0 "
                    f"(got {fan_eff})."
                )
            if motor_eff <= 0:
                raise ValueError(
                    f"[{self.name}] Motor efficiency must be > 0 "
                    f"(got {motor_eff})."
                )
            bhp = cfm * tsp / (FAN_CONSTANT_IP * fan_eff)
            heat_btuh = bhp * HP_TO_BTUH / motor_eff
            temp_rise = heat_btuh / (mass_flow * 60 * CP_AIR_IP)
        else:
            temp_rise = self.parameters["temp_rise"]
            heat_btuh = mass_flow * 60 * CP_AIR_IP * temp_rise
            bhp = heat_btuh * self.parameters["motor_efficiency"] / HP_TO_BTUH

        new_db = entering.dry_bulb + temp_rise
        leaving = calc.from_db_w(new_db, entering.humidity_ratio,
                                 label=f"{self.name} Out")

        leaving_cfm = mass_flow * leaving.specific_volume

        self.ports["outlet"].air_state = leaving
        self.ports["outlet"].mass_flow = mass_flow
        self.results = {
            "outlet_state": leaving,
            "temp_rise_f": temp_rise,
            "fan_heat_btuh": heat_btuh,
            "bhp": bhp,
            "entering_cfm": cfm,
            "leaving_cfm": leaving_cfm,
            "total_static_pressure_iw": self.parameters["total_static_pressure_iw"],
        }

    def get_param_definitions(self):
        return [
            {"name": "input_mode", "type": "choice",
             "choices": ["bhp", "temp_rise", "tsp"],
             "tooltip": "Specify fan heat via BHP, temperature rise, or total static pressure"},
            {"name": "bhp", "type": "float", "min": 0, "max": 500,
             "unit": "HP", "tooltip": "Brake horsepower"},
            {"name": "motor_efficiency", "type": "float", "min": 0.5,
             "max": 1.0, "unit": "fraction", "tooltip": "Motor efficiency"},
            {"name": "fan_efficiency", "type": "float", "min": 0.3,
             "max": 1.0, "unit": "fraction",
             "tooltip": "Fan total efficiency (used in TSP mode)"},
            {"name": "temp_rise", "type": "float", "min": 0, "max": 20,
             "unit": "°F", "tooltip": "Direct temperature rise"},
            {"name": "total_static_pressure_iw", "type": "float", "min": 0,
             "max": 20.0, "unit": "inWG",
             "tooltip": "Total static pressure the fan must deliver"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "fan_heat_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum fan heat dissipation (leave 0 for no limit)"},
        ]
