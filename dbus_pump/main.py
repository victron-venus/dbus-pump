"""Entry point: HA <-> D-Bus water system bridge."""

import argparse
import logging
import os
import signal
import sys
import time
from numbers import Integral

from dbus_pump import config
from dbus_pump.control import MODE_AUTO, MODE_OFF, MODE_ON, ValveController
from dbus_pump.ha_client import CircuitBreaker, HaClient
from dbus_pump.service import VEDBUS_AVAILABLE, WaterSystemServices
from dbus_pump.tank import finite_number, normalize_level
from dbus_pump.worker import HaWorker

logger = logging.getLogger("dbus-pump")

try:
    from dbus import Boolean as DbusBoolean
except ImportError:
    _BOOLEAN_TYPES = (bool,)
else:
    # dbus.Boolean is an int subclass, not a Python bool subclass.
    _BOOLEAN_TYPES = (bool, DbusBoolean)


def _mode_handler_wrap(handler):
    """Vedbus onchange signatures vary across versions; take the last arg."""

    def cb(*args):
        if not args:
            return False
        accepted = handler(args[-1])
        # vedbus rejects the write (SetValue -> 2) unless the callback is
        # truthy, leaving /Mode at its old value.
        return accepted is not False

    return cb


class App:
    """Apply HA snapshots and control decisions on the D-Bus main loop."""

    def __init__(
        self,
        client: HaClient,
        controller: ValveController,
        services: WaterSystemServices,
        enable_control: bool,
        read_only: bool = False,
    ) -> None:
        self.client = client
        self.controller = controller
        self.services = services
        self.read_only = read_only
        self.enable_control = enable_control and not read_only
        self.last_ok_time: float | None = None
        self._last_commanded_valve: bool | None = None
        self.loop_interval_ms = max(250, int(config.POLL_INTERVAL * 1000))
        self.worker: HaWorker | None = None
        self._last_snapshot = {"level": None, "pump": None, "valve": None, "ok": False}
        self._valve_reconcile_required = False
        self._level_rejection_logged = False

    # --- GX -> HA manual mode writes ----------------------------------------
    def handle_mode(self, which: str, mode: int) -> bool:
        if self.read_only:
            return False
        if (
            which not in ("pump", "valve")
            or isinstance(mode, _BOOLEAN_TYPES)
            or not isinstance(mode, Integral)
            or mode not in (MODE_AUTO, MODE_ON, MODE_OFF)
        ):
            logger.warning("Rejected invalid %s /Mode value: %r", which, mode)
            return False
        entity = config.HA_VALVE_SWITCH_ENTITY if which == "valve" else config.HA_PUMP_SWITCH_ENTITY
        logger.info("%s /Mode changed to %s", which, mode)
        action = {MODE_ON: ("turn_on", True), MODE_OFF: ("turn_off", False)}.get(mode)
        if action and not self._request_manual_action(which, action, entity):
            return False
        if which == "valve":
            self.controller.set_mode(mode)
            if not action and self.worker is not None and self.enable_control:
                # Re-evaluate AUTO against the existing sample without making
                # it fresh. This also compensates an in-flight manual ON when
                # the automatic policy now requires OFF.
                self.apply_snapshot(dict(self._last_snapshot, ok=False))
        return True

    def _request_manual_action(self, which, action, entity):
        """Queue one manual write while preserving in-flight valve reconciliation."""
        act, state = action
        compensating = (
            which == "valve"
            and self.worker is not None
            and self.worker.service_pending(entity, "turn_off" if state else "turn_on")
        )

        def completed(ok):
            if not ok:
                if compensating and self.enable_control:
                    self._valve_reconcile_required = True
                return
            self.services.update_device_state(which, state)
            self._last_commanded_valve = state if which == "valve" else self._last_commanded_valve
            if which == "valve":
                self._valve_reconcile_required = False

        return self._request_service(act, entity, completed)

    def _request_service(self, action, entity, callback, deduplicate=False):
        if self.read_only:
            return False
        if self.worker is not None:
            if deduplicate and self.worker.service_pending(entity, action):
                return True
            return self.worker.call_service("switch", action, entity, callback)
        callback(self.client.call_service("switch", action, entity))
        return True

    def shutdown(self) -> None:
        """Fail-safe: force the city-water valve CLOSED before exiting (Q5).

        Best effort — a dead HA or open breaker still leaves the valve as-is;
        residual risk of Cerbo power loss is documented in the README.
        """
        if self.read_only:
            self.client.close()
            return
        if self.worker is not None:
            self.worker.stop()
            return
        try:
            entity = config.HA_VALVE_SWITCH_ENTITY
            if self.client.call_service("switch", "turn_off", entity):
                logger.info("Shutdown: valve forced closed")
        except Exception:
            logger.exception("Shutdown: failed to close valve")

    # --- main cycle ----------------------------------------------------------
    def tick(self) -> bool:
        if self.worker is not None:
            # A slow request must not freeze Connected or postpone the valve's
            # existing stale-sensor fail-safe. No old sample becomes fresh.
            if (
                self.last_ok_time is None
                or _now() - self.last_ok_time >= config.SENSOR_STALE_TIMEOUT
            ):
                self.apply_snapshot(dict(self._last_snapshot, ok=False))
            self.worker.poll(self.apply_snapshot)
            if not self.read_only:
                _write_heartbeat()
            return True
        started_at = _now()
        snapshot = self.client.poll()
        return self.apply_snapshot(dict(snapshot, _sample_started_at=started_at))

    def apply_snapshot(self, snapshot) -> bool:
        """Apply HA results on the D-Bus main loop (also used by dry-run)."""
        self._last_snapshot = dict(snapshot)
        now = _now()
        started_at = finite_number(snapshot.get("_sample_started_at", now))
        acquired_recently = (
            started_at is not None and 0 <= now - started_at < config.SENSOR_STALE_TIMEOUT
        )
        level = normalize_level(
            snapshot["level"],
            config.HA_WATER_LEVEL_UNIT,
            config.TANK_CAPACITY_LITERS,
            config.TANK_OFFSET_CM,
            config.TANK_RADIUS_CM,
            snapshot.get("level_unit"),
        )
        if not acquired_recently:
            level = None
        if level is None:
            # A future timestamp can eventually enter the current window.
            # Do not let a rejected sample resurrect during AUTO reconciliation.
            self._last_snapshot["level"] = None
        now_ok = bool(snapshot["ok"] and acquired_recently and level is not None)
        if snapshot["ok"] and acquired_recently and level is None:
            if not self._level_rejection_logged:
                logger.warning("Rejected tank measurement: check value, unit and tank geometry")
            self._level_rejection_logged = True
        if now_ok:
            self.last_ok_time = started_at
            self._level_rejection_logged = False
        ha_reachable = (
            self.last_ok_time is not None
            and 0 <= now - self.last_ok_time < config.SENSOR_STALE_TIMEOUT
        )
        self.services.set_connected(ha_reachable)

        # One normalized value drives display, volume and automatic control.
        # Network failures may retain the last value only until its original
        # deadline; malformed or delayed samples never become usable via that grace.
        level = level if now_ok or ha_reachable else None
        self.services.update_tank_level(level)

        self.services.update_device_state("pump", snapshot["pump"])
        self.services.update_device_state("valve", snapshot["valve"])

        if self.enable_control:
            self._apply_automatic_control(dict(snapshot, level=level), now_ok, started_at)
        elif snapshot.get("valve") is not None:
            self._last_commanded_valve = snapshot["valve"]

        if not self.read_only:
            _write_heartbeat()
        return True

    def _apply_automatic_control(self, snapshot, now_ok, started_at):
        """Reconcile the valve against the controller decision and pending writes."""
        fresh = now_ok and snapshot["level"] is not None
        desired, why = self.controller.update(snapshot["level"], fresh, sampled_at=started_at)
        entity = config.HA_VALVE_SWITCH_ENTITY
        opposite = "turn_off" if desired else "turn_on"
        superseded = self.worker is not None and self.worker.service_pending(entity, opposite)
        if superseded:
            self.worker.cancel_service(entity)
            self._valve_reconcile_required = True
        # Only command when the best-known actual state differs; avoids
        # spurious writes on startup / in the hysteresis hold band.
        known = snapshot["valve"] if snapshot["valve"] is not None else self._last_commanded_valve
        if desired != known or self._valve_reconcile_required:
            self._request_automatic_valve(desired, why, entity, known)

    def _request_automatic_valve(self, desired, why, entity, known):
        """Queue a deduplicated command while preserving compensating writes."""
        if known is None and not self._valve_reconcile_required:
            logger.debug(
                "Valve %s wanted (%s) but HA state unknown - not commanding blindly",
                "ON" if desired else "OFF",
                why,
            )
            return
        act = "turn_on" if desired else "turn_off"
        logger.info("Valve %s (%s)", "ON" if desired else "OFF", why)

        # A cancelled request might already be in flight. Queue
        # its opposite even if the older sample appears to match.
        compensating = self._valve_reconcile_required

        def completed(ok):
            if ok:
                self._last_commanded_valve = desired
                self.services.update_device_state("valve", desired)
            elif compensating:
                self._valve_reconcile_required = True

        if self._request_service(act, entity, completed, deduplicate=True):
            self._valve_reconcile_required = False


def _now() -> float:
    return time.monotonic()


def _write_heartbeat() -> None:
    try:
        os.makedirs(os.path.dirname(config.HEARTBEAT_FILE), exist_ok=True)
        with open(config.HEARTBEAT_FILE, "w", encoding="utf-8") as f:
            f.write(str(int(time.time())))
    except OSError as exc:  # /run may be read-only off-device
        logger.debug("heartbeat write failed: %s", exc)


def _setup_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


def build_app(*, dry_run: bool = False) -> App:
    """Build normal services, or an isolated read-only preview for dry-run."""
    config.validate()
    controller = ValveController(
        start_value=config.VALVE_START_VALUE,
        stop_value=config.VALVE_STOP_VALUE,
        sensor_stale_timeout=config.SENSOR_STALE_TIMEOUT,
        min_switch_interval=config.MIN_SWITCH_INTERVAL,
    )
    client = HaClient(
        base_url=config.HA_URL,
        token=config.HA_TOKEN,
        level_entity=config.HA_WATER_LEVEL_ENTITY,
        pump_entity=config.HA_PUMP_SWITCH_ENTITY,
        valve_entity=config.HA_VALVE_SWITCH_ENTITY,
        timeout=config.HA_TIMEOUT,
        breaker=CircuitBreaker(config.CIRCUIT_OPEN_THRESHOLD, config.CIRCUIT_RESET_TIMEOUT),
        cm_entity=config.TANK_WATER_CM_ENTITY,
    )
    try:
        services = WaterSystemServices(
            tank_instance=config.DEVICE_INSTANCE_TANK,
            pump_startstop_instance=config.PUMP_STARTSTOP_INSTANCE,
            valve_startstop_instance=config.VALVE_STARTSTOP_INSTANCE,
            version=config.SOFTWARE_VERSION,
            capacity_m3=config.TANK_CAPACITY_LITERS / 1000.0,
            on_pump_mode=_mode_handler_wrap(lambda m: app.handle_mode("pump", m)),
            on_valve_mode=_mode_handler_wrap(lambda m: app.handle_mode("valve", m)),
            register=False,
            language=config.LANGUAGE,
            force_null=dry_run,
        )
        app = App(
            client,
            controller,
            services,
            enable_control=config.control_enabled(),
            read_only=dry_run,
        )
        services.set_connected(False)
        services.register()
    except Exception:
        client.close()
        raise
    if dry_run:
        logger.info("Dry run: read-only HA snapshot, in-memory services, no actuator commands")
    elif not app.enable_control:
        logger.warning(
            "Automation DISABLED (ENABLE_CONTROL=False or token unset) - "
            "monitoring only, valve will not be actuated automatically"
        )
    return app


def serve(app: App) -> None:
    # Venus-only dependency: keep dry-run and tests usable off-device.
    from gi.repository import GLib  # pylint: disable=import-outside-toplevel

    app.worker = HaWorker(app.client, GLib.idle_add, config.HA_VALVE_SWITCH_ENTITY)
    timer = GLib.timeout_add(app.loop_interval_ms, app.tick)
    mainloop = GLib.MainLoop()

    def _stop(*_args):
        logger.info("Shutting down")
        mainloop.quit()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    logger.info("dbus-pump %s started (control=%s)", config.SOFTWARE_VERSION, app.enable_control)
    try:
        mainloop.run()
    finally:
        GLib.source_remove(timer)
        app.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description="HA water system -> Venus OS D-Bus bridge")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview one HA snapshot without native D-Bus registration or actuator commands",
    )
    args = parser.parse_args()
    _setup_logging(args.debug)

    if args.dry_run:
        app = build_app(dry_run=True)
        try:
            app.tick()
            for name, svc in (
                ("tank", app.services.tank),
                ("pump", app.services.pump),
                ("valve", app.services.valve),
            ):
                print(name, svc.service_name, dict(getattr(svc, "items", {})))
            return 0
        finally:
            # Normal shutdown closes the physical valve. Dry-run only closes
            # the HTTP session, including when polling or printing fails.
            app.client.close()

    if not VEDBUS_AVAILABLE:
        logger.error("vedbus/dbus not available - run on the Cerbo GX")
        return 1
    from dbus.mainloop.glib import DBusGMainLoop  # pylint: disable=import-outside-toplevel

    # Must run before any VeDbusService is created (services export onto the
    # default main loop).
    DBusGMainLoop(set_as_default=True)
    serve(build_app())
    return 0


if __name__ == "__main__":
    sys.exit(main())
