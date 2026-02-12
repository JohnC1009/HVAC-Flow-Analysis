"""Air sink node — terminates an airstream branch (exhaust/relief to outdoors)."""

from hvac_flow.models.base_node import BaseNode, Port


class AirSinkNode(BaseNode):
    NODE_TYPE = "air_sink"
    DISPLAY_NAME = "Air Sink / Exhaust"

    def _init_ports(self):
        self.ports["inlet"] = Port(name="inlet", direction="inlet")

    def _init_parameters(self):
        self.parameters = {}

    def compute(self, calc) -> None:
        entering = self.ports["inlet"].air_state
        mass_flow = self.ports["inlet"].mass_flow
        self.results = {
            "inlet_state": entering,
            "mass_flow": mass_flow,
        }

    def get_param_definitions(self):
        return []
