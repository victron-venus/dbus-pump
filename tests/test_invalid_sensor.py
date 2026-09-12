"""Invalid HA measurements must not bypass the existing stale-sensor policy."""

import json
from unittest.mock import MagicMock, patch

import pytest

from dbus_pump.control import MODE_ON, ValveController
from dbus_pump.ha_client import CircuitBreaker, HaClient
from dbus_pump.main import App
from dbus_pump.service import WaterSystemServices


def mocked_client():
    session = MagicMock()
    with patch("dbus_pump.ha_client.requests.Session", return_value=session):
        client = HaClient(
            "http://ha.invalid",
            "test",
            "sensor.level",
            "switch.pump",
            "switch.valve",
            breaker=CircuitBreaker(threshold=1),
        )
    return client, session


@pytest.mark.parametrize("invalid", [None, float("nan"), float("inf"), -float("inf")])
def test_invalid_level_holds_until_existing_deadline_then_closes(invalid):
    now = [1000.0]
    controller = ValveController(30.0, 85.0, 120.0, 0.0, clock=lambda: now[0])
    assert controller.update(20.0, True) == (True, "auto-open")
    now[0] += 1
    assert controller.update(invalid, True) == (True, "hold")
    assert controller.last_level_time == 1000.0
    now[0] = 1120.0
    assert controller.update(invalid, True) == (False, "stale-close")
    assert controller.last_level_time == 1000.0
    assert controller.update(90.0, True) == (False, "auto-close")
    assert controller.last_level_time == 1120.0


def test_invalid_level_preserves_manual_mode():
    controller = ValveController(30.0, 85.0, 120.0, 0.0)
    controller.set_mode(MODE_ON)
    assert controller.update(float("nan"), True) == (True, "manual-on")
    assert controller.last_level_time is None


@pytest.mark.parametrize("invalid", ["NaN", "Infinity", "-Infinity"])
def test_client_rejects_nonfinite_level_and_height_and_recovers(invalid):
    client, session = mocked_client()
    session.post = MagicMock()
    session.post.return_value = MagicMock(
        status_code=200,
        text=json.dumps({"level": invalid, "cm": invalid, "pump": "off", "valve": "on"}),
    )
    result = client.poll()
    assert result["ok"] is False
    assert result["level"] is None
    assert result["cm"] is None
    session.post.return_value.text = json.dumps(
        {"level": "0", "cm": "0", "pump": "off", "valve": "off"}
    )
    recovered = client.poll()
    assert recovered["ok"] is True
    assert recovered["level"] == 0.0
    assert recovered["cm"] == 0.0


@pytest.mark.parametrize("payload", [None, [], 42])
def test_nonobject_json_is_a_failed_poll_not_a_worker_exception(payload):
    client, session = mocked_client()
    session.post = MagicMock(return_value=MagicMock(status_code=200, text=json.dumps(payload)))
    assert client.poll()["ok"] is False
    assert client.breaker.is_open


def test_unavailable_after_valid_sample_keeps_timer_and_stale_close(monkeypatch):
    """Exercise the actual client-to-controller callback and later recovery."""
    now = [1000.0]
    monkeypatch.setattr("dbus_pump.main._now", lambda: now[0])
    monkeypatch.setattr("dbus_pump.main._write_heartbeat", lambda: None)
    monkeypatch.setattr("dbus_pump.main.config.SENSOR_STALE_TIMEOUT", 120.0)
    client, session = mocked_client()
    session.post = MagicMock()
    client.call_service = MagicMock(return_value=True)
    controller = ValveController(30, 85, 120, 0, clock=lambda: now[0])
    services = WaterSystemServices(21, 1, 2, "test", lambda _: None, lambda _: None)
    app = App(client, controller, services, enable_control=True)

    def sample(level):
        session.post.return_value = MagicMock(
            status_code=200, text=json.dumps({"level": level, "pump": "off", "valve": "on"})
        )
        assert app.tick() is True

    sample("20")
    now[0] += 1
    sample("unavailable")
    assert app.last_ok_time == 1000
    assert controller.last_level_time == 1000
    assert services.tank["/Level"] is None
    assert services.tank["/Remaining"] is None
    assert client.call_service.call_count == 0
    now[0] = 1120
    sample("NaN")
    assert services.tank["/Connected"] == 0
    assert client.call_service.call_args.args[1] == "turn_off"
    now[0] += 1
    sample("90")
    assert services.tank["/Level"] == 90
    assert services.tank["/Connected"] == 1
