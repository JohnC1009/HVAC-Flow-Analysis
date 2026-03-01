"""Return / exhaust fan node — same thermodynamics as supply fan, for return or exhaust paths."""

from hvac_flow.models.fan import FanNode


class ReturnFanNode(FanNode):
    NODE_TYPE = "return_fan"
    DISPLAY_NAME = "Return / Exhaust Fan"

    def _init_parameters(self):
        self.parameters = {
            "input_mode": "bhp",
            "bhp": 7.5,
            "motor_efficiency": 0.90,
            "temp_rise": 1.0,
        }
