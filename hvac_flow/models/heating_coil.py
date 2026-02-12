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

    def compute(self, calc) -> None:
        entering = self.ports["inlet"].air_state
        mass_flow = self.ports["inlet"].mass_flow
        ldb = self.parameters["leaving_db"]

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
