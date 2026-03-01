"""Source node — defines an air state entering the system (OA, return air, etc.)."""

from hvac_flow.models.base_node import BaseNode, Port


class SourceNode(BaseNode):
    NODE_TYPE = "source"
    DISPLAY_NAME = "Air Source"

    def _init_ports(self):
        self.ports["outlet"] = Port(name="outlet", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "input_mode": "db_rh",
            "dry_bulb": 95.0,
            "relative_humidity": 0.50,
            "wet_bulb": 78.0,
            "dew_point": 68.0,
            "airflow_cfm": 10000.0,
        }

    def compute(self, calc) -> None:
        mode = self.parameters["input_mode"]
        db = self.parameters["dry_bulb"]
        cfm = self.parameters["airflow_cfm"]
        if cfm <= 0:
            raise ValueError(
                f"[{self.name}] Airflow must be > 0 CFM (got {cfm})."
            )

        if mode == "db_rh":
            rh = self.parameters["relative_humidity"]
            if not (0.0 <= rh <= 1.0):
                raise ValueError(
                    f"[{self.name}] Relative humidity must be 0-1 "
                    f"(got {rh})."
                )
            state = calc.from_db_rh(db, rh, label=self.name)
        elif mode == "db_wb":
            wb = self.parameters["wet_bulb"]
            if wb > db:
                raise ValueError(
                    f"[{self.name}] Wet-bulb ({wb:.1f}°F) cannot exceed "
                    f"dry-bulb ({db:.1f}°F)."
                )
            state = calc.from_db_wb(db, wb, label=self.name)
        elif mode == "db_dp":
            dp = self.parameters["dew_point"]
            if dp > db:
                raise ValueError(
                    f"[{self.name}] Dew-point ({dp:.1f}°F) cannot exceed "
                    f"dry-bulb ({db:.1f}°F)."
                )
            state = calc.from_db_dp(db, dp, label=self.name)
        else:
            raise ValueError(
                f"[{self.name}] Unknown input_mode '{mode}' — "
                f"expected one of: db_rh, db_wb, db_dp."
            )

        self.ports["outlet"].air_state = state
        density = calc.get_moist_air_density(state)
        self.ports["outlet"].mass_flow = cfm * density
        self.results = {
            "outlet_state": state,
            "mass_flow_lb_min": self.ports["outlet"].mass_flow,
        }

    def get_param_definitions(self):
        return [
            {"name": "input_mode", "type": "choice",
             "choices": ["db_rh", "db_wb", "db_dp"],
             "tooltip": "Input property pair"},
            {"name": "dry_bulb", "type": "float", "min": -60, "max": 160,
             "unit": "°F", "tooltip": "Dry-bulb temperature"},
            {"name": "relative_humidity", "type": "float", "min": 0.0,
             "max": 1.0, "unit": "fraction",
             "tooltip": "Relative humidity (0-1)"},
            {"name": "wet_bulb", "type": "float", "min": -60, "max": 160,
             "unit": "°F", "tooltip": "Wet-bulb temperature"},
            {"name": "dew_point", "type": "float", "min": -60, "max": 160,
             "unit": "°F", "tooltip": "Dew-point temperature"},
            {"name": "airflow_cfm", "type": "float", "min": 0, "max": 1e7,
             "unit": "CFM", "tooltip": "Volumetric airflow"},
        ]
