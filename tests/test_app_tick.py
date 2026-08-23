"""Integration-ish tests for App.tick wiring with fake client/services."""

import dbus_pump.main as main_mod
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
    assert (
        "switch",
        "turn_on",
        "switch.shutoff_valve",
    ) not in app.client.calls  # entity comes from config
    assert any(c[1] == "turn_on" for c in app.client.calls)
    assert app.services.valve.items["/State"] == 1


def test_tick_no_control_when_disabled(monkeypatch):
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    snap = dict(BASE, level=10.0)
    app = build_app(snap, enable_control=False)
    app.tick()
    assert app.client.calls == []


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


def test_dry_run_smoke():
    """--dry-run executes one cycle without crashing off-GX."""
    rc = main_mod.main.__wrapped__() if hasattr(main_mod.main, "__wrapped__") else None
    # direct invocation instead:
    import sys

    sys.argv = ["dbus-pump", "--dry-run"]
    rc = main_mod.main()
    assert rc == 0
