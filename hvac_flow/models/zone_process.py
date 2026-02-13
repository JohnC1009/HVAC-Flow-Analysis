"""Zone / Room Process node — models sensible + latent heat gain from occupied space."""

from hvac_flow.engine.constants import CP_AIR_IP
from hvac_flow.models.base_node import BaseNode, Port

# Latent heat of vaporization at typical HVAC conditions
H_FG_IP = 1061.0  # Btu/lb_water


class ZoneProcessNode(BaseNode):
    NODE_TYPE = "zone_process"
    DISPLAY_NAME = "Zone Process"

    def _init_ports(self):
        self.ports["supply_air"] = Port(name="supply_air", direction="inlet")
        self.ports["return_air"] = Port(name="return_air", direction="outlet")

    def _init_parameters(self):
        self.parameters = {
            "input_mode": "loads",       # "loads" or "shr_total"
            "sensible_load_btuh": 120000.0,
            "latent_load_btuh": 30000.0,
            "total_load_btuh": 150000.0,
            "sensible_heat_ratio": 0.80,
        }

    def _init_boundary_conditions(self):
        self.boundary_conditions = {
            "total_load_btuh": None,  # Max total zone load capacity (Btu/hr)
        }

    def compute(self, calc) -> None:
        inlet = self.ports["supply_air"]
        entering = inlet.air_state
        if entering is None:
            raise ValueError(
                f"[{self.name}] Supply air state is not available — "
                f"check upstream connections."
            )
        mass_flow = inlet.mass_flow
        if not mass_flow or mass_flow <= 0:
            raise ValueError(
                f"[{self.name}] Supply air mass flow is zero or missing — "
                f"verify source node airflow."
            )

        if self.parameters["input_mode"] == "loads":
            q_sensible = self.parameters["sensible_load_btuh"]
            q_latent = self.parameters["latent_load_btuh"]
        else:
            q_total = self.parameters["total_load_btuh"]
            shr = self.parameters["sensible_heat_ratio"]
            q_sensible = q_total * shr
            q_latent = q_total * (1 - shr)

        # Temperature rise from sensible load
        delta_t = q_sensible / (mass_flow * 60 * CP_AIR_IP)
        return_db = entering.dry_bulb + delta_t

        # Humidity ratio rise from latent load
        delta_w = q_latent / (mass_flow * 60 * H_FG_IP)
        return_w = max(entering.humidity_ratio + delta_w, 0.0)

        leaving = calc.from_db_w(return_db, return_w,
                                 label=f"{self.name} Return")

        actual_shr = q_sensible / (q_sensible + q_latent) if (q_sensible + q_latent) else 0

        self.ports["return_air"].air_state = leaving
        self.ports["return_air"].mass_flow = mass_flow
        self.results = {
            "outlet_state": leaving,
            "sensible_load_btuh": q_sensible,
            "latent_load_btuh": q_latent,
            "total_load_btuh": q_sensible + q_latent,
            "shr": actual_shr,
            "delta_t_f": delta_t,
        }

    def get_param_definitions(self):
        return [
            {"name": "input_mode", "type": "choice",
             "choices": ["loads", "shr_total"],
             "tooltip": "Specify loads directly or via SHR + total"},
            {"name": "sensible_load_btuh", "type": "float",
             "min": 0, "max": 1e8, "unit": "Btu/hr",
             "tooltip": "Zone sensible heat gain"},
            {"name": "latent_load_btuh", "type": "float",
             "min": 0, "max": 1e8, "unit": "Btu/hr",
             "tooltip": "Zone latent heat gain"},
            {"name": "total_load_btuh", "type": "float",
             "min": 0, "max": 1e8, "unit": "Btu/hr",
             "tooltip": "Total zone load (SHR mode)"},
            {"name": "sensible_heat_ratio", "type": "float",
             "min": 0.0, "max": 1.0, "unit": "fraction",
             "tooltip": "Sensible heat ratio (SHR mode)"},
        ]

    def get_boundary_definitions(self):
        return [
            {"name": "total_load_btuh", "type": "float",
             "min": 0, "max": 1e9, "unit": "Btu/hr",
             "tooltip": "Maximum total zone load capacity (leave 0 for no limit)"},
        ]
