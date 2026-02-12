"""Equipment node models and flow graph."""

from hvac_flow.models.source_node import SourceNode
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.heating_coil import HeatingCoilNode
from hvac_flow.models.fan import FanNode
from hvac_flow.models.enthalpy_wheel import EnthalpyWheelNode
from hvac_flow.models.mixing_box import MixingBoxNode
from hvac_flow.models.zone_process import ZoneProcessNode
from hvac_flow.models.duct_split import DuctSplitNode
from hvac_flow.models.steam_humidifier import SteamHumidifierNode
from hvac_flow.models.adiabatic_humidifier import AdiabaticHumidifierNode
from hvac_flow.models.sensible_heat_recovery import SensibleHeatRecoveryNode
from hvac_flow.models.runaround_loop import RunaroundLoopNode
from hvac_flow.models.indirect_evap_cooler import IndirectEvapCoolerNode
from hvac_flow.models.desiccant_wheel import DesiccantWheelNode
from hvac_flow.models.return_fan import ReturnFanNode
from hvac_flow.models.air_sink import AirSinkNode


class NodeFactory:
    """Factory for creating equipment nodes by type string."""

    _registry = {}

    @classmethod
    def register(cls, node_class):
        cls._registry[node_class.NODE_TYPE] = node_class

    @classmethod
    def create(cls, type_id, **kwargs):
        if type_id not in cls._registry:
            raise ValueError(f"Unknown node type: {type_id}")
        return cls._registry[type_id](**kwargs)

    @classmethod
    def get_types(cls):
        return dict(cls._registry)


for _cls in [SourceNode, CoolingCoilNode, HeatingCoilNode,
             FanNode, EnthalpyWheelNode, MixingBoxNode,
             ZoneProcessNode, DuctSplitNode, SteamHumidifierNode,
             AdiabaticHumidifierNode, SensibleHeatRecoveryNode,
             RunaroundLoopNode, IndirectEvapCoolerNode,
             DesiccantWheelNode, ReturnFanNode, AirSinkNode]:
    NodeFactory.register(_cls)
