"""Sensible heat recovery node — covers heat wheels, plate exchangers, and heat pipes.

Two-stream device that transfers sensible heat only (no moisture transfer).
Each stream moves horizontally on the psychrometric chart (constant W, changing DB).
"""

from hvac_flow.models.base_node import BaseNode, Port


class SensibleHeatRecoveryNode(BaseNode):
    NODE_TYPE = "sensible_hr"
    DISPLAY_NAME = "Sensible Heat Recovery"

    def _init_ports(self):
        self.ports["supply_in"] = Port(name="supply_in", direction="inlet")
        self.ports["supply_out"] = Port(name="supply_out", direction="outlet")
        self.ports["exhaust_in"] = Port(name="exhaust_in", direction="inlet")
        self.ports["exhaust_out"] = Port(name="exhaust_out", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "sensible_effectiveness": 0.65,
            "device_type": "plate_exchanger",  # informational label
        }

    def _init_boundary_conditions(self):
        self.boundary_conditions = {
            "sensible_recovery_btuh": None,  # Max recovery capacity (Btu/hr)
        }

    def compute(self, calc) -> None:
        s_in = self.ports["supply_in"].air_state
        e_in = self.ports["exhaust_in"].air_state
        if s_in is None:
            raise ValueError(
                f"[{self.name}] Supply inlet air state is not available — "
                f"check upstream connections on 'supply_in' port."
            )
        if e_in is None:
            raise ValueError(
                f"[{self.name}] Exhaust inlet air state is not available — "
                f"check upstream connections on 'exhaust_in' port."
            )
        eps = self.parameters["sensible_effectiveness"]

        # Supply side: DB changes, W unchanged
        supply_out_db = s_in.dry_bulb + eps * (e_in.dry_bulb - s_in.dry_bulb)
        supply_out = calc.from_db_w(supply_out_db, s_in.humidity_ratio,
                                    label=f"{self.name} Supply Out")

        # Exhaust side: energy balance, DB changes, W unchanged
        exhaust_out_db = e_in.dry_bulb - eps * (e_in.dry_bulb - s_in.dry_bulb)
        exhaust_out = calc.from_db_w(exhaust_out_db, e_in.humidity_ratio,
                                     label=f"{self.name} Exhaust Out")

        s_mass = self.ports["supply_in"].mass_flow
        e_mass = self.ports["exhaust_in"].mass_flow

        self.ports["supply_out"].air_state = supply_out
        self.ports["supply_out"].mass_flow = s_mass
        self.ports["exhaust_out"].air_state = exhaust_out
        self.ports["exhaust_out"].mass_flow = e_mass

        sensible_recovery = (
            s_mass * 60 * (supply_out.enthalpy - s_in.enthalpy)
            if s_mass else 0
        )

        self.results = {
            "supply_out_state": supply_out,
            "exhaust_out_state": exhaust_out,
            "sensible_recovery_btuh": sensible_recovery,
        }

    def get_param_definitions(self):
        return [
            {"name": "sensible_effectiveness", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Sensible heat recovery effectiveness"},
            {"name": "device_type", "type": "choice",
             "choices": ["plate_exchanger", "heat_wheel", "heat_pipe"],
             "tooltip": "Device type (informational)"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "sensible_recovery_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum sensible recovery capacity (leave 0 for no limit)"},
        ]
