"""Runaround heat recovery loop node.

Models a runaround coil system with a glycol loop connecting a supply-side
coil and an exhaust-side coil. Transfers sensible heat only; no moisture
transfer is possible since the two airstreams are physically separated.

Lower effectiveness than plate/wheel devices (typically 0.45-0.65) due to
the intermediate glycol loop, but allows the supply and exhaust ducts to
be in completely different locations.
"""

from hvac_flow.engine.constants import CP_AIR_IP
from hvac_flow.models.base_node import BaseNode, Port


class RunaroundLoopNode(BaseNode):
    NODE_TYPE = "runaround_loop"
    DISPLAY_NAME = "Runaround Loop"

    def _init_ports(self):
        self.ports["supply_in"] = Port(name="supply_in", direction="inlet")
        self.ports["supply_out"] = Port(name="supply_out", direction="outlet")
        self.ports["exhaust_in"] = Port(name="exhaust_in", direction="inlet")
        self.ports["exhaust_out"] = Port(name="exhaust_out", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "sensible_effectiveness": 0.55,
            "glycol_concentration_pct": 30.0,
            "glycol_flow_gpm": 50.0,
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
        s_mass = self.ports["supply_in"].mass_flow
        e_mass = self.ports["exhaust_in"].mass_flow

        # Capacity ratio correction: if flows are unequal, effective epsilon
        # is based on the minimum-capacity stream (simplified model).
        # For a runaround loop the glycol loop acts as the coupling medium.
        # Using the standard effectiveness-NTU result for the air-side:
        # Q = eps * C_min * (T_exhaust_in - T_supply_in)
        if s_mass and e_mass:
            c_supply = s_mass * 60 * CP_AIR_IP   # Btu/(hr·°F)
            c_exhaust = e_mass * 60 * CP_AIR_IP
            c_min = min(c_supply, c_exhaust)
            c_max = max(c_supply, c_exhaust)

            q_recovered = eps * c_min * (e_in.dry_bulb - s_in.dry_bulb)

            supply_out_db = s_in.dry_bulb + q_recovered / c_supply
            exhaust_out_db = e_in.dry_bulb - q_recovered / c_exhaust
        else:
            supply_out_db = s_in.dry_bulb
            exhaust_out_db = e_in.dry_bulb
            q_recovered = 0

        # Sensible only — humidity ratios unchanged
        supply_out = calc.from_db_w(supply_out_db, s_in.humidity_ratio,
                                    label=f"{self.name} Supply Out")
        exhaust_out = calc.from_db_w(exhaust_out_db, e_in.humidity_ratio,
                                     label=f"{self.name} Exhaust Out")

        self.ports["supply_out"].air_state = supply_out
        self.ports["supply_out"].mass_flow = s_mass
        self.ports["exhaust_out"].air_state = exhaust_out
        self.ports["exhaust_out"].mass_flow = e_mass

        supply_in_cfm = s_mass * s_in.specific_volume if s_mass else 0
        supply_out_cfm = s_mass * supply_out.specific_volume if s_mass else 0
        exhaust_in_cfm = e_mass * e_in.specific_volume if e_mass else 0
        exhaust_out_cfm = e_mass * exhaust_out.specific_volume if e_mass else 0

        self.results = {
            "supply_out_state": supply_out,
            "exhaust_out_state": exhaust_out,
            "sensible_recovery_btuh": q_recovered,
            "sensible_recovery_tons": q_recovered / 12000.0 if q_recovered else 0,
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
             "tooltip": "Overall sensible effectiveness (typical 0.45-0.65)"},
            {"name": "glycol_concentration_pct", "type": "float",
             "min": 0, "max": 60, "unit": "%",
             "tooltip": "Glycol concentration (informational)"},
            {"name": "glycol_flow_gpm", "type": "float",
             "min": 0, "max": 1000, "unit": "GPM",
             "tooltip": "Glycol loop flow rate (informational)"},
            {"name": "supply_pressure_drop_iw", "type": "float", "min": 0.0,
             "max": 10.0, "unit": "inWG",
             "tooltip": "Supply-side coil pressure drop"},
            {"name": "exhaust_pressure_drop_iw", "type": "float", "min": 0.0,
             "max": 10.0, "unit": "inWG",
             "tooltip": "Exhaust-side coil pressure drop"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "sensible_recovery_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum sensible recovery capacity (leave 0 for no limit)"},
        ]
