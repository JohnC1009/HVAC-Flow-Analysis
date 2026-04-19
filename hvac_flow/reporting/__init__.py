"""System comparison and reporting module."""

import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime

from hvac_flow.models.flow_graph import FlowGraph
from hvac_flow.solver.flow_solver import FlowSolver


@dataclass
class SystemMetrics:
    """Key performance metrics for an HVAC system."""
    # Energy
    total_cooling_tons: float = 0.0
    total_cooling_btuh: float = 0.0
    total_heating_btuh: float = 0.0
    fan_energy_kw: float = 0.0
    pump_energy_kw: float = 0.0
    
    # Air flows
    total_supply_cfm: float = 0.0
    outdoor_air_cfm: float = 0.0
    
    # Water flows
    chilled_water_gpm: float = 0.0
    hot_water_gpm: float = 0.0
    condenser_water_gpm: float = 0.0
    
    # Temperatures
    entering_air_db: float = 0.0
    leaving_air_db: float = 0.0
    supply_air_db: float = 0.0
    
    # Economizer
    economizer_savings_percent: float = 0.0
    
    # Efficiency
    eer: float = 0.0  # Energy Efficiency Ratio
    cop: float = 0.0  # Coefficient of Performance


class SystemReporter:
    """Generates reports and comparisons for HVAC systems."""

    def __init__(self):
        self.systems: Dict[str, Dict[str, Any]] = {}

    def capture_system(self, name: str, graph: FlowGraph, solver: FlowSolver) -> SystemMetrics:
        """Capture metrics from a solved system."""
        metrics = SystemMetrics()
        
        # Analyze nodes
        for node in graph.nodes.values():
            node_type = getattr(node, 'NODE_TYPE', '')
            results = getattr(node, 'results', {})
            
            # Cooling
            if node_type in ['cooling_coil', 'chilled_water_coil']:
                tons = results.get('total_load_tons', 0)
                btuh = results.get('total_load_btuh', 0)
                metrics.total_cooling_tons += tons
                metrics.total_cooling_btuh += btuh
            
            # Heating
            if node_type in ['heating_coil', 'hot_water_coil']:
                btuh = results.get('sensible_load_btuh', 0)
                metrics.total_heating_btuh += btuh
            
            # Fans
            if node_type == 'fan':
                kw = results.get('fan_heat_btuh', 0) / 3412  # Approximate
                metrics.fan_energy_kw += kw
            
            # Pumps
            if node_type == 'pump':
                kw = results.get('motor_kw', 0)
                metrics.pump_energy_kw += kw
            
            # Water flows
            if 'water_flow_gpm' in results:
                if node_type == 'chilled_water_coil':
                    metrics.chilled_water_gpm += results['water_flow_gpm']
                elif node_type == 'hot_water_coil':
                    metrics.hot_water_gpm += results['water_flow_gpm']
            
            # Air temperatures
            if 'outlet_state' in results:
                db = results['outlet_state'].dry_bulb
                if node_type == 'source':
                    metrics.entering_air_db = db
                elif node_type == 'air_sink':
                    metrics.leaving_air_db = db
        
        # Calculate derived metrics
        if metrics.total_cooling_btuh > 0:
            total_kw = metrics.fan_energy_kw + metrics.pump_energy_kw
            if total_kw > 0:
                metrics.eer = metrics.total_cooling_btuh / (total_kw * 1000)
                metrics.cop = metrics.eer / 3.412
        
        # Store
        self.systems[name] = {
            'metrics': asdict(metrics),
            'timestamp': datetime.now().isoformat(),
            'node_count': len(graph.nodes),
            'errors': solver.errors,
            'warnings': solver.warnings,
        }
        
        return metrics

    def compare_systems(self, name1: str, name2: str) -> Dict[str, Any]:
        """Compare two systems and return differences."""
        if name1 not in self.systems or name2 not in self.systems:
            raise ValueError("System not found")
        
        sys1 = self.systems[name1]['metrics']
        sys2 = self.systems[name2]['metrics']
        
        comparison = {
            'system_1': name1,
            'system_2': name2,
            'differences': {},
            'percent_change': {},
            'winner': {}
        }
        
        # Compare key metrics
        for key in ['total_cooling_tons', 'total_cooling_btuh', 
                    'fan_energy_kw', 'pump_energy_kw', 'eer', 'cop']:
            val1 = sys1.get(key, 0)
            val2 = sys2.get(key, 0)
            diff = val2 - val1
            pct = ((val2 - val1) / val1 * 100) if val1 != 0 else 0
            
            comparison['differences'][key] = diff
            comparison['percent_change'][key] = pct
            
            # For energy consumption, lower is better
            # For efficiency (EER, COP), higher is better
            if key in ['eer', 'cop']:
                comparison['winner'][key] = name1 if val1 > val2 else name2
            else:
                comparison['winner'][key] = name1 if val1 < val2 else name2
        
        return comparison

    def export_to_json(self, filename: str) -> None:
        """Export all captured systems to JSON."""
        with open(filename, 'w') as f:
            json.dump(self.systems, f, indent=2)

    def generate_text_report(self, name: str) -> str:
        """Generate a human-readable text report."""
        if name not in self.systems:
            return f"System '{name}' not found"
        
        data = self.systems[name]
        m = data['metrics']
        
        report = f"""
{'='*60}
HVAC System Analysis Report
{'='*60}
System Name: {name}
Timestamp: {data['timestamp']}
Nodes: {data['node_count']}

{'-'*60}
ENERGY PERFORMANCE
{'-'*60}
Total Cooling:        {m['total_cooling_tons']:.1f} tons ({m['total_cooling_btuh']:,.0f} Btu/hr)
Total Heating:        {m['total_heating_btuh']:,.0f} Btu/hr
Fan Power:            {m['fan_energy_kw']:.2f} kW
Pump Power:           {m['pump_energy_kw']:.2f} kW

EER:                  {m['eer']:.1f} Btu/Wh
COP:                  {m['cop']:.2f}

{'-'*60}
AIR SIDE
{'-'*60}
Entering Air:         {m['entering_air_db']:.1f}°F
Leaving Air:          {m['leaving_air_db']:.1f}°F
Supply Air:           {m['supply_air_db']:.1f}°F

{'-'*60}
WATER SIDE
{'-'*60}
Chilled Water Flow:   {m['chilled_water_gpm']:.1f} gpm
Hot Water Flow:       {m['hot_water_gpm']:.1f} gpm

{'-'*60}
VALIDATION
{'-'*60}
Errors:   {len(data['errors'])}
Warnings: {len(data['warnings'])}
"""
        if data['errors']:
            report += "\nErrors:\n"
            for err in data['errors']:
                report += f"  - {err}\n"
        
        if data['warnings']:
            report += "\nWarnings:\n"
            for warn in data['warnings']:
                report += f"  - {warn}\n"
        
        report += "\n" + "="*60 + "\n"
        
        return report

    def generate_markdown_report(self, name: str) -> str:
        """Generate a Markdown report suitable for documentation."""
        if name not in self.systems:
            return f"System '{name}' not found"
        
        data = self.systems[name]
        m = data['metrics']
        
        report = f"""# HVAC System Analysis: {name}

**Date:** {data['timestamp'][:10]}  
**Nodes:** {data['node_count']}

## Energy Performance

| Metric | Value |
|--------|-------|
| Total Cooling | {m['total_cooling_tons']:.1f} tons ({m['total_cooling_btuh']:,.0f} Btu/hr) |
| Total Heating | {m['total_heating_btuh']:,.0f} Btu/hr |
| Fan Power | {m['fan_energy_kw']:.2f} kW |
| Pump Power | {m['pump_energy_kw']:.2f} kW |
| **EER** | **{m['eer']:.1f}** |
| **COP** | **{m['cop']:.2f}** |

## Air Side

- Entering Air: {m['entering_air_db']:.1f}°F
- Leaving Air: {m['leaving_air_db']:.1f}°F
- Supply Air: {m['supply_air_db']:.1f}°F

## Water Side

- Chilled Water Flow: {m['chilled_water_gpm']:.1f} gpm
- Hot Water Flow: {m['hot_water_gpm']:.1f} gpm

## Validation

- **Errors:** {len(data['errors'])}
- **Warnings:** {len(data['warnings'])}
"""
        return report
