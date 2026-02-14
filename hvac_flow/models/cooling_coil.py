"""Cooling coil node — cools and/or dehumidifies air."""

from hvac_flow.engine.constants import CP_AIR_IP
from hvac_flow.models.base_node import BaseNode, Port


class CoolingCoilNode(BaseNode):
    NODE_TYPE = "cooling_coil"
    DISPLAY_NAME = "Cooling Coil"

    def _init_ports(self):
        self.ports["inlet"] = Port(name="inlet", direction="inlet")
        self.ports["outlet"] = Port(name="outlet", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "leaving_db": 55.0,
            "leaving_mode": "rh",
            "leaving_rh": 0.90,
            "leaving_w": 0.008,
            "pressure_drop_iw": 0.0,
        }

    def _init_boundary_conditions(self):
        self.boundary_conditions = {
            "total_load_btuh": None,     # Max total cooling capacity (Btu/hr)
            "sensible_load_btuh": None,  # Max sensible cooling capacity (Btu/hr)
        }

    def compute(self, calc) -> None:
        inlet = self.ports["inlet"]
        entering = inlet.air_state
        if entering is None:
            raise ValueError(
                f"[{self.name}] Inlet air state is not available — "
                f"check upstream connections."
            )
        mass_flow = inlet.mass_flow
        if not mass_flow or mass_flow <= 0:
            raise ValueError(
                f"[{self.name}] Inlet mass flow is zero or missing — "
                f"verify source node airflow."
            )
        ldb = self.parameters["leaving_db"]

        if ldb >= entering.dry_bulb:
            raise ValueError(
                f"[{self.name}] Leaving DB ({ldb:.1f}°F) >= entering DB "
                f"({entering.dry_bulb:.1f}°F) — cooling coil cannot heat."
            )

        if self.parameters["leaving_mode"] == "rh":
            leaving = calc.from_db_rh(ldb, self.parameters["leaving_rh"],
                                      label=f"{self.name} Out")
        else:
            leaving = calc.from_db_w(ldb, self.parameters["leaving_w"],
                                     label=f"{self.name} Out")

        delta_h_total = entering.enthalpy - leaving.enthalpy
        delta_h_sensible = (entering.dry_bulb - leaving.dry_bulb) * CP_AIR_IP
        total_load = mass_flow * delta_h_total * 60      # Btu/hr
        sensible_load = mass_flow * delta_h_sensible * 60
        latent_load = total_load - sensible_load

        entering_cfm = mass_flow * entering.specific_volume
        leaving_cfm = mass_flow * leaving.specific_volume

        self.ports["outlet"].air_state = leaving
        self.ports["outlet"].mass_flow = mass_flow
        self.results = {
            "outlet_state": leaving,
            "total_load_btuh": total_load,
            "sensible_load_btuh": sensible_load,
            "latent_load_btuh": latent_load,
            "total_load_tons": total_load / 12000.0,
            "shr": sensible_load / total_load if total_load else 0.0,
            "entering_cfm": entering_cfm,
            "leaving_cfm": leaving_cfm,
            "pressure_drop_iw": self.parameters["pressure_drop_iw"],
        }

    def get_param_definitions(self):
        return [
            {"name": "leaving_db", "type": "float", "min": 30, "max": 100,
             "unit": "°F", "tooltip": "Leaving dry-bulb temperature"},
            {"name": "leaving_mode", "type": "choice",
             "choices": ["rh", "w"],
             "tooltip": "Specify leaving condition as RH or humidity ratio"},
            {"name": "leaving_rh", "type": "float", "min": 0.0, "max": 1.0,
             "unit": "fraction", "tooltip": "Leaving relative humidity"},
            {"name": "leaving_w", "type": "float", "min": 0.0, "max": 0.03,
             "unit": "lb/lb", "tooltip": "Leaving humidity ratio"},
            {"name": "pressure_drop_iw", "type": "float", "min": 0.0,
             "max": 10.0, "unit": "inWG",
             "tooltip": "Air-side pressure drop across coil"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "total_load_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum total cooling capacity (leave 0 for no limit)"},
            {"name": "sensible_load_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum sensible cooling capacity (leave 0 for no limit)"},
        ]
