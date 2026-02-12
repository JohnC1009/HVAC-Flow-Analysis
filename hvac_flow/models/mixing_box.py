"""Mixing box node — blends two airstreams by mass-flow fraction."""

from hvac_flow.models.base_node import BaseNode, Port


class MixingBoxNode(BaseNode):
    NODE_TYPE = "mixing_box"
    DISPLAY_NAME = "Mixing Box"

    def _init_ports(self):
        self.ports["primary"] = Port(name="primary", direction="inlet")
        self.ports["secondary"] = Port(name="secondary", direction="inlet")
        self.ports["mixed"] = Port(name="mixed", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "primary_fraction": 0.20,
        }

    def compute(self, calc) -> None:
        p = self.ports["primary"]
        s = self.ports["secondary"]
        f = self.parameters["primary_fraction"]

        mixed_w = f * p.air_state.humidity_ratio + (1 - f) * s.air_state.humidity_ratio
        mixed_h = f * p.air_state.enthalpy + (1 - f) * s.air_state.enthalpy

        mixed_state = calc.from_enthalpy_w(mixed_h, mixed_w,
                                           label=f"{self.name} Out")

        total_mass = (p.mass_flow or 0) + (s.mass_flow or 0)

        self.ports["mixed"].air_state = mixed_state
        self.ports["mixed"].mass_flow = total_mass
        self.results = {
            "mixed_state": mixed_state,
            "total_mass_flow": total_mass,
            "mixed_db": mixed_state.dry_bulb,
            "mixed_rh": mixed_state.relative_humidity,
        }

    def get_param_definitions(self):
        return [
            {"name": "primary_fraction", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Fraction of total flow from primary inlet (e.g. OA fraction)"},
        ]
