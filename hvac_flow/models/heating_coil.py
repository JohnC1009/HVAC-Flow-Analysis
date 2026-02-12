"""Heating coil node — sensible heating only (humidity ratio constant)."""

from hvac_flow.models.base_node import BaseNode, Port


class HeatingCoilNode(BaseNode):
    NODE_TYPE = "heating_coil"
    DISPLAY_NAME = "Heating Coil"

    def _init_ports(self):
        self.ports["inlet"] = Port(name="inlet", direction="inlet")
        self.ports["outlet"] = Port(name="outlet", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "leaving_db": 105.0,
        }

    def _init_boundary_conditions(self):
        self.boundary_conditions = {
            "sensible_load_btuh": None,  # Max heating capacity (Btu/hr)
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
        ldb = self.parameters["leaving_db"]

        if ldb <= entering.dry_bulb:
            raise ValueError(
                f"[{self.name}] Leaving DB ({ldb:.1f}°F) <= entering DB "
                f"({entering.dry_bulb:.1f}°F) — heating coil cannot cool."
            )

        leaving = calc.from_db_w(ldb, entering.humidity_ratio,
                                 label=f"{self.name} Out")

        sensible_load = mass_flow * (leaving.enthalpy - entering.enthalpy) * 60

        self.ports["outlet"].air_state = leaving
        self.ports["outlet"].mass_flow = mass_flow
        self.results = {
            "outlet_state": leaving,
            "sensible_load_btuh": sensible_load,
        }

    def get_param_definitions(self):
        return [
            {"name": "leaving_db", "type": "float", "min": 30, "max": 200,
             "unit": "°F", "tooltip": "Leaving dry-bulb temperature"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "sensible_load_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum heating capacity (leave 0 for no limit)"},
        ]
