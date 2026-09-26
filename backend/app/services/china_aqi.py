"""HJ 633—2026 realtime breakpoint estimate, not official station AQI.

Inputs are same-hour modelled concentrations in µg/m³ (including raw CO).
The standard's hourly concentration basis is approximated by Open-Meteo's
hourly instantaneous model output, not a verified monitoring-hour average.
See docs/CHINA_AQI.md for the standard, units and missingness policy.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
import math

IAQI = (0, 50, 100, 150, 200, 300, 400, 500)
# CO breakpoints alone are mg/m³; its input is converted exactly once below.
BREAKPOINTS = {
    "pm2_5": (0, 35, 60, 115, 150, 250, 350, 500),
    "pm10": (0, 50, 120, 250, 350, 420, 500, 600),
    "nitrogen_dioxide": (0, 100, 200, 700, 1200, 2340, 3090, 3840),
    "sulfur_dioxide": (0, 150, 500, 650, 800),
    "carbon_monoxide": (0, 5, 10, 35, 60, 90, 120, 150),
    "ozone": (0, 160, 200, 300, 400, 800, 1000, 1200),
}
POLLUTANTS = tuple(BREAKPOINTS)
LABELS = dict(zip(POLLUTANTS, ("PM2.5", "PM10", "NO2", "SO2", "CO", "O3")))


def pollutant_iaqi(pollutant: str, concentration: float | None) -> int | None:
    """Interpolate, round upward, and cap; missing/invalid is never zero."""
    breakpoints = BREAKPOINTS[pollutant]
    if isinstance(concentration, bool) or not isinstance(concentration, (int, float)):
        return None
    try:
        if not math.isfinite(concentration) or concentration < 0:
            return None
    except OverflowError:
        return None
    value = Decimal(str(concentration))
    if pollutant == "carbon_monoxide":
        value /= 1000  # Open-Meteo µg/m³ -> HJ 633 CO mg/m³.
    if value >= breakpoints[-1]:
        # HJ 633—2026 table 1 note: hourly SO2 above 800 has IAQI 200.
        return 200 if pollutant == "sulfur_dioxide" else 500
    for i, high in enumerate(breakpoints[1:], 1):
        if value <= high:
            low = breakpoints[i - 1]
            index = Decimal(IAQI[i - 1]) + (value - low) * (IAQI[i] - IAQI[i - 1]) / (high - low)
            return int(index.to_integral_value(rounding=ROUND_CEILING))
    raise AssertionError("Unreachable breakpoint interval")


@dataclass(frozen=True)
class ChinaAQIEstimate:
    aqi: int | None
    primary_pollutant: str | None
    iaqi: dict[str, int | None]


def calculate_china_aqi(*, pm2_5=None, pm10=None, nitrogen_dioxide=None,
                        sulfur_dioxide=None, carbon_monoxide=None, ozone=None) -> ChinaAQIEstimate:
    """Require all six pollutants; partial raw data remain usable independently."""
    concentrations = dict(zip(POLLUTANTS, (pm2_5, pm10, nitrogen_dioxide, sulfur_dioxide, carbon_monoxide, ozone)))
    indices = {key: pollutant_iaqi(key, value) for key, value in concentrations.items()}
    if any(value is None for value in indices.values()):
        return ChinaAQIEstimate(None, None, indices)
    aqi = max(indices.values())
    primary = ", ".join(LABELS[key] for key, value in indices.items() if value == aqi) if aqi > 50 else None
    return ChinaAQIEstimate(aqi, primary, indices)
