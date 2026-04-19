"""System templates for common HVAC configurations."""

from typing import Dict, List, Any

from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.models.connector import Connector
from hvac_flow.models.source_node import SourceNode
from hvac_flow.models.air_sink import AirSinkNode
from hvac_flow.models.cooling_coil import CoolingCoilNode
from hvac_flow.models.heating_coil import HeatingCoilNode
from hvac_flow.models.mixing_box import MixingBoxNode
from hvac_flow.models.fan import FanNode
from hvac_flow.models.chilled_water_coil import ChilledWaterCoilNode
from hvac_flow.models.hot_water_coil import HotWaterCoilNode
from hvac_flow.models.pump import PumpNode
from hvac_flow.models.sensible_heat_recovery import SensibleHeatRecoveryNode
from hvac_flow.models.enthalpy_wheel import EnthalpyWheelNode


class SystemTemplate:
    """Base class for system templates."""
    
    name: str = ""
    description: str = ""
    category: str = ""
    
    @classmethod
    def create(cls) -> FlowGraph:
        """Create the system and return the graph."""
        raise NotImplementedError
    
    @classmethod
    def get_info(cls) -> Dict[str, Any]:
        """Get template information."""
        return {
            "name": cls.name,
            "description": cls.description,
            "category": cls.category,
        }


class SimpleAHU(SystemTemplate):
    """Simple air handling unit with mixing box, cooling coil, and fan."""
    
    name = "Simple AHU"
    description = "Basic air handler with economizer, cooling coil, and supply fan"
    category = "Air Handling"
    
    @classmethod
    def create(cls) -> FlowGraph:
        graph = FlowGraph()
        
        # Create nodes
        oa = SourceNode(name="Outdoor Air")
        ra = SourceNode(name="Return Air")
        mixer = MixingBoxNode(name="Mixing Box")
        coil = CoolingCoilNode(name="Cooling Coil")
        fan = FanNode(name="Supply Fan")
        zone = AirSinkNode(name="Zone")
        
        # Configure
        oa.parameters.update({"dry_bulb": 95.0, "relative_humidity": 0.40, "mass_flow": 400})
        ra.parameters.update({"dry_bulb": 75.0, "relative_humidity": 0.50, "mass_flow": 1600})
        
        mixer.parameters.update({
            "economizer_mode": "temperature",
            "min_oa_fraction": 0.20,
            "econ_high_limit_db": 75.0,
            "supply_setpoint_db": 55.0
        })
        
        coil.parameters.update({
            "leaving_db": 55.0,
            "leaving_mode": "rh",
            "leaving_rh": 0.90
        })
        
        fan.parameters.update({
            "input_mode": "bhp",
            "bhp": 15.0,
            "motor_efficiency": 0.90
        })
        
        # Add to graph
        for node in [oa, ra, mixer, coil, fan, zone]:
            graph.add_node(node)
        
        # Connect
        connections = [
            (oa, "outlet", mixer, "primary"),
            (ra, "outlet", mixer, "secondary"),
            (mixer, "mixed", coil, "inlet"),
            (coil, "outlet", fan, "inlet"),
            (fan, "outlet", zone, "inlet"),
        ]
        
        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            graph.add_connector(conn)
        
        return graph


class DOASWithHeatRecovery(SystemTemplate):
    """Dedicated Outdoor Air System with energy recovery."""
    
    name = "DOAS with ERV"
    description = "100% outdoor air system with enthalpy wheel energy recovery"
    category = "Ventilation"
    
    @classmethod
    def create(cls) -> FlowGraph:
        graph = FlowGraph()
        
        oa = SourceNode(name="Outdoor Air")
        ra = SourceNode(name="Return Air")
        erv = EnthalpyWheelNode(name="Energy Recovery")
        coil = ChilledWaterCoilNode(name="Cooling Coil")
        hw_coil = HotWaterCoilNode(name="Heating Coil")
        fan = FanNode(name="Supply Fan")
        zone = AirSinkNode(name="Zone")
        
        # Configure
        oa.parameters.update({"dry_bulb": 95.0, "relative_humidity": 0.60, "mass_flow": 1000})
        ra.parameters.update({"dry_bulb": 75.0, "relative_humidity": 0.50, "mass_flow": 1000})
        
        erv.parameters.update({
            "sensible_effectiveness": 0.75,
            "latent_effectiveness": 0.60
        })
        
        coil.parameters.update({
            "leaving_db": 55.0,
            "leaving_mode": "rh",
            "leaving_rh": 0.90,
            "entering_water_temp": 44.0,
            "water_flow_gpm": 100
        })
        
        hw_coil.parameters.update({
            "leaving_db": 65.0,
            "entering_water_temp": 180.0,
            "water_flow_gpm": 20
        })
        
        fan.parameters.update({
            "input_mode": "bhp",
            "bhp": 10.0,
            "motor_efficiency": 0.90
        })
        
        # Add nodes
        for node in [oa, ra, erv, coil, hw_coil, fan, zone]:
            graph.add_node(node)
        
        # Connect (simplified - ERV has two air streams)
        connections = [
            (oa, "outlet", erv, "supply_inlet"),
            (ra, "outlet", erv, "exhaust_inlet"),
            (erv, "supply_outlet", coil, "air_inlet"),
            (coil, "air_outlet", hw_coil, "air_inlet"),
            (hw_coil, "air_outlet", fan, "inlet"),
            (fan, "outlet", zone, "inlet"),
        ]
        
        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            graph.add_connector(conn)
        
        return graph


class ChilledWaterPlant(SystemTemplate):
    """Central chilled water plant with chiller, pumps, and coils."""
    
    name = "Chilled Water Plant"
    description = "Chiller with primary/secondary pumping and multiple air handlers"
    category = "Hydronic"
    
    @classmethod
    def create(cls) -> FlowGraph:
        graph = FlowGraph()
        
        # Chiller (modeled as a black box)
        chiller_supply = SourceNode(name="Chiller Supply")
        chiller_return = AirSinkNode(name="Chiller Return")
        
        # Pumps
        primary_pump = PumpNode(name="Primary Pump")
        secondary_pump = PumpNode(name="Secondary Pump")
        
        # Air handlers
        ahu1_coil = ChilledWaterCoilNode(name="AHU-1 Coil")
        ahu2_coil = ChilledWaterCoilNode(name="AHU-2 Coil")
        
        # Configure
        chiller_supply.parameters.update({
            "dry_bulb": 44.0,
            "relative_humidity": 0.0,
            "mass_flow": 0  # Water system
        })
        
        primary_pump.parameters.update({
            "flow_rate_gpm": 500,
            "head_ft": 30,
            "efficiency": 0.75
        })
        
        secondary_pump.parameters.update({
            "flow_rate_gpm": 400,
            "head_ft": 40,
            "efficiency": 0.75,
            "variable_speed": True,
            "speed_percent": 75
        })
        
        for coil in [ahu1_coil, ahu2_coil]:
            coil.parameters.update({
                "leaving_db": 55.0,
                "leaving_mode": "rh",
                "leaving_rh": 0.90,
                "entering_water_temp": 44.0,
                "water_flow_gpm": 200
            })
        
        # Add nodes
        for node in [chiller_supply, chiller_return, primary_pump, secondary_pump,
                     ahu1_coil, ahu2_coil]:
            graph.add_node(node)
        
        # Connect (simplified hydronic loop)
        # In reality, this would need a more sophisticated model
        
        return graph


class VAVWithReheat(SystemTemplate):
    """Variable air volume system with terminal reheat."""
    
    name = "VAV with Reheat"
    description = "Central AHU with VAV boxes and hot water reheat coils"
    category = "Air Handling"
    
    @classmethod
    def create(cls) -> FlowGraph:
        graph = FlowGraph()
        
        # Central AHU
        oa = SourceNode(name="Outdoor Air")
        ra = SourceNode(name="Return Air")
        mixer = MixingBoxNode(name="Mixing Box")
        cooling = CoolingCoilNode(name="Cooling Coil")
        fan = FanNode(name="Supply Fan")
        
        # VAV zones (simplified - just show reheat concept)
        vav1 = AirSink(name="VAV Zone 1")
        vav2 = AirSink(name="VAV Zone 2")
        
        # Configure
        oa.parameters.update({"dry_bulb": 95.0, "relative_humidity": 0.40, "mass_flow": 500})
        ra.parameters.update({"dry_bulb": 75.0, "relative_humidity": 0.50, "mass_flow": 4500})
        
        mixer.parameters.update({
            "economizer_mode": "enthalpy",
            "min_oa_fraction": 0.10
        })
        
        cooling.parameters.update({
            "leaving_db": 55.0,
            "leaving_mode": "rh",
            "leaving_rh": 0.95  # Cold deck
        })
        
        fan.parameters.update({
            "input_mode": "bhp",
            "bhp": 25.0,
            "motor_efficiency": 0.92
        })
        
        # Add nodes
        for node in [oa, ra, mixer, cooling, fan, vav1, vav2]:
            graph.add_node(node)
        
        # Connect AHU
        connections = [
            (oa, "outlet", mixer, "primary"),
            (ra, "outlet", mixer, "secondary"),
            (mixer, "mixed", cooling, "inlet"),
            (cooling, "outlet", fan, "inlet"),
        ]
        
        for src, src_port, tgt, tgt_port in connections:
            conn = Connector(
                source_node_id=src.id, source_port_name=src_port,
                target_node_id=tgt.id, target_port_name=tgt_port
            )
            graph.add_connector(conn)
        
        # Split to zones (would need duct split node in reality)
        
        return graph


class TemplateLibrary:
    """Library of available system templates."""
    
    TEMPLATES = {
        "simple_ahu": SimpleAHU,
        "doas_erv": DOASWithHeatRecovery,
        "chw_plant": ChilledWaterPlant,
        "vav_reheat": VAVWithReheat,
    }
    
    @classmethod
    def list_templates(cls) -> List[Dict[str, Any]]:
        """List all available templates."""
        return [template.get_info() for template in cls.TEMPLATES.values()]
    
    @classmethod
    def get_template(cls, name: str) -> SystemTemplate:
        """Get a template by name."""
        if name in cls.TEMPLATES:
            return cls.TEMPLATES[name]
        raise ValueError(f"Template '{name}' not found")
    
    @classmethod
    def create_system(cls, name: str) -> FlowGraph:
        """Create a system from a template."""
        template = cls.get_template(name)
        return template.create()
