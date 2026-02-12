"""Mixing box node — blends two airstreams with optional economizer control."""

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
            "economizer_mode": "fixed",   # "fixed", "temperature", "enthalpy"
            "min_oa_fraction": 0.15,
            "econ_high_limit_db": 65.0,   # °F — OA lockout above this DB
            "econ_high_limit_h": 28.0,    # Btu/lb — OA lockout above this enthalpy
            "supply_setpoint_db": 55.0,   # °F — target mixed-air temp for economizer
        }

    def compute(self, calc) -> None:
        p = self.ports["primary"]
        s = self.ports["secondary"]
        if p.air_state is None:
            raise ValueError(
                f"[{self.name}] Primary inlet air state is not available — "
                f"check upstream connections on 'primary' port."
            )
        if s.air_state is None:
            raise ValueError(
                f"[{self.name}] Secondary inlet air state is not available — "
                f"check upstream connections on 'secondary' port."
            )

        f = self._determine_oa_fraction(p, s)

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
            "effective_oa_fraction": f,
        }

    def _determine_oa_fraction(self, primary, secondary):
        """Calculate outdoor-air fraction based on economizer mode."""
        mode = self.parameters["economizer_mode"]
        min_oa = self.parameters["min_oa_fraction"]

        if mode == "fixed":
            return self.parameters["primary_fraction"]

        oa_state = primary.air_state
        ra_state = secondary.air_state

        # Check lockout conditions
        if mode == "temperature":
            if oa_state.dry_bulb > self.parameters["econ_high_limit_db"]:
                return min_oa  # Too hot, minimum OA only
        elif mode == "enthalpy":
            if oa_state.enthalpy > self.parameters["econ_high_limit_h"]:
                return min_oa  # Too much energy, minimum OA only
            if oa_state.enthalpy > ra_state.enthalpy:
                return min_oa  # OA is worse than RA

        # Economizer is active: modulate OA to reach supply setpoint
        sp = self.parameters["supply_setpoint_db"]

        if abs(oa_state.dry_bulb - ra_state.dry_bulb) < 0.1:
            return min_oa  # No temperature difference to exploit

        # f = (T_supply - T_return) / (T_oa - T_return)
        f = (sp - ra_state.dry_bulb) / (oa_state.dry_bulb - ra_state.dry_bulb)
        f = max(min_oa, min(f, 1.0))
        return f

    def get_param_definitions(self):
        return [
            {"name": "primary_fraction", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Fixed OA fraction (used in 'fixed' mode)"},
            {"name": "economizer_mode", "type": "choice",
             "choices": ["fixed", "temperature", "enthalpy"],
             "tooltip": "Economizer control strategy"},
            {"name": "min_oa_fraction", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Minimum outdoor-air fraction (ventilation requirement)"},
            {"name": "econ_high_limit_db", "type": "float",
             "min": 30, "max": 100, "unit": "°F",
             "tooltip": "OA temp lockout for temperature economizer"},
            {"name": "econ_high_limit_h", "type": "float",
             "min": 10, "max": 50, "unit": "Btu/lb",
             "tooltip": "OA enthalpy lockout for enthalpy economizer"},
            {"name": "supply_setpoint_db", "type": "float",
             "min": 40, "max": 80, "unit": "°F",
             "tooltip": "Target mixed-air temperature when economizer is active"},
        ]
