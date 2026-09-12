"""Initialize the entire water-service group before publishing bus names."""

from types import SimpleNamespace

import pytest

from dbus_pump import main, service


@pytest.fixture(name="native")
def native_services(monkeypatch):
    """Record initialization order and each private bus without hardware I/O."""
    state = SimpleNamespace(instances=[], snapshots=[], buses=[], failure=False)

    class NativeService(service.NullDbusService):
        """Model a native service that must explicitly acquire its name."""

        def __init__(self, name, *, bus, register):
            assert register is False
            assert bus in state.buses
            super().__init__(name)
            self.registered = False
            state.instances.append(self)

        def add_path(
            self, path, value, description="", writeable=False, onchangecallback=None, **kwargs
        ):
            assert not self.registered
            if state.failure and self.service_name.endswith("startstop2"):
                raise ValueError("invalid initialization")
            super().add_path(path, value, description, writeable, onchangecallback, **kwargs)

        def register(self):
            assert not self.registered
            assert len(state.instances) == 3
            assert "/ActiveTankService" in state.instances[-1].items
            self.registered = True
            state.snapshots.append(dict(self.items))

    def system_bus(*, private):
        assert private is True
        bus = object()
        state.buses.append(bus)
        return bus

    monkeypatch.setattr(service, "dbus", SimpleNamespace(SystemBus=system_bus), raising=False)
    monkeypatch.setattr(service, "VEDBUS_AVAILABLE", True)
    monkeypatch.setattr(service, "VeDbusService", NativeService, raising=False)
    return state


def test_native_group_registers_complete_paths_once_on_private_buses(native):
    water = service.WaterSystemServices(21, 1, 2, "test", capacity_m3=0.6)
    assert len(native.snapshots) == 3
    assert len({id(bus) for bus in native.buses}) == 3
    for snapshot, instance in zip(native.snapshots, native.instances):
        for path in (
            "/Mgmt/ProcessName",
            "/Mgmt/ProcessVersion",
            "/Mgmt/Connection",
            "/DeviceInstance",
            "/ProductId",
            "/ProductName",
            "/FirmwareVersion",
            "/Connected",
            "/Serial",
        ):
            assert path in snapshot
        assert snapshot == instance.items
    assert native.snapshots[0]["/Capacity"] == 0.6
    assert native.snapshots[0]["/Level"] is None
    for snapshot in native.snapshots[1:]:
        assert snapshot["/ActiveTankService"] == water.tank.service_name
        assert snapshot["/Mode"] == 0
        assert snapshot["/State"] == 0
    water.register()
    assert len(native.snapshots) == 3


def test_builder_registers_configured_capacity_and_disconnected_state(native, monkeypatch):
    monkeypatch.setattr(main.config, "TANK_CAPACITY_LITERS", 600.0)
    app = main.build_app()
    assert native.snapshots[0]["/Capacity"] == 0.6
    assert all(snapshot["/Connected"] == 0 for snapshot in native.snapshots)
    assert native.snapshots[0] == app.services.tank.items
    app.client.close()


def test_initialization_failure_does_not_publish_partial_group(native):
    native.failure = True
    with pytest.raises(ValueError, match="invalid initialization"):
        service.WaterSystemServices(21, 1, 2, "test")
    assert not native.snapshots
