"""Enthalpy wheel (energy recovery) node — two-stream heat/moisture exchange."""

from hvac_flow.models.base_node import BaseNode, Port


class EnthalpyWheelNode(BaseNode):
    NODE_TYPE = "enthalpy_wheel"
    DISPLAY_NAME = "Enthalpy Wheel"

    def _init_ports(self):
        self.ports["supply_in"] = Port(name="supply_in", direction="inlet")
        self.ports["supply_out"] = Port(name="supply_out", direction="outlet")
        self.ports["exhaust_in"] = Port(name="exhaust_in", direction="inlet")
        self.ports["exhaust_out"] = Port(name="exhaust_out", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "sensible_effectiveness": 0.75,
            "latent_effectiveness": 0.70,
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
        eps_s = self.parameters["sensible_effectiveness"]
        eps_l = self.parameters["latent_effectiveness"]
        bypass = self.parameters["bypass_fraction"]
        through_fraction = 1.0 - bypass

        # Wheel physics on the through-flow portion
        wheel_out_db = s_in.dry_bulb + eps_s * (e_in.dry_bulb - s_in.dry_bulb)
        wheel_out_w = (s_in.humidity_ratio
                       + eps_l * (e_in.humidity_ratio - s_in.humidity_ratio))
        wheel_out = calc.from_db_w(wheel_out_db, wheel_out_w,
                                   label=f"{self.name} Wheel Out")

        # Mix wheel outlet with bypassed air
        if bypass > 0.0:
            mixed_w = through_fraction * wheel_out.humidity_ratio + bypass * s_in.humidity_ratio
            mixed_h = through_fraction * wheel_out.enthalpy + bypass * s_in.enthalpy
            supply_out = calc.from_enthalpy_w(mixed_h, mixed_w,
                                              label=f"{self.name} Supply Out")
        else:
            supply_out = wheel_out.with_label(f"{self.name} Supply Out")

        # Exhaust outlet: energy balance accounts for reduced supply flow through wheel
        exhaust_out_db = e_in.dry_bulb - eps_s * through_fraction * (e_in.dry_bulb - s_in.dry_bulb)
        exhaust_out_w = (e_in.humidity_ratio
                         - eps_l * through_fraction * (e_in.humidity_ratio - s_in.humidity_ratio))
        exhaust_out = calc.from_db_w(exhaust_out_db, exhaust_out_w,
                                     label=f"{self.name} Exhaust Out")

        s_mass = self.ports["supply_in"].mass_flow
        e_mass = self.ports["exhaust_in"].mass_flow

        self.ports["supply_out"].air_state = supply_out
        self.ports["supply_out"].mass_flow = s_mass
        self.ports["exhaust_out"].air_state = exhaust_out
        self.ports["exhaust_out"].mass_flow = e_mass

        sensible_recovery = (s_mass * 60 *
                             (supply_out.enthalpy - s_in.enthalpy)
                             if s_mass else 0)

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
            {"name": "latent_effectiveness", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Latent heat recovery effectiveness"},
            {"name": "bypass_fraction", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Fraction of supply air bypassing the wheel (0 = all through wheel)"},
            {"name": "supply_pressure_drop_iw", "type": "float", "min": 0.0,
             "max": 10.0, "unit": "inWG",
             "tooltip": "Supply-side pressure drop across wheel"},
            {"name": "exhaust_pressure_drop_iw", "type": "float", "min": 0.0,
             "max": 10.0, "unit": "inWG",
             "tooltip": "Exhaust-side pressure drop across wheel"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "sensible_recovery_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum energy recovery capacity (leave 0 for no limit)"},
        ]
