"""A blocked HA request must not occupy or mutate the D-Bus main loop."""

# Tests inject a deterministic control clock and inspect compensation state.
# pylint: disable=protected-access

import queue
import threading

import pytest

import dbus_pump.main as main_mod
from dbus_pump import config
from dbus_pump.control import MODE_AUTO, MODE_OFF, MODE_ON
from dbus_pump.worker import HaWorker
from tests.test_app_tick import BASE, build_app


class MainLoop:
    """Dispatch worker completions only when the test's main thread pumps them."""

    def __init__(self):
        self.callbacks = queue.Queue()

    def dispatch(self, callback, *args):
        self.callbacks.put((callback, args))

    def run_one(self):
        callback, args = self.callbacks.get(timeout=2)
        assert callback(*args) is False


class BlockingClient:
    """Gate network operations while recording serialization and cleanup."""

    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.polls = 0
        self.calls = []
        self.threads = []
        self.active = 0
        self.maximum_active = 0
        self.closed = False
        self.snapshot = dict(BASE)
        self.error = False
        self.block_open = False
        self.open_started = threading.Event()
        self.release_open = threading.Event()
        self.service_results = []

    def _enter(self):
        self.threads.append(threading.get_ident())
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)

    def poll(self):
        self._enter()
        self.polls += 1
        self.started.set()
        try:
            assert self.release.wait(3), "test did not release the HA request"
            if self.error:
                raise RuntimeError("test HA failure")
            return dict(self.snapshot)
        finally:
            self.active -= 1

    def call_service(self, *args):
        self._enter()
        try:
            self.calls.append(args)
            if args[1] == "turn_on" and self.block_open:
                self.open_started.set()
                assert self.release_open.wait(3), "test did not release the valve ON request"
            result = self.service_results.pop(0) if self.service_results else True
            if isinstance(result, Exception):
                raise result  # pylint: disable=raising-bad-type
            return result
        finally:
            self.active -= 1

    def close(self):
        assert self.active == 0
        self.closed = True


@pytest.fixture(name="running")
def running_app(monkeypatch):
    monkeypatch.setattr(main_mod, "_write_heartbeat", lambda: None)
    monkeypatch.setattr(config, "HA_VALVE_SWITCH_ENTITY", "switch.test_valve")
    monkeypatch.setattr(config, "HA_PUMP_SWITCH_ENTITY", "switch.test_pump")
    app = build_app(dict(BASE), enable_control=False)
    app.apply_snapshot(dict(BASE))
    client = BlockingClient()
    app.client = client
    loop = MainLoop()
    app.worker = HaWorker(client, loop.dispatch, config.HA_VALVE_SWITCH_ENTITY)
    try:
        yield app, client, loop
    finally:
        client.release.set()
        client.release_open.set()
        assert app.worker.stop(timeout=2)


def test_slow_poll_does_not_block_reads_or_overlap_and_applies_on_main_loop(running):
    app, client, loop = running
    main_thread = threading.get_ident()
    mutation_threads = []
    original = app.services.update_tank_level

    def update(*args, **kwargs):
        mutation_threads.append(threading.get_ident())
        return original(*args, **kwargs)

    app.services.update_tank_level = update
    client.snapshot["level"] = 85.0
    assert app.tick() is True
    assert client.started.wait(2)
    for _ in range(20):
        assert app.tick() is True
        assert app.services.tank.items["/Level"] == 50.0
    assert client.polls == 1
    assert not mutation_threads
    client.release.set()
    loop.run_one()
    assert app.services.tank.items["/Level"] == 85.0
    assert mutation_threads == [main_thread]
    assert client.maximum_active == 1
    assert all(t != main_thread for t in client.threads)


def test_manual_command_is_serialized_and_dbus_changes_only_after_completion(running):
    app, client, loop = running
    app.tick()
    assert client.started.wait(2)
    assert app.handle_mode("pump", MODE_ON) is True
    assert client.calls == []
    assert app.services.pump.items["/State"] == 0
    client.release.set()
    loop.run_one()  # Poll result, then service-call completion.
    assert app.services.pump.items["/State"] == 0
    loop.run_one()
    assert app.services.pump.items["/State"] == 1
    assert client.maximum_active == 1
    assert len(set(client.threads)) == 1


def test_stale_data_expires_and_stale_close_is_queued_during_blocked_poll(running, monkeypatch):
    app, client, loop = running
    clock = [100.0]
    monkeypatch.setattr(main_mod, "_now", lambda: clock[0])
    monkeypatch.setattr(config, "SENSOR_STALE_TIMEOUT", 10.0)
    app.controller._clock = lambda: clock[0]
    app.controller.sensor_stale_timeout = 10.0
    app.controller._last_transition = 0.0
    app.enable_control = True
    app.handle_mode("valve", MODE_AUTO)
    app.apply_snapshot(dict(BASE, level=10.0, valve=True))
    app.tick()
    assert client.started.wait(2)
    clock[0] = 110.0
    app.tick()
    assert app.last_ok_time == 100.0
    assert app.services.tank.items["/Connected"] == 0
    assert app.services.tank.items["/Level"] is None
    assert app.worker.service_pending(config.HA_VALVE_SWITCH_ENTITY, "turn_off")
    assert client.calls == []  # No concurrent HTTP request.
    client.release.set()
    loop.run_one()
    loop.run_one()
    assert any(c[1] == "turn_off" for c in client.calls)


def test_manual_off_cancels_queued_automatic_open(running):
    app, client, loop = running
    app.enable_control = True
    app.tick()
    assert client.started.wait(2)
    app.apply_snapshot(dict(BASE, level=10.0, valve=False))
    assert app.worker.service_pending(config.HA_VALVE_SWITCH_ENTITY, "turn_on")
    assert app.handle_mode("valve", MODE_OFF) is True
    assert app.controller.mode == MODE_OFF
    client.release.set()
    loop.run_one()
    loop.run_one()
    assert [c[1] for c in client.calls] == ["turn_off"]
    assert app.services.valve.items["/State"] == 0


def test_expiry_cancels_queued_open_even_if_last_observed_valve_was_closed(running, monkeypatch):
    app, client, _ = running
    clock = [100.0]
    monkeypatch.setattr(main_mod, "_now", lambda: clock[0])
    monkeypatch.setattr(config, "SENSOR_STALE_TIMEOUT", 10.0)
    app.controller._clock = lambda: clock[0]
    app.controller.sensor_stale_timeout = 10.0
    app.controller._last_transition = 0.0
    app.enable_control = True
    app.tick()
    assert client.started.wait(2)
    app.apply_snapshot(dict(BASE, level=10.0, valve=False))
    assert app.worker.service_pending(config.HA_VALVE_SWITCH_ENTITY, "turn_on")
    clock[0] = 110.0
    app.tick()
    assert not app.worker.service_pending(config.HA_VALVE_SWITCH_ENTITY, "turn_on")
    assert app.worker.stop(timeout=0) is False
    client.release.set()
    assert app.worker.stop(timeout=2)
    assert [c[1] for c in client.calls] == ["turn_off"]  # Shutdown only.


@pytest.mark.parametrize("trigger", ["expiry", "auto"])
def test_inflight_open_gets_compensating_close_after_expiry_or_auto(running, monkeypatch, trigger):
    app, client, loop = running
    clock = [100.0]
    monkeypatch.setattr(main_mod, "_now", lambda: clock[0])
    monkeypatch.setattr(config, "SENSOR_STALE_TIMEOUT", 10.0)
    app.controller._clock = lambda: clock[0]
    app.controller.sensor_stale_timeout = 10.0
    app.controller._last_transition = 0.0
    app.enable_control = True
    client.block_open = True
    if trigger == "expiry":
        app.apply_snapshot(dict(BASE, level=10.0, valve=False))
    else:
        app.apply_snapshot(dict(BASE, level=90.0, valve=False))
        app.handle_mode("valve", MODE_ON)
    assert client.open_started.wait(2)
    if trigger == "expiry":
        clock[0] = 110.0
        app.tick()
    else:
        app.handle_mode("valve", MODE_AUTO)
    assert app.worker.service_pending(config.HA_VALVE_SWITCH_ENTITY, "turn_off")
    client.release_open.set()
    loop.run_one()  # Superseded ON result must not publish an open valve.
    assert app.services.valve.items["/State"] == 0
    loop.run_one()
    assert [c[1] for c in client.calls] == ["turn_on", "turn_off"]
    assert client.maximum_active == 1


def test_full_queue_rejects_mode_write_without_changing_controller_mode(running):
    app, client, _ = running
    app.tick()
    assert client.started.wait(2)
    for _ in range(8):
        assert app.handle_mode("pump", MODE_ON)
    previous_mode = app.controller.mode
    callback = main_mod._mode_handler_wrap(lambda mode: app.handle_mode("valve", mode))
    assert callback("/Mode", MODE_OFF) is False
    assert app.controller.mode == previous_mode


def test_compensating_close_retries_after_full_queue(running, monkeypatch):
    app, client, loop = running
    clock = [100.0]
    monkeypatch.setattr(main_mod, "_now", lambda: clock[0])
    monkeypatch.setattr(config, "SENSOR_STALE_TIMEOUT", 10.0)
    app.controller._clock = lambda: clock[0]
    app.controller.sensor_stale_timeout = 10.0
    app.controller._last_transition = 0.0
    app.enable_control = True
    client.block_open = True
    app.apply_snapshot(dict(BASE, level=10.0, valve=False))
    assert client.open_started.wait(2)
    for _ in range(8):
        assert app.handle_mode("pump", MODE_ON)
    clock[0] = 110.0
    app.tick()
    assert app._valve_reconcile_required
    client.release_open.set()
    loop.run_one()  # Superseded valve ON.
    loop.run_one()  # Only the last queued pump command survives.
    app.tick()
    loop.run_one()  # The deferred safety OFF now completes.
    assert [c[1] for c in client.calls if c[2] == config.HA_VALVE_SWITCH_ENTITY] == [
        "turn_on",
        "turn_off",
    ]
    assert not app._valve_reconcile_required


def test_compensating_close_retries_after_ha_rejects_it(running):
    app, client, loop = running
    app.enable_control = True
    app.apply_snapshot(dict(BASE, level=90.0, valve=False))
    client.block_open = True
    client.service_results = [True, False, True]
    app.handle_mode("valve", MODE_ON)
    assert client.open_started.wait(2)
    app.handle_mode("valve", MODE_AUTO)
    client.release_open.set()
    loop.run_one()
    loop.run_one()
    assert app._valve_reconcile_required
    app.apply_snapshot(dict(BASE, level=90.0, valve=False))
    loop.run_one()
    assert [c[1] for c in client.calls] == ["turn_on", "turn_off", "turn_off"]
    assert not app._valve_reconcile_required


@pytest.mark.parametrize("failure", [False, RuntimeError("test service failure")])
def test_failed_manual_off_retries_after_inflight_open_with_old_closed_snapshot(running, failure):
    app, client, loop = running
    app.enable_control = True
    client.block_open = True
    client.service_results = [True, failure, True]
    app.apply_snapshot(dict(BASE, level=10.0, valve=False))
    assert client.open_started.wait(2)
    app.handle_mode("valve", MODE_OFF)
    client.release_open.set()
    loop.run_one()
    loop.run_one()
    assert app.controller.mode == MODE_OFF
    assert app._valve_reconcile_required
    app.apply_snapshot(dict(BASE, valve=False))
    loop.run_one()
    assert [c[1] for c in client.calls] == ["turn_on", "turn_off", "turn_off"]
    assert not app._valve_reconcile_required


def test_monitoring_only_mode_does_not_introduce_automatic_commands(running):
    app, client, loop = running
    app.tick()
    assert client.started.wait(2)
    app.handle_mode("valve", MODE_ON)
    app.handle_mode("valve", MODE_AUTO)
    client.release.set()
    loop.run_one()
    loop.run_one()
    assert app.controller.mode == MODE_AUTO
    assert [c[1] for c in client.calls] == ["turn_on"]


def test_shutdown_cancels_queued_open_discards_callbacks_and_closes_session(running):
    app, client, loop = running
    app.tick()
    assert client.started.wait(2)
    app.handle_mode("valve", MODE_ON)
    assert app.worker.stop(timeout=0) is False
    assert not app.worker.poll(app.apply_snapshot)
    assert not app.handle_mode("pump", MODE_ON)
    client.release.set()
    assert app.worker.stop(timeout=2)
    loop.run_one()  # The in-flight poll callback must not mutate after stop.
    assert [c[1] for c in client.calls] == ["turn_off"]
    assert client.closed
    assert app.services.valve.items["/State"] == 0


def test_unexpected_poll_failure_allows_retry_without_fabricating_values(running):
    app, client, loop = running
    client.error = True
    client.release.set()
    app.tick()
    loop.run_one()
    assert app.services.tank.items["/Level"] == 50.0
    client.error = False
    client.snapshot["level"] = 61.0
    app.tick()
    loop.run_one()
    assert client.polls == 2
    assert app.services.tank.items["/Level"] == 61.0
