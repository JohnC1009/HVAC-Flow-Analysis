"""
HVAC Calculators - Backend Calculation Logic

This module provides engineering calculations for:
1. Conduit Fill (NEC)
2. Pipe Sizing (ASHRAE)
3. Duct Pressure Drop (SMACNA)
4. Fan Laws (AMCA)
5. Pump Laws (Hydraulic Institute)

All calculations use Decimal precision for accuracy.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Union
import math


class HvacCalculatorError(Exception):
    """Base exception for HVAC calculator errors."""
    pass


class ValidationError(HvacCalculatorError):
    """Raised when input validation fails."""
    pass


class CalculationError(HvacCalculatorError):
    """Raised when a calculation fails."""
    pass


def _validate_positive(value: Union[int, float, Decimal], name: str) -> Decimal:
    """Validate that a value is positive."""
    d = Decimal(str(value))
    if d <= 0:
        raise ValidationError(f"{name} must be positive, got {value}")
    return d


def _validate_non_negative(value: Union[int, float, Decimal], name: str) -> Decimal:
    """Validate that a value is non-negative."""
    d = Decimal(str(value))
    if d < 0:
        raise ValidationError(f"{name} must be non-negative, got {value}")
    return d


def _round_result(value: Decimal, places: int = 2) -> float:
    """Round a Decimal to specified places and return as float."""
    quantize_str = '0.' + '0' * places
    return float(value.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP))


# ============================================================================
# 1. CONDUIT FILL CALCULATOR (NEC)
# ============================================================================

def calculate_conduit_fill(
    conduit_type: str,
    conduit_size: float,
    wire_gauge: int,
    num_wires: int,
    insulation_type: str = "THHN"
) -> Dict[str, Any]:
    """
    Calculate conduit fill percentage per NEC Chapter 9, Table 1.
    
    NEC allows:
    - 1 wire: 53% fill
    - 2 wires: 31% fill
    - 3+ wires: 40% fill
    
    Args:
        conduit_type: Type of conduit ("RMC", "EMT", "PVC", "Flex")
        conduit_size: Conduit size in inches (0.5, 0.75, 1, 1.25, 1.5, 2, etc.)
        wire_gauge: AWG wire size (14, 12, 10, 8, 6, 4, 2, 1, 1/0, 2/0, etc.)
        num_wires: Number of conductors
        insulation_type: Insulation type (THHN, THWN, XHHW, etc.)
    
    Returns:
        Dictionary with fill_percentage, max_wires, status, and details
    """
    # Validate inputs
    conduit_size_d = _validate_positive(conduit_size, "Conduit size")
    num_wires_d = _validate_positive(num_wires, "Number of wires")
    wire_gauge_d = _validate_positive(wire_gauge, "Wire gauge")
    
    # NEC conduit internal areas (simplified - in sq inches)
    conduit_areas = {
        "RMC": {0.5: 0.161, 0.75: 0.213, 1: 0.346, 1.25: 0.533, 1.5: 0.684, 2: 1.174, 2.5: 1.610, 3: 2.343, 4: 4.084},
        "EMT": {0.5: 0.122, 0.75: 0.213, 1: 0.346, 1.25: 0.533, 1.5: 0.684, 2: 1.174, 2.5: 1.610, 3: 2.343, 4: 4.084},
        "PVC": {0.5: 0.161, 0.75: 0.213, 1: 0.346, 1.25: 0.533, 1.5: 0.684, 2: 1.174, 2.5: 1.610, 3: 2.343, 4: 4.084},
        "Flex": {0.5: 0.161, 0.75: 0.213, 1: 0.346, 1.25: 0.533, 1.5: 0.684, 2: 1.174, 2.5: 1.610, 3: 2.343, 4: 4.084},
    }
    
    # Wire areas including insulation (simplified - in sq inches)
    # THHN wire areas by AWG
    wire_areas_thhn = {
        14: 0.0097, 12: 0.0133, 10: 0.0211, 8: 0.0366, 6: 0.0594,
        4: 0.0973, 3: 0.1153, 2: 0.1343, 1: 0.1563,
        "1/0": 0.1843, "2/0": 0.2223, "3/0": 0.2673, "4/0": 0.3233,
        250: 0.3523, 300: 0.4233, 350: 0.4943, 400: 0.5653, 500: 0.7073,
    }
    
    # Get conduit area
    conduit_type_upper = conduit_type.upper()
    if conduit_type_upper not in conduit_areas:
        raise ValidationError(f"Unknown conduit type: {conduit_type}")
    
    conduit_area = conduit_areas[conduit_type_upper].get(float(conduit_size_d))
    if conduit_area is None:
        raise ValidationError(f"Unknown conduit size {conduit_size} for {conduit_type}")
    
    # Get wire area
    wire_key = wire_gauge if wire_gauge in wire_areas_thhn else str(wire_gauge)
    if wire_key not in wire_areas_thhn:
        raise ValidationError(f"Unknown wire gauge: {wire_gauge}")
    
    wire_area = wire_areas_thhn[wire_key]
    
    # Calculate fill
    total_wire_area = Decimal(str(wire_area)) * num_wires_d
    conduit_area_d = Decimal(str(conduit_area))
    fill_percentage = (total_wire_area / conduit_area_d) * 100
    
    # NEC fill limits based on number of wires
    if num_wires == 1:
        max_fill = 53
    elif num_wires == 2:
        max_fill = 31
    else:
        max_fill = 40
    
    # Determine status
    if fill_percentage <= max_fill:
        status = "PASS"
        status_detail = f"Within NEC limit ({max_fill}%)"
    else:
        status = "FAIL"
        status_detail = f"Exceeds NEC limit ({max_fill}%)"
    
    # Calculate max wires allowed
    max_wire_area = conduit_area_d * Decimal(str(max_fill)) / 100
    max_wires = int(max_wire_area / Decimal(str(wire_area)))
    
    return {
        "fill_percentage": _round_result(fill_percentage, 2),
        "max_fill_percentage": max_fill,
        "max_wires": max_wires,
        "num_wires": num_wires,
        "conduit_type": conduit_type_upper,
        "conduit_size": float(conduit_size_d),
        "wire_gauge": wire_gauge,
        "insulation_type": insulation_type,
        "status": status,
        "status_detail": status_detail,
        "total_wire_area_sq_in": _round_result(total_wire_area, 4),
        "conduit_area_sq_in": _round_result(conduit_area_d, 4),
    }


# ============================================================================
# 2. PIPE SIZING CALCULATOR (ASHRAE)
# ============================================================================

def calculate_pipe_sizing(
    flow_rate_gpm: float,
    pipe_material: str = "CU",
    max_velocity_fps: float = 8.0,
    max_pressure_drop: float = 4.0
) -> Dict[str, Any]:
    """
    Calculate pipe sizing per ASHRAE fundamentals.
    
    Args:
        flow_rate_gpm: Flow rate in gallons per minute
        pipe_material: Pipe material ("CU" for copper, "STEEL", "PVC")
        max_velocity_fps: Maximum recommended velocity in feet per second
        max_pressure_drop: Maximum pressure drop in feet of water per 100 ft
    
    Returns:
        Dictionary with recommended_size, velocity, pressure_drop, and status
    """
    # Validate inputs
    flow_rate = _validate_positive(flow_rate_gpm, "Flow rate")
    max_velocity = _validate_positive(max_velocity_fps, "Max velocity")
    max_dp = _validate_positive(max_pressure_drop, "Max pressure drop")
    
    # Standard pipe sizes (NPS) with internal diameters in inches
    pipe_sizes = {
        "1/2": 0.622, "3/4": 0.824, "1": 1.049, "1.25": 1.380, "1.5": 1.610,
        "2": 2.067, "2.5": 2.469, "3": 3.068, "4": 4.026, "5": 5.047,
        "6": 6.065, "8": 7.981, "10": 10.020, "12": 11.938,
    }
    
    # Friction factors by material (simplified Hazen-Williams C values)
    friction_factors = {
        "CU": 140,      # Copper
        "STEEL": 120,   # Steel
        "PVC": 150,     # PVC
    }
    
    material = pipe_material.upper()
    if material not in friction_factors:
        raise ValidationError(f"Unknown pipe material: {pipe_material}")
    
    C = friction_factors[material]
    
    # Convert GPM to cubic feet per second
    # 1 GPM = 0.002228 cfs
    flow_cfs = flow_rate * Decimal("0.002228")
    
    best_size = None
    best_velocity: float = 0.0
    best_dp: float = 0.0
    results = []
    
    for size, id_inches in pipe_sizes.items():
        # Calculate area in sq ft
        id_ft = Decimal(str(id_inches)) / 12
        area_sqft = (Decimal(str(math.pi)) / 4) * (id_ft ** 2)
        
        # Calculate velocity: V = Q / A
        velocity = flow_cfs / area_sqft
        
        # Calculate pressure drop using Hazen-Williams:
        # hf = 10.44 * L * Q^1.85 / (C^1.85 * d^4.87)
        # For 100 ft: hf/100ft = 10.44 * Q^1.85 / (C^1.85 * d^4.87)
        Q = float(flow_rate)  # GPM
        d = id_inches  # inches
        
        dp_per_100ft = (10.44 * (Q ** 1.85)) / ((C ** 1.85) * (d ** 4.87))
        
        velocity_float = _round_result(velocity, 2)
        dp_float = _round_result(Decimal(str(dp_per_100ft)), 2)
        
        result = {
            "size": size,
            "internal_diameter_in": id_inches,
            "velocity_fps": velocity_float,
            "pressure_drop_ft_per_100ft": dp_float,
        }
        results.append(result)
        
        # Check if this size meets criteria
        if velocity <= max_velocity and dp_per_100ft <= max_dp:
            if best_size is None:
                best_size = size
                best_velocity = velocity_float
                best_dp = dp_float
    
    # If no size meets criteria, pick the largest
    if best_size is None:
        largest = results[-1]
        best_size = largest["size"]
        best_velocity = largest["velocity_fps"]
        best_dp = largest["pressure_drop_ft_per_100ft"]
    
    # Determine status
    max_vel_float = float(max_velocity)
    max_dp_float = float(max_dp)
    if best_velocity <= max_vel_float and best_dp <= max_dp_float:
        status = "PASS"
        status_detail = "Meets ASHRAE velocity and pressure drop criteria"
    else:
        status = "WARNING"
        reasons = []
        if best_velocity > max_vel_float:
            reasons.append(f"Velocity {best_velocity} fps exceeds {max_vel_float} fps")
        if best_dp > max_dp_float:
            reasons.append(f"Pressure drop {best_dp} ft/100ft exceeds {max_dp_float} ft/100ft")
        status_detail = "; ".join(reasons)
    
    return {
        "recommended_size": best_size,
        "velocity_fps": best_velocity,
        "pressure_drop_ft_per_100ft": best_dp,
        "max_velocity_fps": float(max_velocity),
        "max_pressure_drop_ft_per_100ft": float(max_dp),
        "flow_rate_gpm": float(flow_rate),
        "pipe_material": material,
        "status": status,
        "status_detail": status_detail,
        "all_sizes": results,
    }


# ============================================================================
# 3. DUCT PRESSURE DROP CALCULATOR (SMACNA)
# ============================================================================

def calculate_duct_pressure_drop(
    airflow_cfm: float,
    duct_width_in: float,
    duct_height_in: float,
    duct_material: str = "galvanized",
    length_ft: float = 100.0
) -> Dict[str, Any]:
    """
    Calculate duct pressure drop per SMACNA HVAC Duct Construction Standards.
    
    Args:
        airflow_cfm: Airflow in cubic feet per minute
        duct_width_in: Duct width in inches
        duct_height_in: Duct height in inches
        duct_material: Duct material ("galvanized", "aluminum", "fiberglass")
        length_ft: Duct length in feet
    
    Returns:
        Dictionary with pressure_drop, velocity, equivalent_diameter, and status
    """
    # Validate inputs
    airflow = _validate_positive(airflow_cfm, "Airflow")
    width = _validate_positive(duct_width_in, "Duct width")
    height = _validate_positive(duct_height_in, "Duct height")
    length = _validate_positive(length_ft, "Duct length")
    
    # Calculate equivalent diameter for rectangular duct
    # Huebscher equation: De = 1.30 * (a*b)^0.625 / (a+b)^0.25
    a = float(width)
    b = float(height)
    equivalent_diameter = 1.30 * ((a * b) ** 0.625) / ((a + b) ** 0.25)
    
    # Calculate duct area and velocity
    area_sqft = (a * b) / 144  # sq ft
    velocity_fpm = float(airflow) / area_sqft
    velocity_fps = velocity_fpm / 60
    
    # Friction rate (pressure drop per 100 ft) using Darcy-Weisbach simplified
    # For standard air and galvanized duct:
    # friction = 0.109136 * (CFM^1.9) / (De^5.02)
    # This is a simplified version of the Colebrook equation
    
    De = equivalent_diameter
    Q = float(airflow)
    
    # Material roughness factors
    roughness_factors = {
        "galvanized": 1.0,
        "aluminum": 0.95,
        "fiberglass": 1.3,
    }
    
    material_factor = roughness_factors.get(duct_material.lower(), 1.0)
    
    # Friction rate per 100 ft (inches of water)
    friction_rate = 0.109136 * (Q ** 1.9) / (De ** 5.02) * material_factor
    
    # Total pressure drop
    total_dp = friction_rate * (float(length) / 100)
    
    # Velocity pressure: Pv = (V/4005)^2
    velocity_pressure = (velocity_fpm / 4005) ** 2
    
    # Check against typical design criteria
    # Typical: 0.1 in w.g. per 100 ft for low velocity, 0.08 for medium
    if friction_rate <= 0.1:
        status = "PASS"
        status_detail = "Within low-velocity design criteria (≤0.1 in w.g./100ft)"
    elif friction_rate <= 0.2:
        status = "ACCEPTABLE"
        status_detail = "Within medium-velocity design criteria (≤0.2 in w.g./100ft)"
    else:
        status = "HIGH"
        status_detail = f"High velocity design - {friction_rate:.2f} in w.g./100ft"
    
    return {
        "pressure_drop_in_wg": _round_result(Decimal(str(total_dp)), 3),
        "friction_rate_in_wg_per_100ft": _round_result(Decimal(str(friction_rate)), 3),
        "velocity_fpm": _round_result(Decimal(str(velocity_fpm)), 0),
        "velocity_fps": _round_result(Decimal(str(velocity_fps)), 1),
        "velocity_pressure_in_wg": _round_result(Decimal(str(velocity_pressure)), 3),
        "equivalent_diameter_in": _round_result(Decimal(str(equivalent_diameter)), 2),
        "duct_area_sqft": _round_result(Decimal(str(area_sqft)), 2),
        "airflow_cfm": float(airflow),
        "duct_dimensions": f"{width}x{height} inches",
        "duct_material": duct_material,
        "length_ft": float(length),
        "status": status,
        "status_detail": status_detail,
    }


# ============================================================================
# 4. FAN LAWS CALCULATOR (AMCA)
# ============================================================================

def calculate_fan_laws(
    cfm_1: float,
    rpm_1: float,
    bhp_1: float,
    cfm_2: float = None,
    rpm_2: float = None,
    calculation_type: str = "cfm"
) -> Dict[str, Any]:
    """
    Calculate fan performance using AMCA Fan Laws.
    
    Fan Law 1: CFM ∝ RPM
    Fan Law 2: SP ∝ RPM²
    Fan Law 3: BHP ∝ RPM³
    
    Args:
        cfm_1: Known airflow at condition 1
        rpm_1: Known fan speed at condition 1
        bhp_1: Known brake horsepower at condition 1
        cfm_2: Target airflow (if calculation_type='cfm')
        rpm_2: Target RPM (if calculation_type='rpm')
        calculation_type: 'cfm' to find new RPM/BHP, or 'rpm' to find new CFM/BHP
    
    Returns:
        Dictionary with new operating conditions and fan law results
    """
    # Validate inputs
    cfm_1_d = _validate_positive(cfm_1, "CFM at condition 1")
    rpm_1_d = _validate_positive(rpm_1, "RPM at condition 1")
    bhp_1_d = _validate_non_negative(bhp_1, "BHP at condition 1")
    
    calc_type = calculation_type.lower()
    if calc_type not in ["cfm", "rpm"]:
        raise ValidationError("calculation_type must be 'cfm' or 'rpm'")
    
    if calc_type == "cfm":
        if cfm_2 is None:
            raise ValidationError("cfm_2 required when calculation_type='cfm'")
        cfm_2_d = _validate_positive(cfm_2, "Target CFM")
        
        # Fan Law 1: RPM2 = RPM1 * (CFM2 / CFM1)
        rpm_2 = rpm_1_d * (cfm_2_d / cfm_1_d)
        
        # Fan Law 2: SP2 = SP1 * (RPM2 / RPM1)² (we don't have SP1, so skip)
        # Fan Law 3: BHP2 = BHP1 * (RPM2 / RPM1)³
        bhp_2 = bhp_1_d * ((rpm_2 / rpm_1_d) ** 3)
        
        cfm_2_result = float(cfm_2_d)
        rpm_2_result = _round_result(rpm_2, 0)
        bhp_2_result = _round_result(bhp_2, 2)
        
    else:  # calc_type == "rpm"
        if rpm_2 is None:
            raise ValidationError("rpm_2 required when calculation_type='rpm'")
        rpm_2_d = _validate_positive(rpm_2, "Target RPM")
        
        # Fan Law 1: CFM2 = CFM1 * (RPM2 / RPM1)
        cfm_2 = cfm_1_d * (rpm_2_d / rpm_1_d)
        
        # Fan Law 3: BHP2 = BHP1 * (RPM2 / RPM1)³
        bhp_2 = bhp_1_d * ((rpm_2_d / rpm_1_d) ** 3)
        
        cfm_2_result = _round_result(cfm_2, 0)
        rpm_2_result = float(rpm_2_d)
        bhp_2_result = _round_result(bhp_2, 2)
    
    # Calculate ratios
    rpm_1_float = float(rpm_1_d)
    cfm_1_float = float(cfm_1_d)
    rpm_ratio = rpm_2_result / rpm_1_float if calc_type == "cfm" else float(rpm_2_d) / rpm_1_float
    cfm_ratio = cfm_2_result / cfm_1_float
    bhp_ratio = bhp_2_result / float(bhp_1_d) if bhp_1_d > 0 else 0
    
    # Efficiency note
    efficiency_note = "Fan laws assume constant efficiency. Actual performance may vary."
    if rpm_ratio > 1.25:
        efficiency_note += " WARNING: Large speed increases may reduce fan efficiency."
    elif rpm_ratio < 0.75:
        efficiency_note += " WARNING: Large speed decreases may affect fan stability."
    
    return {
        "condition_1": {
            "cfm": float(cfm_1_d),
            "rpm": float(rpm_1_d),
            "bhp": float(bhp_1_d),
        },
        "condition_2": {
            "cfm": cfm_2_result,
            "rpm": rpm_2_result,
            "bhp": bhp_2_result,
        },
        "ratios": {
            "rpm_ratio": _round_result(Decimal(str(rpm_ratio)), 3),
            "cfm_ratio": _round_result(Decimal(str(cfm_ratio)), 3),
            "bhp_ratio": _round_result(Decimal(str(bhp_ratio)), 3),
        },
        "calculation_type": calc_type,
        "efficiency_note": efficiency_note,
        "fan_laws_applied": ["CFM ∝ RPM", "SP ∝ RPM²", "BHP ∝ RPM³"],
    }


# ============================================================================
# 5. PUMP LAWS CALCULATOR (Hydraulic Institute)
# ============================================================================

def calculate_pump_laws(
    gpm_1: float,
    rpm_1: float,
    head_1: float,
    bhp_1: float,
    gpm_2: float = None,
    rpm_2: float = None,
    calculation_type: str = "gpm"
) -> Dict[str, Any]:
    """
    Calculate pump performance using Hydraulic Institute Pump Laws (Affinity Laws).
    
    Pump Law 1: GPM ∝ RPM
    Pump Law 2: Head ∝ RPM²
    Pump Law 3: BHP ∝ RPM³
    
    Args:
        gpm_1: Known flow rate at condition 1
        rpm_1: Known pump speed at condition 1
        head_1: Known head at condition 1 (feet)
        bhp_1: Known brake horsepower at condition 1
        gpm_2: Target flow rate (if calculation_type='gpm')
        rpm_2: Target RPM (if calculation_type='rpm')
        calculation_type: 'gpm' to find new RPM/Head/BHP, or 'rpm' to find new GPM/Head/BHP
    
    Returns:
        Dictionary with new operating conditions and pump affinity law results
    """
    # Validate inputs
    gpm_1_d = _validate_positive(gpm_1, "GPM at condition 1")
    rpm_1_d = _validate_positive(rpm_1, "RPM at condition 1")
    head_1_d = _validate_positive(head_1, "Head at condition 1")
    bhp_1_d = _validate_non_negative(bhp_1, "BHP at condition 1")
    
    calc_type = calculation_type.lower()
    if calc_type not in ["gpm", "rpm"]:
        raise ValidationError("calculation_type must be 'gpm' or 'rpm'")
    
    if calc_type == "gpm":
        if gpm_2 is None:
            raise ValidationError("gpm_2 required when calculation_type='gpm'")
        gpm_2_d = _validate_positive(gpm_2, "Target GPM")
        
        # Pump Law 1: RPM2 = RPM1 * (GPM2 / GPM1)
        rpm_2 = rpm_1_d * (gpm_2_d / gpm_1_d)
        
        # Pump Law 2: Head2 = Head1 * (RPM2 / RPM1)²
        head_2 = head_1_d * ((rpm_2 / rpm_1_d) ** 2)
        
        # Pump Law 3: BHP2 = BHP1 * (RPM2 / RPM1)³
        bhp_2 = bhp_1_d * ((rpm_2 / rpm_1_d) ** 3)
        
        gpm_2_result = float(gpm_2_d)
        rpm_2_result = _round_result(rpm_2, 0)
        head_2_result = _round_result(head_2, 1)
        bhp_2_result = _round_result(bhp_2, 2)
        
    else:  # calc_type == "rpm"
        if rpm_2 is None:
            raise ValidationError("rpm_2 required when calculation_type='rpm'")
        rpm_2_d = _validate_positive(rpm_2, "Target RPM")
        
        # Pump Law 1: GPM2 = GPM1 * (RPM2 / RPM1)
        gpm_2 = gpm_1_d * (rpm_2_d / rpm_1_d)
        
        # Pump Law 2: Head2 = Head1 * (RPM2 / RPM1)²
        head_2 = head_1_d * ((rpm_2_d / rpm_1_d) ** 2)
        
        # Pump Law 3: BHP2 = BHP1 * (RPM2 / RPM1)³
        bhp_2 = bhp_1_d * ((rpm_2_d / rpm_1_d) ** 3)
        
        gpm_2_result = _round_result(gpm_2, 0)
        rpm_2_result = float(rpm_2_d)
        head_2_result = _round_result(head_2, 1)
        bhp_2_result = _round_result(bhp_2, 2)
    
    # Calculate ratios
    rpm_1_float = float(rpm_1_d)
    gpm_1_float = float(gpm_1_d)
    head_1_float = float(head_1_d)
    rpm_ratio = rpm_2_result / rpm_1_float if calc_type == "gpm" else float(rpm_2_d) / rpm_1_float
    gpm_ratio = gpm_2_result / gpm_1_float
    head_ratio = head_2_result / head_1_float
    bhp_ratio = bhp_2_result / float(bhp_1_d) if bhp_1_d > 0 else 0
    
    # Efficiency note
    efficiency_note = "Pump laws assume constant efficiency and impeller diameter."
    if rpm_ratio > 1.2:
        efficiency_note += " WARNING: Speed increases >20% may exceed pump design limits."
    elif rpm_ratio < 0.8:
        efficiency_note += " WARNING: Speed decreases >20% may affect pump efficiency."
    
    # Check NPSH (simplified - actual NPSH would require more data)
    npsh_note = "Note: Verify NPSH available exceeds NPSH required at new condition."
    
    return {
        "condition_1": {
            "gpm": float(gpm_1_d),
            "rpm": float(rpm_1_d),
            "head_ft": float(head_1_d),
            "bhp": float(bhp_1_d),
        },
        "condition_2": {
            "gpm": gpm_2_result,
            "rpm": rpm_2_result,
            "head_ft": head_2_result,
            "bhp": bhp_2_result,
        },
        "ratios": {
            "rpm_ratio": _round_result(Decimal(str(rpm_ratio)), 3),
            "gpm_ratio": _round_result(Decimal(str(gpm_ratio)), 3),
            "head_ratio": _round_result(Decimal(str(head_ratio)), 3),
            "bhp_ratio": _round_result(Decimal(str(bhp_ratio)), 3),
        },
        "calculation_type": calc_type,
        "efficiency_note": efficiency_note,
        "npsh_note": npsh_note,
        "pump_laws_applied": ["GPM ∝ RPM", "Head ∝ RPM²", "BHP ∝ RPM³"],
    }


# ============================================================================
# API INTERFACE
# ============================================================================

def calculate(calculator_type: str, **kwargs) -> Dict[str, Any]:
    """
    Unified calculation interface.
    
    Args:
        calculator_type: One of 'conduit', 'pipe', 'duct', 'fan', 'pump'
        **kwargs: Parameters specific to each calculator
    
    Returns:
        Calculation result dictionary
    """
    calculators = {
        "conduit": calculate_conduit_fill,
        "pipe": calculate_pipe_sizing,
        "duct": calculate_duct_pressure_drop,
        "fan": calculate_fan_laws,
        "pump": calculate_pump_laws,
    }
    
    if calculator_type.lower() not in calculators:
        raise ValidationError(
            f"Unknown calculator type: {calculator_type}. "
            f"Valid types: {', '.join(calculators.keys())}"
        )
    
    calculator_func = calculators[calculator_type.lower()]
    return calculator_func(**kwargs)


# Module exports
__all__ = [
    "HvacCalculatorError",
    "ValidationError",
    "CalculationError",
    "calculate_conduit_fill",
    "calculate_pipe_sizing",
    "calculate_duct_pressure_drop",
    "calculate_fan_laws",
    "calculate_pump_laws",
    "calculate",
]
