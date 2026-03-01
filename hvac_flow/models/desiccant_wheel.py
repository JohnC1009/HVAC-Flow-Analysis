"""Desiccant wheel node — active dehumidification via adsorption.

The process airstream loses moisture (W drops) but gains sensible heat from
the heat of adsorption (DB rises). On the psychrometric chart the state point
moves down and to the right. A regeneration airstream (heated externally) drives
moisture off the wheel and is exhausted.
"""

from hvac_flow.engine.constants import CP_AIR_IP, H_FG_IP
from hvac_flow.models.base_node import BaseNode, Port


class DesiccantWheelNode(BaseNode):
    NODE_TYPE = "desiccant_wheel"
    DISPLAY_NAME = "Desiccant Wheel"

    def _init_ports(self):
        self.ports["process_in"] = Port(name="process_in", direction="inlet")
        self.ports["process_out"] = Port(name="process_out", direction="outlet")
        self.ports["regen_in"] = Port(name="regen_in", direction="inlet")
        self.ports["regen_out"] = Port(name="regen_out", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "dehumidification_effectiveness": 0.75,
            "heat_carryover_fraction": 0.10,
        }

    def _init_boundary_conditions(self):
        self.boundary_conditions = {
            "moisture_removed_lb_hr": None,  # Max moisture removal (lb/hr)
        }

    def compute(self, calc) -> None:
        p_in = self.ports["process_in"].air_state
        r_in = self.ports["regen_in"].air_state
        if p_in is None:
            raise ValueError(
                f"[{self.name}] Process inlet air state is not available — "
                f"check upstream connections on 'process_in' port."
            )
        if r_in is None:
            raise ValueError(
                f"[{self.name}] Regen inlet air state is not available — "
                f"check upstream connections on 'regen_in' port."
            )
        eff = self.parameters["dehumidification_effectiveness"]
        carryover = self.parameters["heat_carryover_fraction"]

        p_mass = self.ports["process_in"].mass_flow
        r_mass = self.ports["regen_in"].mass_flow

        # Process side: moisture removal
        delta_w = eff * (p_in.humidity_ratio - r_in.humidity_ratio)
        delta_w = max(delta_w, 0.0)  # only dehumidify
        process_out_w = p_in.humidity_ratio - delta_w

        # DB rise from heat of adsorption
        delta_t_adsorption = H_FG_IP * delta_w / CP_AIR_IP

        # Additional heat carryover from hot regen side of wheel
        delta_t_carryover = carryover * (r_in.dry_bulb - p_in.dry_bulb)
        delta_t_carryover = max(delta_t_carryover, 0.0)

        process_out_db = p_in.dry_bulb + delta_t_adsorption + delta_t_carryover
        process_out = calc.from_db_w(process_out_db, process_out_w,
                                     label=f"{self.name} Process Out")

        # Regen side: picks up moisture, cools down
        if p_mass and r_mass:
            mass_ratio = p_mass / r_mass
            regen_out_w = r_in.humidity_ratio + delta_w * mass_ratio
            regen_out_db = r_in.dry_bulb - delta_t_adsorption * mass_ratio
        else:
            regen_out_w = r_in.humidity_ratio
            regen_out_db = r_in.dry_bulb

        regen_out = calc.from_db_w(regen_out_db, regen_out_w,
                                   label=f"{self.name} Regen Out")

        self.ports["process_out"].air_state = process_out
        self.ports["process_out"].mass_flow = p_mass
        self.ports["regen_out"].air_state = regen_out
        self.ports["regen_out"].mass_flow = r_mass

        moisture_removed = delta_w * p_mass * 60 if p_mass else 0  # lb/hr
        grains_removed = moisture_removed * 7000  # grains/hr

        self.results = {
            "process_out_state": process_out,
            "regen_out_state": regen_out,
            "moisture_removed_lb_hr": moisture_removed,
            "moisture_removed_grains_hr": grains_removed,
            "process_db_rise_f": process_out_db - p_in.dry_bulb,
        }

    def get_param_definitions(self):
        return [
            {"name": "dehumidification_effectiveness", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Moisture removal effectiveness"},
            {"name": "heat_carryover_fraction", "type": "float",
             "min": 0.0, "max": 0.5, "unit": "fraction",
             "tooltip": "Fraction of regen heat carried over to process side"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "moisture_removed_lb_hr", "type": "float",
             "min": 0, "max": 1e6, "unit": "lb/hr",
             "tooltip": "Maximum moisture removal capacity (leave 0 for no limit)"},
        ]
