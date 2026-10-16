"""D-Bus service registration (Venus OS).

Registers three services:
  com.victronenergy.tank.ha_tank<N>   - tank level from HA
  com.victronenergy.pump.startstop<N> - pump
  com.victronenergy.pump.startstop<M> - city water valve

Off-GX (tests / dev laptop) a NullDbusService stand-in is used so the module
imports cleanly without velib_python/dbus.
"""

import logging

from .i18n import normalize_language, translate

# Shared protocol identifiers keep publication and update paths consistent.
DBUS_STATE_PATH = "/State"
DBUS_MODE_PATH = "/Mode"
DBUS_CONNECTED_PATH = "/Connected"

logger = logging.getLogger(__name__)

VEDBUS_AVAILABLE = False
try:
    import sys

    sys.path.insert(0, "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python")
    import dbus
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
        self._gettext: dict[str, callable] = {}

    def add_path(
        self,
        path,
        value,
        description="",
        writeable=False,
        onchangecallback=None,
        gettextcallback=None,
        **_kw,
    ):
        self.items[path] = value
        if onchangecallback:
            self._onchange[path] = onchangecallback
        if gettextcallback:
            self._gettext[path] = gettextcallback

    def get_text(self, path):
        """Mirror native GetText, including its invalid-value marker."""
        value = self.items[path]
        if value is None:
            return "---"
        if path in self._gettext:
            return self._gettext[path](path, value)
        if path == "/ProductId":
            return f"0x{value:X}"
        return str(value)

    def __setitem__(self, path, value):
        old = self.items.get(path)
        self.items[path] = value
        cb = self._onchange.get(path)
        if cb and old != value:
            cb(path, value)  # match vedbus (path, value) signature

    def __getitem__(self, path):
        return self.items[path]

    def __delitem__(self, path):
        del self.items[path]
        self._onchange.pop(path, None)
        self._gettext.pop(path, None)


def _make_service(service_name: str, *, force_null: bool = False):
    if VEDBUS_AVAILABLE and not force_null:
        # One private connection per service: VeDbusService exports at '/',
        # and a single connection can register that object path only once.
        return VeDbusService(service_name, bus=dbus.SystemBus(private=True), register=False)
    return NullDbusService(service_name)


def _identity_paths(
    svc,
    product_name: str,
    version: str,
    custom_name: str,
    instance: int,
    connection: str,
    connected_text=None,
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
    svc.add_path(DBUS_CONNECTED_PATH, 1, gettextcallback=connected_text)


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
        capacity_m3: float = 0.0,
        register: bool = True,
        language: str = "en",
        force_null: bool = False,
    ) -> None:
        self._registered = False
        self._uses_native = VEDBUS_AVAILABLE and not force_null
        self.language = normalize_language(language)

        def enum_text(messages):
            # GetText callbacks affect presentation only. Native vedbus handles
            # invalid (None) values itself and returns the stable marker '---'.
            def get_text(_path, value):
                try:
                    message = messages.get(value, "unknown")
                except TypeError:
                    message = "unknown"  # malformed/unhashable values stay readable
                return translate(message, self.language)

            return get_text

        connected_text = enum_text({0: "disconnected", 1: "connected"})
        mode_text = enum_text({0: "mode.auto", 1: "on", 2: "off"})
        # D-Bus bus names forbid a digit directly after a dot, so the device
        # instance goes into /DeviceInstance only; the name suffix is text.
        tank_bus_name = f"com.victronenergy.tank.ha_tank{tank_instance}"
        self.tank = _make_service(tank_bus_name, force_null=force_null)
        _identity_paths(
            self.tank,
            translate("tank.name", self.language),
            version,
            translate("tank.custom_name", self.language),
            tank_instance,
            "Home Assistant",
            connected_text,
        )
        self.tank.add_path("/Level", None)
        self.tank.add_path("/FluidType", FLUID_TYPE_FRESH_WATER)
        self.capacity_m3 = float(capacity_m3)  # mirror of /Capacity; VeDbusService has no .items
        self.tank.add_path("/Capacity", self.capacity_m3)
        self.tank.add_path("/Remaining", 0.0)
        self.tank.add_path(
            "/Status",
            0,  # 0 = OK
            gettextcallback=enum_text({0: "tank.status.ok", 4: "tank.status.unknown_sensor"}),
        )

        def _make_pump(name: str, inst: int, on_mode, state_text):
            svc = _make_service(f"com.victronenergy.pump.startstop{inst}", force_null=force_null)
            _identity_paths(svc, name, version, name, inst, "Home Assistant", connected_text)
            # None unknown, 0 stopped/closed, 1 on/open.
            svc.add_path(DBUS_STATE_PATH, None, gettextcallback=state_text)
            # vedbus calls onchangecallback(path, value); our handlers take
            # the last arg so both signatures work.
            svc.add_path(
                DBUS_MODE_PATH,
                0,
                writeable=True,
                onchangecallback=on_mode,
                gettextcallback=mode_text,
            )
            svc.add_path("/ActiveTankService", tank_bus_name)
            return svc

        self.pump = _make_pump(
            translate("pump.name", self.language),
            pump_startstop_instance,
            on_pump_mode,
            enum_text({0: "off", 1: "on"}),
        )
        self.valve = _make_pump(
            translate("valve.name", self.language),
            valve_startstop_instance,
            on_valve_mode,
            enum_text({0: "valve.closed", 1: "valve.open"}),
        )

        if register:
            self.register()

    def register(self) -> None:
        """Publish the complete service group after callers finish setup."""
        if not self._registered:
            if self._uses_native:
                for service in (self.tank, self.pump, self.valve):
                    service.register()
            self._registered = True

    # --- updates -------------------------------------------------------------
    def update_tank_level(self, level_pct: float | None, remaining_m3: float | None = None) -> None:
        """Publish canonical level and derive volume from capacity by default.

        The application normalizes its authoritative measurement to a volume
        percentage before calling this method. An explicit remaining volume
        remains supported for existing callers of the service API.
        """
        self.tank["/Level"] = round(level_pct, 1) if level_pct is not None else None
        if remaining_m3 is None and level_pct is not None:
            remaining_m3 = self.capacity_m3 * (level_pct / 100.0)
        self.tank["/Remaining"] = round(remaining_m3, 3) if remaining_m3 is not None else None
        self.tank["/Status"] = 0 if level_pct is not None else 4  # 4 = unknown sensor

    def set_connected(self, connected: bool) -> None:
        value = 1 if connected else 0
        self.tank[DBUS_CONNECTED_PATH] = value
        self.pump[DBUS_CONNECTED_PATH] = value
        self.valve[DBUS_CONNECTED_PATH] = value

    def update_device_state(self, which: str, running: bool | None) -> None:
        svc = self.pump if which == "pump" else self.valve
        # None = HA unavailable/unknown — do not publish as stopped (0).
        if running is None:
            svc[DBUS_STATE_PATH] = None
        else:
            svc[DBUS_STATE_PATH] = 1 if running else 0

    def set_mode_quietly(self, which: str, mode: int) -> None:
        """Set /Mode without re-triggering the onchange handler loop."""
        svc = self.pump if which == "pump" else self.valve
        if isinstance(svc, NullDbusService):
            svc.items[DBUS_MODE_PATH] = mode  # bypass onchange
        else:
            svc[DBUS_MODE_PATH] = mode
