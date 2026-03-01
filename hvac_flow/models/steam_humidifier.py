"""Steam humidifier node — isothermal humidification (nearly constant DB)."""

from hvac_flow.models.base_node import BaseNode, Port


class SteamHumidifierNode(BaseNode):
    NODE_TYPE = "steam_humidifier"
    DISPLAY_NAME = "Steam Humidifier"

    def _init_ports(self):
        self.ports["inlet"] = Port(name="inlet", direction="inlet")
        self.ports["outlet"] = Port(name="outlet", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "control_mode": "target_rh",  # "target_rh", "target_w", "steam_rate"
            "target_rh": 0.40,
            "target_w": 0.006,
            "steam_rate_lb_hr": 50.0,
        }

    def _init_boundary_conditions(self):
        self.boundary_conditions = {
            "steam_consumption_lb_hr": None,  # Max steam generation (lb/hr)
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
        mode = self.parameters["control_mode"]

        if mode == "target_rh":
            target_w = calc.get_humidity_ratio_from_rh(
                entering.dry_bulb, self.parameters["target_rh"]
            )
        elif mode == "target_w":
            target_w = self.parameters["target_w"]
        else:
            steam_mass_per_min = self.parameters["steam_rate_lb_hr"] / 60.0
            delta_w = steam_mass_per_min / mass_flow
            target_w = entering.humidity_ratio + delta_w

        # Isothermal: DB stays essentially constant
        leaving = calc.from_db_w(entering.dry_bulb, target_w,
                                 label=f"{self.name} Out")

        steam_consumed = (target_w - entering.humidity_ratio) * mass_flow * 60
        steam_consumed = max(steam_consumed, 0.0)

        self.ports["outlet"].air_state = leaving
        self.ports["outlet"].mass_flow = mass_flow
        self.results = {
            "outlet_state": leaving,
            "steam_consumption_lb_hr": steam_consumed,
            "delta_w": target_w - entering.humidity_ratio,
        }

    def get_param_definitions(self):
        return [
            {"name": "control_mode", "type": "choice",
             "choices": ["target_rh", "target_w", "steam_rate"],
             "tooltip": "Humidifier control mode"},
            {"name": "target_rh", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Target leaving relative humidity"},
            {"name": "target_w", "type": "float",
             "min": 0.0, "max": 0.03, "unit": "lb/lb",
             "tooltip": "Target leaving humidity ratio"},
            {"name": "steam_rate_lb_hr", "type": "float",
             "min": 0, "max": 10000, "unit": "lb/hr",
             "tooltip": "Fixed steam injection rate"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "steam_consumption_lb_hr", "type": "float",
             "min": 0, "max": 1e6, "unit": "lb/hr",
             "tooltip": "Maximum steam generation capacity (leave 0 for no limit)"},
        ]
