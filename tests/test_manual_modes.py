"""Reject malformed D-Bus mode writes before they can actuate equipment."""

from enum import IntEnum

import pytest

from dbus_pump import main, service


class DbusIntStandIn(int):
    """Model integer D-Bus wrappers without requiring dbus-python off-device."""


class DbusBooleanStandIn(int):
    """dbus.Boolean inherits int instead of bool."""


class ModeEnum(IntEnum):
    AUTO = 0
    ON = 1
    OFF = 2


@pytest.fixture
def app(monkeypatch):
    class Client:
        def __init__(self, **_kwargs):
            self.calls = []

        def call_service(self, *args):
            self.calls.append(args)
            return True

        def close(self):
            pass

    monkeypatch.setattr(main, "HaClient", Client)
    monkeypatch.setattr(service, "VEDBUS_AVAILABLE", False)
    monkeypatch.setattr(main, "_BOOLEAN_TYPES", (bool, DbusBooleanStandIn))
    monkeypatch.setattr(main.config, "HA_PUMP_SWITCH_ENTITY", "switch.test_pump")
    monkeypatch.setattr(main.config, "HA_VALVE_SWITCH_ENTITY", "switch.test_valve")
    return main.build_app()


@pytest.mark.parametrize("which", ["pump", "valve"])
@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        DbusBooleanStandIn(1),
        DbusBooleanStandIn(0),
        0.0,
        1.0,
        1.5,
        2.9,
        float("nan"),
        float("inf"),
        "1",
        "2",
        None,
        [],
        {},
        -1,
        3,
        99,
    ],
)
def test_invalid_modes_never_reach_actuator_or_change_controller(app, which, value):
    callback = getattr(app.services, which)._onchange["/Mode"]
    assert callback("/Mode", value) is False
    assert app.client.calls == []
    assert app.controller.mode == 0
    assert app.services.pump["/Mode"] == 0
    assert app.services.valve["/Mode"] == 0


@pytest.mark.parametrize("mode_type", [int, DbusIntStandIn, ModeEnum])
@pytest.mark.parametrize("value,action", [(0, None), (1, "turn_on"), (2, "turn_off")])
@pytest.mark.parametrize("which", ["pump", "valve"])
def test_valid_integral_modes_keep_existing_behavior(app, which, value, action, mode_type):
    callback = getattr(app.services, which)._onchange["/Mode"]
    assert callback("/Mode", mode_type(value)) is True
    expected = [] if action is None else [("switch", action, f"switch.test_{which}")]
    assert app.client.calls == expected
    assert app.controller.mode == (value if which == "valve" else 0)


def test_direct_invalid_mode_and_unknown_device_are_rejected(app):
    assert app.handle_mode("valve", 1.5) is False
    assert app.handle_mode("typo", 1) is False
    assert app.client.calls == []


def test_empty_callback_is_rejected(app):
    callback = app.services.valve._onchange["/Mode"]
    assert callback() is False
    assert app.client.calls == []
