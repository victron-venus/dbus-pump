"""Configuration.

Real values live in local_config.py at the repo root (gitignored).
Falls back to safe defaults when it is missing.
"""

import logging
import os

from dbus_pump.tank import finite_number, validate_geometry

logger = logging.getLogger(__name__)

try:
    import local_config  # type: ignore
except ImportError:
    local_config = None  # type: ignore
    logger.warning("local_config.py not found - using defaults/example values")


def _get(name: str, default):
    if local_config is not None and hasattr(local_config, name):
        return getattr(local_config, name)
    return default


def _read_version() -> str:
    try:
        with open(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "version")
        ) as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


# --- Home Assistant -----------------------------------------------------------
HA_URL: str = str(_get("HA_URL", "")).rstrip("/")
HA_TOKEN: str = str(_get("HA_TOKEN", ""))
HA_WATER_LEVEL_ENTITY: str = str(_get("HA_WATER_LEVEL_ENTITY", ""))
HA_WATER_LEVEL_UNIT: str = str(_get("HA_WATER_LEVEL_UNIT", "%")).strip()
HA_PUMP_SWITCH_ENTITY: str = str(_get("HA_PUMP_SWITCH_ENTITY", ""))
HA_VALVE_SWITCH_ENTITY: str = str(_get("HA_VALVE_SWITCH_ENTITY", ""))

# --- Tank geometry ------------------------------------------------------------
# /Capacity comes from config. In cm mode, the authoritative level converts to
# volume and percentage using a vertical cylinder:
#   liters = (cm - TANK_OFFSET_CM) * pi * TANK_RADIUS_CM^2 / 1000
TANK_CAPACITY_LITERS: float = float(_get("TANK_CAPACITY_LITERS", 0.0))
TANK_WATER_CM_ENTITY: str = str(_get("TANK_WATER_CM_ENTITY", ""))  # diagnostic only
TANK_OFFSET_CM: float = float(_get("TANK_OFFSET_CM", 0.0))  # sensor reading at empty tank
TANK_RADIUS_CM: float = float(_get("TANK_RADIUS_CM", 0.0))

# --- D-Bus identity -----------------------------------------------------------
DEVICE_INSTANCE_TANK: int = int(_get("DEVICE_INSTANCE_TANK", 21))
PUMP_STARTSTOP_INSTANCE: int = int(_get("PUMP_STARTSTOP_INSTANCE", 1))
VALVE_STARTSTOP_INSTANCE: int = int(_get("VALVE_STARTSTOP_INSTANCE", 2))
PRODUCT_NAME = "dbus-pump"
SOFTWARE_VERSION = _read_version()
LANGUAGE: str = str(_get("LANGUAGE", "en"))

# --- Control logic ------------------------------------------------------------
# Master switch for automated actuation. Defaults to OFF so a fresh deploy is
# inert until thresholds have been tuned on site (fail-safe).
ENABLE_CONTROL: bool = _get("ENABLE_CONTROL", False)
VALVE_START_VALUE: float = float(_get("VALVE_START_VALUE", 30.0))  # open below this %
VALVE_STOP_VALUE: float = float(_get("VALVE_STOP_VALUE", 85.0))  # close at/above this %
SENSOR_STALE_TIMEOUT: float = float(_get("SENSOR_STALE_TIMEOUT", 120.0))  # s
MIN_SWITCH_INTERVAL: float = float(_get("MIN_SWITCH_INTERVAL", 60.0))  # s
POLL_INTERVAL: float = float(_get("POLL_INTERVAL", 2.0))  # s

HEARTBEAT_FILE = "/run/dbus-pump/heartbeat"
HA_TIMEOUT: float = float(_get("HA_TIMEOUT", 3.0))

# Circuit breaker
CIRCUIT_OPEN_THRESHOLD: int = int(_get("CIRCUIT_OPEN_THRESHOLD", 5))
CIRCUIT_RESET_TIMEOUT: float = float(_get("CIRCUIT_RESET_TIMEOUT", 60.0))


def validate() -> None:
    """Fail startup before registering services when configuration is unsafe."""
    validate_geometry(HA_WATER_LEVEL_UNIT, TANK_CAPACITY_LITERS, TANK_OFFSET_CM, TANK_RADIUS_CM)
    if not isinstance(ENABLE_CONTROL, bool):
        raise ValueError("ENABLE_CONTROL must be True or False, not a string or number")
    if not (
        finite_number(VALVE_START_VALUE) is not None
        and finite_number(VALVE_STOP_VALUE) is not None
        and 0 <= VALVE_START_VALUE < VALVE_STOP_VALUE <= 100
    ):
        raise ValueError("Valve thresholds must satisfy 0 <= START < STOP <= 100 (%)")
    for name in ("SENSOR_STALE_TIMEOUT", "POLL_INTERVAL", "HA_TIMEOUT", "CIRCUIT_RESET_TIMEOUT"):
        value = globals()[name]
        if finite_number(value) is None or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if finite_number(MIN_SWITCH_INTERVAL) is None or MIN_SWITCH_INTERVAL < 0:
        raise ValueError("MIN_SWITCH_INTERVAL must be finite and nonnegative")
    if CIRCUIT_OPEN_THRESHOLD <= 0:
        raise ValueError("CIRCUIT_OPEN_THRESHOLD must be positive")


def control_enabled() -> bool:
    """Automation runs only with ENABLE_CONTROL and a configured token."""
    if not HA_TOKEN or HA_TOKEN == "your_long_lived_access_token_here":
        return False
    return ENABLE_CONTROL
