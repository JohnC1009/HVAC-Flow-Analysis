"""Indirect evaporative cooler node.

Cools the primary (supply) airstream sensibly using evaporative cooling
on a secondary (scavenger) airstream. The supply air DB drops with no
moisture addition — a horizontal line to the left on the psychrometric chart.
"""

from hvac_flow.engine.constants import CP_AIR_IP
from hvac_flow.models.base_node import BaseNode, Port


class IndirectEvapCoolerNode(BaseNode):
    NODE_TYPE = "indirect_evap_cooler"
    DISPLAY_NAME = "Indirect Evap Cooler"

    def _init_ports(self):
        self.ports["primary_in"] = Port(name="primary_in", direction="inlet")
        self.ports["primary_out"] = Port(name="primary_out", direction="outlet")
        self.ports["secondary_in"] = Port(name="secondary_in", direction="inlet")
        self.ports["secondary_out"] = Port(name="secondary_out", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "wet_bulb_effectiveness": 0.70,
        }

    def _init_boundary_conditions(self):
        self.boundary_conditions = {
            "cooling_btuh": None,  # Max cooling capacity (Btu/hr)
        }

    def get_iterable_inlet(self):
        return "secondary_in"

    def compute(self, calc) -> None:
        p_in = self.ports["primary_in"].air_state
        s_in = self.ports["secondary_in"].air_state
        if p_in is None:
            raise ValueError(
                f"[{self.name}] Primary inlet air state is not available — "
                f"check upstream connections on 'primary_in' port."
            )
        if s_in is None:
            raise ValueError(
                f"[{self.name}] Secondary inlet air state is not available — "
                f"check upstream connections on 'secondary_in' port."
            )
        eff = self.parameters["wet_bulb_effectiveness"]

        # Primary side: sensible cooling toward secondary wet-bulb
        # DB drops, W stays constant (no moisture added to primary)
        primary_out_db = p_in.dry_bulb - eff * (p_in.dry_bulb - s_in.wet_bulb)
        primary_out = calc.from_db_w(primary_out_db, p_in.humidity_ratio,
                                     label=f"{self.name} Primary Out")

        # Secondary side undergoes direct evaporative cooling then heating
        # Simplified: secondary picks up the heat rejected by primary
        # and exhausts warmer and more humid
        p_mass = self.ports["primary_in"].mass_flow
        s_mass = self.ports["secondary_in"].mass_flow

        if p_mass and s_mass:
            q_removed = p_mass * 60 * CP_AIR_IP * (p_in.dry_bulb - primary_out_db)
            secondary_dt = q_removed / (s_mass * 60 * CP_AIR_IP)
            secondary_out_db = s_in.dry_bulb + secondary_dt
        else:
            secondary_out_db = s_in.dry_bulb

        secondary_out = calc.from_db_w(secondary_out_db, s_in.humidity_ratio,
                                       label=f"{self.name} Secondary Out")

        self.ports["primary_out"].air_state = primary_out
        self.ports["primary_out"].mass_flow = p_mass
        self.ports["secondary_out"].air_state = secondary_out
        self.ports["secondary_out"].mass_flow = s_mass

        cooling_btuh = (
            p_mass * 60 * (p_in.enthalpy - primary_out.enthalpy) if p_mass else 0
        )

        self.results = {
            "primary_out_state": primary_out,
            "secondary_out_state": secondary_out,
            "cooling_btuh": cooling_btuh,
            "primary_db_drop_f": p_in.dry_bulb - primary_out_db,
        }

    def get_param_definitions(self):
        return [
            {"name": "wet_bulb_effectiveness", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Wet-bulb effectiveness (how close primary DB gets to secondary WB)"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "cooling_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum cooling capacity (leave 0 for no limit)"},
        ]
