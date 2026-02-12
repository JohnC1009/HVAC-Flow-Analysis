"""Duct split node — divides one airstream into two branches."""

from hvac_flow.models.base_node import BaseNode, Port


class DuctSplitNode(BaseNode):
    NODE_TYPE = "duct_split"
    DISPLAY_NAME = "Duct Split"

    def _init_ports(self):
        self.ports["inlet"] = Port(name="inlet", direction="inlet")
        self.ports["outlet_a"] = Port(name="outlet_a", direction="outlet")
        self.ports["outlet_b"] = Port(name="outlet_b", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "split_fraction": 0.50,
        }

    def compute(self, calc) -> None:
        entering = self.ports["inlet"].air_state
        mass_flow = self.ports["inlet"].mass_flow
        f = self.parameters["split_fraction"]

        state_a = entering.with_label(f"{self.name} A")
        state_b = entering.with_label(f"{self.name} B")

        self.ports["outlet_a"].air_state = state_a
        self.ports["outlet_a"].mass_flow = mass_flow * f
        self.ports["outlet_b"].air_state = state_b
        self.ports["outlet_b"].mass_flow = mass_flow * (1 - f)

        self.results = {
            "outlet_a_flow": mass_flow * f,
            "outlet_b_flow": mass_flow * (1 - f),
        }

    def get_param_definitions(self):
        return [
            {"name": "split_fraction", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Fraction of flow to outlet A (remainder to B)"},
        ]
