"""Reject unsafe configuration before any service is registered."""

from unittest.mock import MagicMock

import pytest

from dbus_pump import config, main


@pytest.mark.parametrize(
    "name,value",
    [
        ("HA_WATER_LEVEL_UNIT", "liters"),
        ("TANK_CAPACITY_LITERS", -1),
        ("TANK_CAPACITY_LITERS", float("nan")),
        ("ENABLE_CONTROL", "False"),
        ("VALVE_START_VALUE", -1),
        ("VALVE_STOP_VALUE", 101),
        ("VALVE_STOP_VALUE", float("inf")),
        ("SENSOR_STALE_TIMEOUT", 0),
        ("POLL_INTERVAL", float("nan")),
        ("HA_TIMEOUT", -1),
        ("CIRCUIT_RESET_TIMEOUT", float("inf")),
        ("MIN_SWITCH_INTERVAL", -1),
        ("CIRCUIT_OPEN_THRESHOLD", 0),
    ],
)
def test_invalid_configuration_fails_before_service_creation(monkeypatch, name, value):
    monkeypatch.setattr(config, name, value)
    services = MagicMock()
    monkeypatch.setattr(main, "WaterSystemServices", services)
    with pytest.raises(ValueError):
        main.build_app()
    services.assert_not_called()


def test_percentage_without_geometry_remains_supported():
    config.validate()
