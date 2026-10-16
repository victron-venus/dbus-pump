"""Integration-ish tests for App.tick wiring with fake client/services."""

import math

import pytest

import dbus_pump.main as main_mod
from dbus_pump import config as cfg
from dbus_pump.control import ValveController
from dbus_pump.main import App
from dbus_pump.service import WaterSystemServices


class FakeClient:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = []

    def poll(self):
        return self.snapshot

    def call_service(self, domain, action, entity_id):
        self.calls.append((domain, action, entity_id))
        return True


def build_app(snapshot, enable_control=True):
    controller = ValveController(30.0, 85.0, sensor_stale_timeout=120.0, min_switch_interval=60.0)
    services = WaterSystemServices(
        21, 1, 2, "0.1.0", on_pump_mode=lambda m: None, on_valve_mode=lambda m: None
    )
    client = FakeClient(snapshot)
    app = App(client, controller, services, enable_control=enable_control)
    return app


BASE = {"level": 50.0, "pump": False, "valve": False, "ok": True}


def test_tick_publishes_values(monkeypatch):
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    app = build_app(dict(BASE))
    app.tick()
    assert app.services.tank.items["/Level"] == 50.0
    assert app.services.valve.items["/State"] == 0
    assert app.client.calls == []  # nothing to command


def test_tick_commands_valve_open_when_low(monkeypatch):
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    snap = dict(BASE, level=10.0)
    app = build_app(snap)
    app.tick()
    # valve command targets the configured HA switch entity
    assert (
        "switch",
        "turn_on",
        cfg.HA_VALVE_SWITCH_ENTITY,
    ) in app.client.calls
    assert any(c[1] == "turn_on" for c in app.client.calls)
    assert app.services.valve.items["/State"] == 1


def test_tick_no_control_when_disabled(monkeypatch):
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    snap = dict(BASE, level=10.0)
    app = build_app(snap, enable_control=False)
    app.tick()
    assert app.client.calls == []


def test_tick_cm_source_drives_level_volume_and_control(monkeypatch):
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    monkeypatch.setattr(cfg, "HA_WATER_LEVEL_UNIT", "cm")
    monkeypatch.setattr(cfg, "TANK_CAPACITY_LITERS", 387.0)
    monkeypatch.setattr(cfg, "TANK_OFFSET_CM", 18.0)
    monkeypatch.setattr(cfg, "TANK_RADIUS_CM", 35.56)
    # 93cm is ~77%, below the close threshold. The old implementation read it
    # as 93% and would close an open valve. Secondary cm disagrees deliberately.
    snap = dict(BASE, level=93.0, cm=118.0, level_unit="cm", valve=True)
    app = build_app(snap)
    app.services.capacity_m3 = 0.387
    app.controller._desired = True
    app.tick()
    expected_m3 = (93.0 - 18.0) * math.pi * 35.56**2 / 1e6
    assert app.services.tank.items["/Level"] == round(expected_m3 / 0.387 * 100, 1)
    assert app.services.tank.items["/Remaining"] == round(expected_m3, 3)
    assert app.client.calls == []


def test_percent_source_is_authoritative_over_secondary_height(monkeypatch):
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    monkeypatch.setattr(cfg, "TANK_OFFSET_CM", 18.0)
    monkeypatch.setattr(cfg, "TANK_RADIUS_CM", 35.56)
    app = build_app(dict(BASE, cm=118.0))
    app.services.capacity_m3 = 0.387
    app.tick()
    assert app.services.tank.items["/Level"] == 50.0
    assert app.services.tank.items["/Remaining"] == 0.194


def test_tick_remaining_falls_back_to_capacity_derivation(monkeypatch):
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    app = build_app(dict(BASE))  # no 'cm' in snapshot
    app.services.capacity_m3 = 0.387
    app.tick()
    assert app.services.tank.items["/Remaining"] == 0.194


def test_tick_stale_publishes_invalid_level(monkeypatch):
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    snap = {"level": None, "pump": None, "valve": None, "ok": False}
    app = build_app(snap)
    app.tick()
    assert app.services.tank.items["/Level"] is None
    assert app.services.tank.items["/Status"] == 4
    assert app.services.tank.items["/Connected"] == 0


def test_handle_mode_manual_turns_valve(monkeypatch):
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    app = build_app(dict(BASE))
    app.handle_mode("valve", 1)  # ON
    assert ("switch", "turn_on", app.services.valve.service_name) != ...  # sanity
    assert any(c[:2] == ("switch", "turn_on") for c in app.client.calls)
    assert app.controller.mode == 1


def test_mode_handler_wrap_accepts_write():
    """vedbus rejects the SetValue (leaves /Mode stale) on a falsy callback."""
    seen = []
    cb = main_mod._mode_handler_wrap(lambda m: seen.append(m))
    assert cb("/Mode", 2) is True
    assert seen == [2]


def test_dry_run_smoke():
    """--dry-run executes one cycle without crashing off-GX."""
    rc = main_mod.main.__wrapped__() if hasattr(main_mod.main, "__wrapped__") else None
    # direct invocation instead:
    import sys

    sys.argv = ["dbus-pump", "--dry-run"]
    rc = main_mod.main()
    assert rc == 0


def test_stale_close_stays_closed_when_fresh_level_recovers_in_band(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(main_mod, "_now", lambda: now[0])
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    app = build_app(dict(BASE))
    app.controller._clock = lambda: now[0]
    app.controller._last_transition = now[0] - app.controller.min_switch_interval
    app.apply_snapshot(dict(BASE, level=20.0))
    assert app.client.calls[-1][1] == "turn_on"
    now[0] += 121
    app.apply_snapshot(dict(BASE, level=None, valve=True, ok=False))
    assert app.client.calls[-1][1] == "turn_off"
    now[0] += 1
    app.apply_snapshot(dict(BASE, level=50.0, valve=False))
    assert [call[1] for call in app.client.calls] == ["turn_on", "turn_off"]


@pytest.mark.parametrize("timestamp", [1001.0, 880.0, float("nan"), None, "bad"])
def test_invalid_or_expired_sample_cannot_change_recent_control_decision(monkeypatch, timestamp):
    monkeypatch.setattr(main_mod, "_now", lambda: 1000.0)
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    app = build_app(dict(BASE))
    app.controller._clock = lambda: 1000.0
    app.controller._last_transition = 0.0
    app.apply_snapshot(dict(BASE, level=50.0))
    app.apply_snapshot(dict(BASE, level=1.0, _sample_started_at=timestamp))
    assert app.services.tank["/Level"] is None
    assert app.client.calls == []
    assert app.last_ok_time == 1000.0
    assert app.controller.last_level_time == 1000.0


def test_conflicting_ha_unit_is_rejected_without_refreshing_deadline(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(main_mod, "_now", lambda: now[0])
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    app = build_app(dict(BASE))
    app.controller._clock = lambda: now[0]
    app.controller._last_transition = 0.0
    app.apply_snapshot(dict(BASE))
    now[0] += 1
    app.apply_snapshot(dict(BASE, level=10.0, level_unit="cm"))
    assert app.services.tank["/Level"] is None
    assert app.services.tank["/Remaining"] is None
    assert app.last_ok_time == 1000.0
    assert app.client.calls == []


def test_rejected_future_sample_cannot_resurrect_when_time_catches_up(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(main_mod, "_now", lambda: now[0])
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    app = build_app(dict(BASE))
    app.controller._clock = lambda: now[0]
    app.controller._last_transition = 0.0
    app.apply_snapshot(dict(BASE))
    app.apply_snapshot(dict(BASE, level=1, _sample_started_at=1001.0))
    now[0] = 1002.0
    app.apply_snapshot(dict(app._last_snapshot, ok=False))
    assert app.services.tank["/Level"] is None
    assert app.client.calls == []
    assert app.last_ok_time == 1000.0


def test_cm_cached_sample_expires_without_double_conversion(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(main_mod, "_now", lambda: now[0])
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    monkeypatch.setattr(cfg, "HA_WATER_LEVEL_UNIT", "cm")
    monkeypatch.setattr(cfg, "TANK_CAPACITY_LITERS", 387.0)
    monkeypatch.setattr(cfg, "TANK_OFFSET_CM", 18.0)
    monkeypatch.setattr(cfg, "TANK_RADIUS_CM", 35.56)
    app = build_app(dict(BASE), enable_control=False)
    app.services.capacity_m3 = 0.387
    sample = dict(BASE, level=93.0, level_unit="cm")
    app.apply_snapshot(sample)
    level = app.services.tank["/Level"]
    now[0] += 119
    app.apply_snapshot(dict(sample, ok=False))
    assert app.services.tank["/Level"] == level
    assert app.last_ok_time == 1000.0
    now[0] += 1
    app.apply_snapshot(dict(sample, ok=False))
    assert app.services.tank["/Level"] is None
    assert app.services.tank["/Remaining"] is None
    assert app.services.tank["/Connected"] == 0


@pytest.mark.parametrize(
    "level,display,remaining,was_open,threshold,action",
    [
        (30.04, 30.0, 0.451, False, 30.0, "turn_on"),
        (84.96, 85.0, 1.274, True, 85.0, "turn_off"),
    ],
)
def test_display_rounding_does_not_change_control_threshold_or_volume(
    monkeypatch, level, display, remaining, was_open, threshold, action
):
    now = [1000.0]
    monkeypatch.setattr(main_mod, "_now", lambda: now[0])
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    monkeypatch.setattr(cfg, "HA_WATER_LEVEL_UNIT", "%")
    monkeypatch.setattr(cfg, "TANK_CAPACITY_LITERS", 1500.0)
    app = build_app(dict(BASE))
    app.services.capacity_m3 = 1.5
    app.controller._clock = lambda: now[0]
    app.controller._last_transition = 0.0
    app.controller._desired = was_open

    app.apply_snapshot(dict(BASE, level=level, valve=was_open))
    assert app.services.tank["/Level"] == display
    # 1500L distinguishes volume calculated before versus after rounding the
    # displayed percentage. The controller must use the unrounded value too.
    assert app.services.tank["/Remaining"] == remaining
    assert app.client.calls == []

    now[0] += 1
    app.apply_snapshot(dict(BASE, level=threshold, valve=was_open))
    assert app.client.calls == [("switch", action, cfg.HA_VALVE_SWITCH_ENTITY)]
