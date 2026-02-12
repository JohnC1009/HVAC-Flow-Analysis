"""Project container — holds the flow graph and global settings."""

from hvac_flow.engine.constants import UnitSystem, STD_ATM_PRESSURE_IP
from hvac_flow.models.flow_graph import FlowGraph


class Project:
    """Top-level project container."""

    def __init__(self):
        self.graph = FlowGraph()
        self.unit_system = UnitSystem.IP
        self.pressure = STD_ATM_PRESSURE_IP
        self.altitude_ft = 0.0
        self.name = "Untitled Project"
