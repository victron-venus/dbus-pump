"""Entry point: HA <-> D-Bus water system bridge."""

import argparse
import logging
import os
import signal
import sys
import time

from dbus_pump import config
from dbus_pump.control import MODE_OFF, MODE_ON, ValveController
from dbus_pump.ha_client import HaClient
from dbus_pump.service import VEDBUS_AVAILABLE, WaterSystemServices

logger = logging.getLogger("dbus-pump")


def _mode_handler_wrap(handler):
    """Vedbus onchange signatures vary across versions; take the last arg."""

    def cb(*args):
        handler(args[-1])

    return cb


class App:
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

    # --- GX -> HA manual mode writes ----------------------------------------
    def handle_mode(self, which: str, mode: int) -> None:
        entity = config.HA_VALVE_SWITCH_ENTITY if which == "valve" else config.HA_PUMP_SWITCH_ENTITY
        logger.info("%s /Mode changed to %s", which, mode)
        if which == "valve":
            self.controller.set_mode(mode)
        action = {MODE_ON: ("turn_on", True), MODE_OFF: ("turn_off", False)}.get(mode)
        if action:
            act, state = action
            if self.client.call_service("switch", act, entity):
                self.services.update_device_state(which, state)
                self._last_commanded_valve = (
                    state if which == "valve" else self._last_commanded_valve
                )

    def shutdown(self) -> None:
        """Fail-safe: force the city-water valve CLOSED before exiting (Q5).

        Best effort — a dead HA or open breaker still leaves the valve as-is;
        residual risk of Cerbo power loss is documented in the README.
        """
        try:
            entity = config.HA_VALVE_SWITCH_ENTITY
            if self.client.call_service("switch", "turn_off", entity):
                logger.info("Shutdown: valve forced closed")
        except Exception:
            logger.exception("Shutdown: failed to close valve")

    # --- main cycle ----------------------------------------------------------
    def tick(self) -> bool:
        snapshot = self.client.poll()
        now_ok = snapshot["ok"]
        if now_ok:
            self.last_ok_time = _now()
        ha_reachable = (
            self.last_ok_time is not None
            and (_now() - self.last_ok_time) < config.SENSOR_STALE_TIMEOUT
        )
        self.services.set_connected(ha_reachable)

        level = snapshot["level"] if now_ok else self.controller_level_if_fresh(snapshot)
        if level is not None:
            self.services.update_tank_level(level)
        else:
            # Stale: publish invalid level so consumers see the gap.
            self.services.update_tank_level(None)

        self.services.update_device_state("pump", snapshot["pump"])
        self.services.update_device_state("valve", snapshot["valve"])

        if self.enable_control:
            fresh = now_ok and snapshot["level"] is not None
            desired, why = self.controller.update(snapshot["level"], fresh)
            # Only command when the best-known actual state differs; avoids
            # spurious writes on startup / in the hysteresis hold band.
            known = (
                snapshot["valve"] if snapshot["valve"] is not None else self._last_commanded_valve
            )
            if desired != known:
                if known is None:
                    logger.debug(
                        "Valve %s wanted (%s) but HA state unknown - not commanding blindly",
                        "ON" if desired else "OFF",
                        why,
                    )
                else:
                    entity = config.HA_VALVE_SWITCH_ENTITY
                    act = "turn_on" if desired else "turn_off"
                    logger.info("Valve %s (%s)", "ON" if desired else "OFF", why)
                    if self.client.call_service("switch", act, entity):
                        self._last_commanded_valve = desired
                        self.services.update_device_state("valve", desired)
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


def _write_heartbeat() -> None:
    try:
        os.makedirs(os.path.dirname(config.HEARTBEAT_FILE), exist_ok=True)
        with open(config.HEARTBEAT_FILE, "w") as f:
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
    )
    services = WaterSystemServices(
        tank_instance=config.DEVICE_INSTANCE_TANK,
        pump_startstop_instance=config.PUMP_STARTSTOP_INSTANCE,
        valve_startstop_instance=config.VALVE_STARTSTOP_INSTANCE,
        version=config.SOFTWARE_VERSION,
        on_pump_mode=_mode_handler_wrap(lambda m: app.handle_mode("pump", int(m))),
        on_valve_mode=_mode_handler_wrap(lambda m: app.handle_mode("valve", int(m))),
    )
    app = App(client, controller, services, enable_control=config.control_enabled())
    if not app.enable_control:
        logger.warning(
            "Automation DISABLED (ENABLE_CONTROL=False or token unset) - "
            "monitoring only, valve will not be actuated automatically"
        )
    return app


def serve(app: App) -> None:
    import gobject  # provided by Venus OS python env

    gobject.timeout_add(app.loop_interval_ms, app.tick)
    mainloop = gobject.MainLoop()

    def _stop(*_args):
        logger.info("Shutting down")
        app.shutdown()
        mainloop.quit()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    logger.info("dbus-pump %s started (control=%s)", config.SOFTWARE_VERSION, app.enable_control)
    mainloop.run()


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
    serve(build_app())
    return 0


if __name__ == "__main__":
    sys.exit(main())
