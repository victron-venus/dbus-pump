"""Normalize one authoritative tank measurement into a percentage.

The same percentage feeds the D-Bus level, remaining volume and controller.
Geometry describes a vertical cylinder; all lengths are centimetres.
"""

import math
from typing import Any


def finite_number(value: Any) -> float | None:
    """Return a finite measurement, rejecting booleans and absent values."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def validate_geometry(unit: str, capacity_liters: float, offset_cm: float, radius_cm: float):
    """Reject ambiguous units and unusable geometry before publishing values."""
    if unit not in ("%", "cm"):
        raise ValueError("HA_WATER_LEVEL_UNIT must be '%' or 'cm'")
    if finite_number(capacity_liters) is None or capacity_liters < 0:
        raise ValueError("TANK_CAPACITY_LITERS must be finite and nonnegative")
    if unit == "cm" and (
        capacity_liters <= 0
        or finite_number(offset_cm) is None
        or finite_number(radius_cm) is None
        or radius_cm <= 0
    ):
        raise ValueError(
            "cm levels require positive finite TANK_CAPACITY_LITERS and TANK_RADIUS_CM "
            "and finite TANK_OFFSET_CM"
        )


def normalize_level(
    value: Any,
    unit: str,
    capacity_liters: float,
    offset_cm: float,
    radius_cm: float,
    reported_unit: Any = None,
) -> float | None:
    """Convert to 0..100%, or reject invalid data without inventing a level.

    HA metadata is a consistency check, not implicit unit selection. Sources
    without metadata use the explicit configured unit. A secondary cm sensor
    never overrides or rescues the authoritative measurement.
    """
    try:
        validate_geometry(unit, capacity_liters, offset_cm, radius_cm)
    except ValueError:
        return None
    if reported_unit is not None and str(reported_unit).strip() not in ("", unit):
        return None
    level = finite_number(value)
    if level is None:
        return None
    if unit == "cm":
        # Multiplication (not exponentiation) lets extreme finite inputs become
        # inf, which is explicitly rejected instead of raising OverflowError.
        liters = (level - offset_cm) * math.pi * radius_cm * radius_cm / 1000.0
        level = finite_number(liters / capacity_liters * 100.0)
        if level is None:
            return None
    return max(0.0, min(100.0, level))
