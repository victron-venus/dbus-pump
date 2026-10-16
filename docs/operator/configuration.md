# Configuration and interfaces

[Operator guide](README.md) · [Calibration](calibration.md) · [Control](control.md)

Configuration is Python in repository-root `local_config.py`, loaded at process
startup. Copy [the example](../../local_config.example.py), protect its token and
never commit it. Restarting to load changes can attempt to close the valve.

## Home Assistant and units

- `HA_URL`: REST base URL, without `/api`; trailing slash is removed. Default empty.
- `HA_TOKEN`: private long-lived token. Default empty. Never include it in logs,
  screenshots, reports or public configuration snippets.
- `HA_WATER_LEVEL_ENTITY`: source level entity. Default empty.
- `HA_WATER_LEVEL_UNIT`: `%` for a percentage or `cm` for measured height. Default
  `%` preserves percentage-based configurations. Set `cm` explicitly for height.
- `HA_PUMP_SWITCH_ENTITY`: pump power switch. Default empty. The configured
  installation uses `switch.pump_power_enable`, replacing `switch.pump_switch`.
- `HA_VALVE_SWITCH_ENTITY`: valve switch. Default empty; configured installation
  uses `switch.shutoff_valve`.

Entity names do not establish units. The configured installation's
`sensor.water_level_2_water_level` and `sensor.water_cm` both report **cm**.
Do not copy an old “level (%)” comment into a new configuration.

## Tank geometry

- `TANK_CAPACITY_LITERS`: usable capacity in L, default `0.0`.
- `TANK_WATER_CM_ENTITY`: optional raw height sensor for diagnostics only, default empty.
  It no longer independently overrides `/Remaining`.
- `TANK_OFFSET_CM`: source reading at empty, default `0.0` cm.
- `TANK_RADIUS_CM`: vertical cylinder radius, default `0.0` cm.

Height-to-percentage conversion requires finite, positive capacity and radius,
and a finite offset. The configured installation uses `387.0 L`, `18.0 cm`
offset and `35.56 cm` radius. These are calibration inputs, not universal defaults.
Invalid `cm` geometry or an unsupported configured unit fails startup.
A nonempty HA `unit_of_measurement` must match the configured unit; a missing
attribute is allowed. See [calibration](calibration.md) for the formula and sensor/geometry restrictions.

## Identity and localization

- `DEVICE_INSTANCE_TANK = 21`
- `PUMP_STARTSTOP_INSTANCE = 1`
- `VALVE_STARTSTOP_INSTANCE = 2`
- `LANGUAGE = "en"`: display labels; also supports `ru`, `de`, `nl`.

Choose unique instance numbers on the GX. The native relay pump feature normally
uses instance `0`. Instance separation prevents service-name collisions, not two
controllers writing the same physical switch. Display translation leaves bus
names, paths, entities, instance numbers and machine-readable values stable.
See [localization](localization.md).

## Automatic control and polling

- `ENABLE_CONTROL = False`: permits automatic valve decisions when true and a
  non-placeholder HA token is configured. It does not block manual `/Mode`
  commands or shutdown closure.
- `VALVE_START_VALUE = 30.0`: open at or below this percentage.
- `VALVE_STOP_VALUE = 85.0`: close at or above this percentage; must exceed start.
- `SENSOR_STALE_TIMEOUT = 120.0`: seconds before level evidence expires.
- `MIN_SWITCH_INTERVAL = 60.0`: seconds between normal policy transitions.
- `POLL_INTERVAL = 2.0`: seconds between scheduled polls.
- `HA_TIMEOUT = 3.0`: per-request HTTP timeout, seconds.
- `CIRCUIT_OPEN_THRESHOLD = 5`: consecutive failures before circuit opens.
- `CIRCUIT_RESET_TIMEOUT = 60.0`: seconds until the circuit permits a retry.

The pump has no automatic level policy. Review [control ownership](control.md)
before enabling valve automation, especially when HA automations already run.

## D-Bus and MQTT contract

The tank service is `com.victronenergy.tank.ha_tank<N>`; pump and valve use
`com.victronenergy.pump.startstop<P>` and `...startstop<V>`.

- Tank `/Level`: percentage, rounded to one decimal; unavailable for invalid or
  expired data. `/Status`: `0` valid, `4` unknown sensor.
- `/Capacity` and `/Remaining`: **m³**, not liters. Remaining volume is rounded
  to three decimals, so displayed liters may round to the nearest liter.
- `/Connected`: `0` during startup/disconnection, `1` for a valid connected snapshot.
- Switch `/State`: `0` off/closed, `1` on/open, unavailable for unknown.
- Switch `/Mode`: writable `0` AUTO, `1` ON, `2` OFF. Acceptance means queued;
  it is not confirmation of physical movement.
- `/ActiveTankService`: stable tank bus name. `/DeviceInstance`, `/Serial` and
  other identity fields must not be translated.

Venus forwards telemetry to `N/<portal>/tank/<N>/Level` and
`N/<portal>/pump/<P-or-V>/State`. Configure each consumer with the correct portal
and instances. GX/VRM use native services; MQTT consumers do not need the HA token.
Historical clients may still write directly to HA, so verify ownership rather
than assuming that a shared read path creates a single command owner.
