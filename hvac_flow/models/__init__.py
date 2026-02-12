"""Equipment node models and flow graph."""

from hvac_flow.models.source_node import SourceNode
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.heating_coil import HeatingCoilNode
from hvac_flow.models.fan import FanNode
from hvac_flow.models.enthalpy_wheel import EnthalpyWheelNode
from hvac_flow.models.mixing_box import MixingBoxNode


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
             FanNode, EnthalpyWheelNode, MixingBoxNode]:
    NodeFactory.register(_cls)
