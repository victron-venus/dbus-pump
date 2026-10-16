"""Dry-run is a real HA read with no native publication or actuator writes."""

import sys
from types import SimpleNamespace

import pytest

from dbus_pump import main, service


@pytest.fixture
def preview(monkeypatch):
    state = SimpleNamespace(clients=[], fail_poll=False)

    class Client:
        def __init__(self, **_kwargs):
            self.closed = False
            self.polls = 0
            self.calls = []
            state.clients.append(self)

        def poll(self):
            self.polls += 1
            if state.fail_poll:
                raise RuntimeError("poll failed")
            return {"level": 10.0, "level_unit": "%", "pump": False, "valve": False, "ok": True}

        def call_service(self, *args):
            self.calls.append(args)
            pytest.fail("dry-run must never actuate equipment")

        def close(self):
            self.closed = True

    def forbid_native(*_args, **_kwargs):
        pytest.fail("dry-run must never construct a native D-Bus service or connection")

    def forbid_heartbeat():
        pytest.fail("dry-run must not refresh the real service's health heartbeat")

    monkeypatch.setattr(main, "HaClient", Client)
    monkeypatch.setattr(main, "_write_heartbeat", forbid_heartbeat)
    monkeypatch.setattr(main, "VEDBUS_AVAILABLE", True)
    monkeypatch.setattr(service, "VEDBUS_AVAILABLE", True)
    monkeypatch.setattr(service, "VeDbusService", forbid_native, raising=False)
    monkeypatch.setattr(service, "dbus", SimpleNamespace(SystemBus=forbid_native), raising=False)
    monkeypatch.setattr(main.config, "ENABLE_CONTROL", True)
    monkeypatch.setattr(main.config, "HA_TOKEN", "test-token")
    monkeypatch.setattr(main.config, "HA_WATER_LEVEL_UNIT", "%")
    monkeypatch.setattr(sys, "argv", ["dbus-pump", "--dry-run"])
    return state


def test_dry_run_reads_once_without_native_services_or_actuation(preview, capsys):
    assert main.main() == 0
    assert len(preview.clients) == 1
    client = preview.clients[0]
    assert client.polls == 1
    assert client.closed
    assert client.calls == []
    output = capsys.readouterr().out
    assert "com.victronenergy.tank.ha_tank21" in output
    assert "'/Level': 10.0" in output
    assert "'/State': 0" in output


def test_dry_run_uses_null_services_even_when_native_is_available(preview):
    app = main.build_app(dry_run=True)
    assert app.read_only
    assert not app.enable_control
    assert all(
        type(svc) is service.NullDbusService
        for svc in (app.services.tank, app.services.pump, app.services.valve)
    )
    app.services.register()  # still no native publication on repeated registration
    for which in ("pump", "valve"):
        assert app.handle_mode(which, 1) is False
        assert app.handle_mode(which, 2) is False
    assert app._request_service("turn_on", "switch.test", lambda _: None) is False
    app.shutdown()
    assert preview.clients[0].closed
    assert preview.clients[0].calls == []


def test_dry_run_closes_session_when_polling_fails(preview):
    preview.fail_poll = True
    with pytest.raises(RuntimeError, match="poll failed"):
        main.main()
    assert preview.clients[0].closed


def test_dry_run_closes_session_when_printing_fails(preview, monkeypatch):
    def broken_print(*_args, **_kwargs):
        raise BrokenPipeError("output closed")

    monkeypatch.setattr("builtins.print", broken_print)
    with pytest.raises(BrokenPipeError, match="output closed"):
        main.main()
    assert preview.clients[0].closed


def test_builder_closes_session_when_service_setup_fails(preview, monkeypatch):
    def fail_setup(*_args, **_kwargs):
        raise RuntimeError("setup failed")

    monkeypatch.setattr(main, "WaterSystemServices", fail_setup)
    with pytest.raises(RuntimeError, match="setup failed"):
        main.main()
    assert preview.clients[0].closed
