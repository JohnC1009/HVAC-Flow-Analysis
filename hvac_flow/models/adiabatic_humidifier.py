"""Adiabatic humidifier / direct evaporative cooler node.

Follows a constant wet-bulb (adiabatic saturation) process:
DB decreases, humidity ratio increases, enthalpy approximately constant.
"""

from hvac_flow.models.base_node import BaseNode, Port


class AdiabaticHumidifierNode(BaseNode):
    NODE_TYPE = "adiabatic_humidifier"
    DISPLAY_NAME = "Evap Cooler / Humidifier"

    def _init_ports(self):
        self.ports["inlet"] = Port(name="inlet", direction="inlet")
        self.ports["outlet"] = Port(name="outlet", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "saturation_efficiency": 0.85,
            "pressure_drop_iw": 0.0,
        }

    def _init_boundary_conditions(self):
        self.boundary_conditions = {
            "water_consumption_lb_hr": None,  # Max water supply (lb/hr)
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
        eff = self.parameters["saturation_efficiency"]

        # Saturation state at inlet wet-bulb temperature
        # At saturation: DB = WB, W = W_sat(WB)
        sat_db = entering.wet_bulb
        sat_w = calc.get_saturation_humidity_ratio(entering.wet_bulb)

        # Leaving condition along the constant-WB line
        leaving_db = entering.dry_bulb - eff * (entering.dry_bulb - sat_db)
        leaving_w = entering.humidity_ratio + eff * (sat_w - entering.humidity_ratio)

        leaving = calc.from_db_w(leaving_db, leaving_w,
                                 label=f"{self.name} Out")

        water_evaporated = (leaving_w - entering.humidity_ratio) * mass_flow * 60
        db_drop = entering.dry_bulb - leaving_db

        entering_cfm = mass_flow * entering.specific_volume
        leaving_cfm = mass_flow * leaving.specific_volume

        self.ports["outlet"].air_state = leaving
        self.ports["outlet"].mass_flow = mass_flow
        self.results = {
            "outlet_state": leaving,
            "water_consumption_lb_hr": water_evaporated,
            "db_drop_f": db_drop,
            "leaving_rh": leaving.relative_humidity,
            "entering_cfm": entering_cfm,
            "leaving_cfm": leaving_cfm,
            "pressure_drop_iw": self.parameters["pressure_drop_iw"],
        }

    def get_param_definitions(self):
        return [
            {"name": "saturation_efficiency", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Saturation efficiency (0-1). Typical wetted media: 0.80-0.95"},
            {"name": "pressure_drop_iw", "type": "float", "min": 0.0,
             "max": 10.0, "unit": "inWG",
             "tooltip": "Air-side pressure drop across humidifier media"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "water_consumption_lb_hr", "type": "float",
             "min": 0, "max": 1e6, "unit": "lb/hr",
             "tooltip": "Maximum water supply rate (leave 0 for no limit)"},
        ]
