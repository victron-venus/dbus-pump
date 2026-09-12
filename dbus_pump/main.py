"""Entry point: HA <-> D-Bus water system bridge."""

import argparse
import logging
import math
import os
import signal
import sys
import time

from dbus_pump import config
from dbus_pump.control import MODE_OFF, MODE_ON, ValveController
from dbus_pump.ha_client import HaClient
from dbus_pump.service import VEDBUS_AVAILABLE, WaterSystemServices
from dbus_pump.worker import HaWorker

logger = logging.getLogger("dbus-pump")


def _mode_handler_wrap(handler):
    """Vedbus onchange signatures vary across versions; take the last arg."""

    def cb(*args):
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
    ) -> None:
        self.client = client
        self.controller = controller
        self.services = services
        self.enable_control = enable_control
        self.last_ok_time: float | None = None
        self._last_commanded_valve: bool | None = None
        self.loop_interval_ms = max(250, int(config.POLL_INTERVAL * 1000))
        self.worker: HaWorker | None = None
        self._last_snapshot = {"level": None, "pump": None, "valve": None, "ok": False}
        self._valve_reconcile_required = False

    # --- GX -> HA manual mode writes ----------------------------------------
    def handle_mode(self, which: str, mode: int) -> bool:
        entity = config.HA_VALVE_SWITCH_ENTITY if which == "valve" else config.HA_PUMP_SWITCH_ENTITY
        logger.info("%s /Mode changed to %s", which, mode)
        action = {MODE_ON: ("turn_on", True), MODE_OFF: ("turn_off", False)}.get(mode)
        if action:
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
                self._last_commanded_valve = (
                    state if which == "valve" else self._last_commanded_valve
                )
                if which == "valve":
                    self._valve_reconcile_required = False

            if not self._request_service(act, entity, completed):
                return False
        if which == "valve":
            self.controller.set_mode(mode)
            if not action and self.worker is not None and self.enable_control:
                # Re-evaluate AUTO against the existing sample without making
                # it fresh. This also compensates an in-flight manual ON when
                # the automatic policy now requires OFF.
                self.apply_snapshot(dict(self._last_snapshot, ok=False))
        return True

    def _request_service(self, action, entity, callback, deduplicate=False):
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
            _write_heartbeat()
            return True
        started_at = _now()
        snapshot = self.client.poll()
        return self.apply_snapshot(dict(snapshot, _sample_started_at=started_at))

    def apply_snapshot(self, snapshot) -> bool:
        """Apply HA results on the D-Bus main loop (also used by dry-run)."""
        self._last_snapshot = dict(snapshot)
        now = _now()
        started_at = snapshot.get("_sample_started_at", now)
        now_ok = snapshot["ok"] and 0 <= now - started_at < config.SENSOR_STALE_TIMEOUT
        if now_ok:
            self.last_ok_time = started_at
        ha_reachable = (
            self.last_ok_time is not None
            and (_now() - self.last_ok_time) < config.SENSOR_STALE_TIMEOUT
        )
        self.services.set_connected(ha_reachable)

        level = snapshot["level"] if now_ok else self.controller_level_if_fresh(snapshot)
        # Liters computed here from the raw height; falls back to Capacity x Level.
        self.services.update_tank_level(
            level,
            remaining_m3=_tank_remaining_m3(
                snapshot.get("cm") if level is not None else None,
                config.TANK_OFFSET_CM,
                config.TANK_RADIUS_CM,
            ),
        )

        self.services.update_device_state("pump", snapshot["pump"])
        self.services.update_device_state("valve", snapshot["valve"])

        if self.enable_control:
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
            known = (
                snapshot["valve"] if snapshot["valve"] is not None else self._last_commanded_valve
            )
            if desired != known or self._valve_reconcile_required:
                if known is None and not self._valve_reconcile_required:
                    logger.debug(
                        "Valve %s wanted (%s) but HA state unknown - not commanding blindly",
                        "ON" if desired else "OFF",
                        why,
                    )
                else:
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
        elif snapshot.get("valve") is not None:
            self._last_commanded_valve = snapshot["valve"]

        _write_heartbeat()
        return True

    def controller_level_if_fresh(self, snapshot):
        # Last-known level stays valid only inside the stale window.
        if (
            self.last_ok_time is not None
            and (_now() - self.last_ok_time) < config.SENSOR_STALE_TIMEOUT
        ):
            return snapshot["level"]
        return None


def _now() -> float:
    return time.monotonic()


def _tank_remaining_m3(water_cm: float | None, offset_cm: float, radius_cm: float) -> float | None:
    """Remaining volume from raw water-column height, computed here so HA is
    only a sensor source. Cylinder with a dead zone: negative readings (sensor
    below the offset) clamp to 0. None when the reading or geometry is absent
    (caller falls back to Capacity x Level)."""
    if water_cm is None or radius_cm <= 0:
        return None
    liters = (water_cm - offset_cm) * math.pi * radius_cm * radius_cm / 1000.0
    return max(0.0, liters) / 1000.0


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


def build_app() -> App:
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
        cm_entity=config.TANK_WATER_CM_ENTITY,
    )
    services = WaterSystemServices(
        tank_instance=config.DEVICE_INSTANCE_TANK,
        pump_startstop_instance=config.PUMP_STARTSTOP_INSTANCE,
        valve_startstop_instance=config.VALVE_STARTSTOP_INSTANCE,
        version=config.SOFTWARE_VERSION,
        capacity_m3=config.TANK_CAPACITY_LITERS / 1000.0,
        on_pump_mode=_mode_handler_wrap(lambda m: app.handle_mode("pump", int(m))),
        on_valve_mode=_mode_handler_wrap(lambda m: app.handle_mode("valve", int(m))),
        register=False,
    )
    app = App(client, controller, services, enable_control=config.control_enabled())
    services.set_connected(False)
    services.register()
    if not app.enable_control:
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
        help="run one control cycle against a NullDbusService and exit",
    )
    args = parser.parse_args()
    _setup_logging(args.debug)

    if args.dry_run:
        app = build_app()
        app.tick()
        for name, svc in (
            ("tank", app.services.tank),
            ("pump", app.services.pump),
            ("valve", app.services.valve),
        ):
            print(name, svc.service_name, dict(getattr(svc, "items", {})))
        return 0

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
