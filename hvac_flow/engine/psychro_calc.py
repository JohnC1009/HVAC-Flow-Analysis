"""Facade over psychrolib providing typed AirState construction.

This is the only module that imports psychrolib directly, making it
straightforward to swap the underlying library in the future.
"""

import psychrolib

from hvac_flow.engine.air_state import AirState
from hvac_flow.engine.constants import UnitSystem, STD_ATM_PRESSURE_IP, STD_ATM_PRESSURE_SI


class PsychroCalc:
    """Psychrometric calculation engine.

    All factory methods return a fully-resolved AirState.
    """

    def __init__(self, unit_system: UnitSystem = UnitSystem.IP,
                 pressure: float = None):
        self._unit_system = unit_system

        if pressure is None:
            pressure = (STD_ATM_PRESSURE_IP if unit_system == UnitSystem.IP
                        else STD_ATM_PRESSURE_SI)
        self._pressure = pressure

        if unit_system == UnitSystem.IP:
            psychrolib.SetUnitSystem(psychrolib.IP)
        else:
            psychrolib.SetUnitSystem(psychrolib.SI)

    @property
    def unit_system(self) -> UnitSystem:
        return self._unit_system

    @property
    def pressure(self) -> float:
        return self._pressure

    # ── Factory methods ──────────────────────────────────────────────

    def from_db_rh(self, dry_bulb: float, rel_hum: float,
                   label: str = None) -> AirState:
        """Create AirState from dry-bulb temperature and relative humidity (0-1)."""
        hr, wb, dp, _vp, h, v, _dos = psychrolib.CalcPsychrometricsFromRelHum(
            dry_bulb, rel_hum, self._pressure
        )
        return AirState(
            dry_bulb=dry_bulb, humidity_ratio=hr,
            relative_humidity=rel_hum, wet_bulb=wb, dew_point=dp,
            enthalpy=h, specific_volume=v, pressure=self._pressure,
            label=label,
        )

    def from_db_wb(self, dry_bulb: float, wet_bulb: float,
                   label: str = None) -> AirState:
        """Create AirState from dry-bulb and wet-bulb temperatures."""
        # CalcPsychrometricsFromTWetBulb returns:
        # (HumRatio, TDewPoint, RelHum, VapPres, MoistAirEnthalpy,
        #  MoistAirVolume, DegreeOfSaturation)
        result = psychrolib.CalcPsychrometricsFromTWetBulb(
            dry_bulb, wet_bulb, self._pressure
        )
        return AirState(
            dry_bulb=dry_bulb, humidity_ratio=result[0],
            relative_humidity=result[2], wet_bulb=wet_bulb, dew_point=result[1],
            enthalpy=result[4], specific_volume=result[5],
            pressure=self._pressure, label=label,
        )

    def from_db_dp(self, dry_bulb: float, dew_point: float,
                   label: str = None) -> AirState:
        """Create AirState from dry-bulb and dew-point temperatures."""
        result = psychrolib.CalcPsychrometricsFromTDewPoint(
            dry_bulb, dew_point, self._pressure
        )
        # Returns: (HumRatio, TWetBulb, RelHum, VapPres, MoistAirEnthalpy,
        #           MoistAirVolume, DegreeOfSaturation)
        return AirState(
            dry_bulb=dry_bulb, humidity_ratio=result[0],
            relative_humidity=result[2], wet_bulb=result[1],
            dew_point=dew_point, enthalpy=result[4], specific_volume=result[5],
            pressure=self._pressure, label=label,
        )

    def from_db_w(self, dry_bulb: float, hum_ratio: float,
                  label: str = None) -> AirState:
        """Create AirState from dry-bulb and humidity ratio."""
        rh = psychrolib.GetRelHumFromHumRatio(
            dry_bulb, hum_ratio, self._pressure
        )
        wb = psychrolib.GetTWetBulbFromHumRatio(
            dry_bulb, hum_ratio, self._pressure
        )
        dp = psychrolib.GetTDewPointFromHumRatio(
            dry_bulb, hum_ratio, self._pressure
        )
        h = psychrolib.GetMoistAirEnthalpy(dry_bulb, hum_ratio)
        v = psychrolib.GetMoistAirVolume(dry_bulb, hum_ratio, self._pressure)
        return AirState(
            dry_bulb=dry_bulb, humidity_ratio=hum_ratio,
            relative_humidity=rh, wet_bulb=wb, dew_point=dp,
            enthalpy=h, specific_volume=v, pressure=self._pressure,
            label=label,
        )

    def from_enthalpy_w(self, enthalpy: float, hum_ratio: float,
                        label: str = None) -> AirState:
        """Create AirState from enthalpy and humidity ratio (used for mixing)."""
        db = psychrolib.GetTDryBulbFromEnthalpyAndHumRatio(enthalpy, hum_ratio)
        return self.from_db_w(db, hum_ratio, label=label)

    # ── Utility ──────────────────────────────────────────────────────

    def get_saturation_humidity_ratio(self, dry_bulb: float) -> float:
        """Return the saturation humidity ratio at the given dry-bulb temp."""
        return psychrolib.GetSatHumRatio(dry_bulb, self._pressure)

    def get_moist_air_density(self, state: AirState) -> float:
        """Return the density of moist air for the given state."""
        return psychrolib.GetMoistAirDensity(
            state.dry_bulb, state.humidity_ratio, self._pressure
        )

    def get_humidity_ratio_from_rh(self, dry_bulb: float,
                                   rel_hum: float) -> float:
        """Return humidity ratio given dry-bulb and relative humidity."""
        return psychrolib.GetHumRatioFromRelHum(
            dry_bulb, rel_hum, self._pressure
        )

    def get_humidity_ratio_from_twetbulb(self, dry_bulb: float,
                                         wet_bulb: float) -> float:
        """Return humidity ratio given dry-bulb and wet-bulb temperatures."""
        return psychrolib.GetHumRatioFromTWetBulb(
            dry_bulb, wet_bulb, self._pressure
        )
