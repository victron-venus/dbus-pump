"""D-Bus service registration (Venus OS).

Registers three services:
  com.victronenergy.tank.<N>          - tank level from HA
  com.victronenergy.pump.startstop<N> - pump
  com.victronenergy.pump.startstop<M> - city water valve

Off-GX (tests / dev laptop) a NullDbusService stand-in is used so the module
imports cleanly without velib_python/dbus.
"""

import logging

logger = logging.getLogger(__name__)

VEDBUS_AVAILABLE = False
try:
    import sys

    sys.path.insert(0, "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python")
    import dbus  # noqa: F401
    from vedbus import VeDbusService

    VEDBUS_AVAILABLE = True
except ImportError:
    logger.info("vedbus/dbus unavailable - using NullDbusService (off-GX mode)")


class NullDbusService:
    """Dict-like stand-in for VeDbusService used off-device."""

    def __init__(self, service_name: str, **_kwargs) -> None:
        self.service_name = service_name
        self.items: dict[str, object] = {}
        self._onchange: dict[str, callable] = {}

    def add_path(self, path, value, description="", writeable=False, onchange=None, **_kw):
        self.items[path] = value
        if onchange:
            self._onchange[path] = onchange

    def __setitem__(self, path, value):
        old = self.items.get(path)
        self.items[path] = value
        cb = self._onchange.get(path)
        if cb and old != value:
            cb(value)

    def __getitem__(self, path):
        return self.items[path]

    def __delitem__(self, path):
        del self.items[path]


def _make_service(service_name: str):
    if VEDBUS_AVAILABLE:
        return VeDbusService(service_name)
    return NullDbusService(service_name)


def _identity_paths(
    svc, product_name: str, version: str, custom_name: str, instance: int, connection: str
):
    svc.add_path("/Mgmt/ProcessName", "dbus-pump")
    svc.add_path("/Mgmt/ProcessVersion", version)
    svc.add_path("/Mgmt/Connection", connection)
    svc.add_path("/DeviceInstance", instance)
    svc.add_path("/ProductId", 0xFFFF)  # generic/unknown product
    svc.add_path("/ProductName", product_name)
    svc.add_path("/FirmwareVersion", version)
    svc.add_path("/HardwareVersion", "n/a")
    svc.add_path("/Serial", f"dbuspump-{instance}")
    svc.add_path("/CustomName", custom_name)
    svc.add_path("/Connected", 1)


FLUID_TYPE_FRESH_WATER = 1


class WaterSystemServices:
    """Owns the three D-Bus services and their writable paths."""

    def __init__(
        self,
        tank_instance: int,
        pump_startstop_instance: int,
        valve_startstop_instance: int,
        version: str,
        on_pump_mode=None,
        on_valve_mode=None,
    ) -> None:
        self.tank = _make_service(f"com.victronenergy.tank.{tank_instance}")
        _identity_paths(
            self.tank, "Water tank", version, "Water tank (HA)", tank_instance, "Home Assistant"
        )
        self.tank.add_path("/Level", None)
        self.tank.add_path("/FluidType", FLUID_TYPE_FRESH_WATER)
        self.tank.add_path("/Capacity", 0.0)
        self.tank.add_path("/Remaining", 0.0)
        self.tank.add_path("/Status", 0)  # 0 = OK

        def _make_pump(name: str, inst: int, on_mode):
            svc = _make_service(f"com.victronenergy.pump.startstop{inst}")
            _identity_paths(svc, name, version, name, inst, "Home Assistant")
            svc.add_path("/State", 0)  # 0 stopped, 1 running
            svc.add_path(
                "/Mode",
                0,
                writeable=True,
                onchange=on_mode,
            )
            svc.add_path("/ActiveTankService", f"com.victronenergy.tank.{tank_instance}")
            return svc

        self.pump = _make_pump("Water pump", pump_startstop_instance, on_pump_mode)
        self.valve = _make_pump("City water valve", valve_startstop_instance, on_valve_mode)

    # --- updates -------------------------------------------------------------
    def update_tank_level(self, level_pct: float | None) -> None:
        self.tank["/Level"] = round(level_pct, 1) if level_pct is not None else None
        remaining = (
            self.tank.items["/Capacity"] * (level_pct / 100.0) if level_pct is not None else 0.0
        )
        self.tank["/Remaining"] = round(remaining, 3)
        self.tank["/Status"] = 0 if level_pct is not None else 4  # 4 = unknown sensor

    def set_connected(self, connected: bool) -> None:
        value = 1 if connected else 0
        self.tank["/Connected"] = value
        self.pump["/Connected"] = value
        self.valve["/Connected"] = value

    def update_device_state(self, which: str, running: bool | None) -> None:
        svc = self.pump if which == "pump" else self.valve
        svc["/State"] = 1 if running else 0

    def set_mode_quietly(self, which: str, mode: int) -> None:
        """Set /Mode without re-triggering the onchange handler loop."""
        svc = self.pump if which == "pump" else self.valve
        if isinstance(svc, NullDbusService):
            svc.items["/Mode"] = mode  # bypass onchange
        else:
            svc["/Mode"] = mode
