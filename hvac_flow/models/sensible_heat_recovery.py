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
            "bypass_fraction": 0.0,
            "supply_pressure_drop_iw": 0.0,
            "exhaust_pressure_drop_iw": 0.0,
        }

    def _init_boundary_conditions(self):
        self.boundary_conditions = {
            "sensible_recovery_btuh": None,  # Max recovery capacity (Btu/hr)
        }

    def get_iterable_inlet(self):
        return "exhaust_in"

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
        bypass = self.parameters["bypass_fraction"]
        through_fraction = 1.0 - bypass

        # Supply side: DB changes, W unchanged
        wheel_out_db = s_in.dry_bulb + eps * (e_in.dry_bulb - s_in.dry_bulb)

        # Mix wheel outlet with bypassed air
        if bypass > 0.0:
            supply_out_db = through_fraction * wheel_out_db + bypass * s_in.dry_bulb
        else:
            supply_out_db = wheel_out_db

        supply_out = calc.from_db_w(supply_out_db, s_in.humidity_ratio,
                                    label=f"{self.name} Supply Out")

        # Exhaust side: energy balance accounts for reduced supply flow through wheel
        exhaust_out_db = e_in.dry_bulb - eps * through_fraction * (e_in.dry_bulb - s_in.dry_bulb)
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

        supply_in_cfm = s_mass * s_in.specific_volume if s_mass else 0
        supply_out_cfm = s_mass * supply_out.specific_volume if s_mass else 0
        exhaust_in_cfm = e_mass * e_in.specific_volume if e_mass else 0
        exhaust_out_cfm = e_mass * exhaust_out.specific_volume if e_mass else 0

        self.results = {
            "supply_out_state": supply_out,
            "exhaust_out_state": exhaust_out,
            "sensible_recovery_btuh": sensible_recovery,
            "bypass_fraction": bypass,
            "supply_in_cfm": supply_in_cfm,
            "supply_out_cfm": supply_out_cfm,
            "exhaust_in_cfm": exhaust_in_cfm,
            "exhaust_out_cfm": exhaust_out_cfm,
            "supply_pressure_drop_iw": self.parameters["supply_pressure_drop_iw"],
            "exhaust_pressure_drop_iw": self.parameters["exhaust_pressure_drop_iw"],
        }

    def get_param_definitions(self):
        return [
            {"name": "sensible_effectiveness", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Sensible heat recovery effectiveness"},
            {"name": "device_type", "type": "choice",
             "choices": ["plate_exchanger", "heat_wheel", "heat_pipe"],
             "tooltip": "Device type (informational)"},
            {"name": "bypass_fraction", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Fraction of supply air bypassing the device (0 = all through device)"},
            {"name": "supply_pressure_drop_iw", "type": "float", "min": 0.0,
             "max": 10.0, "unit": "inWG",
             "tooltip": "Supply-side pressure drop across device"},
            {"name": "exhaust_pressure_drop_iw", "type": "float", "min": 0.0,
             "max": 10.0, "unit": "inWG",
             "tooltip": "Exhaust-side pressure drop across device"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "sensible_recovery_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum sensible recovery capacity (leave 0 for no limit)"},
        ]
