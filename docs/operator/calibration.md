# Sensor units and tank calibration

[Operator guide](README.md) · [Configuration](configuration.md) · [Troubleshooting](troubleshooting.md)

`/Level` is always a percentage. Select the source unit with
`HA_WATER_LEVEL_UNIT`; the name of an HA entity is not sufficient evidence.
For a centimetre sensor use `"cm"`. For an already normalized percentage use
`"%"` (the backward-compatible default).

## Vertical cylindrical tank

For a vertical cylinder with constant cross-section:

```text
height_cm = max(0, reading_cm - TANK_OFFSET_CM)
liters = height_cm × π × TANK_RADIUS_CM² / 1000
bounded_liters = min(TANK_CAPACITY_LITERS, liters)
level_percent = 100 × bounded_liters / TANK_CAPACITY_LITERS
remaining_m3 = bounded_liters / 1000
```

The empty offset is the sensor reading when usable water is zero. It is not an
extra amount to add. The radius is half the inside diameter. The model assumes
height increases with water volume; an ultrasonic **distance to the surface**
needs conversion to water height before use. Horizontal cylinders, irregular
tanks and sloped installations require their own calibrated percentage source;
this vertical-cylinder formula does not represent them.

![Linear percentage versus measured centimetres, clamped below empty and above capacity; 93 cm corresponds to about 77 percent.](../assets/calibration.svg)

With capacity **387 L**, radius **35.56 cm** and empty offset **18 cm**:

- Each centimetre above empty adds about **3.973 L**.
- Empty is `18 cm`; modeled full is approximately `115.418 cm`.
- `93 cm` means `75 cm` of usable water, about **297.94 L**, **76.99%**.
- D-Bus rounding displays approximately `/Level = 77.0` and
  `/Remaining = 0.298 m³` (298 L).

The graph is calculated from these configured example inputs. It is not a
recorded fill test, sensor trace or independent validation of tank capacity.

## Choosing the data path

In `cm` mode the configured primary level reading drives both percentage and
remaining volume, using the same calibration. This prevents mixing a percent
from one interpretation with liters from another.

In `%` mode the primary reading supplies the normalized percentage and remaining
volume is capacity times that percentage. `TANK_WATER_CM_ENTITY` is retained for
diagnostics only; it no longer overrides volume with a second, potentially
inconsistent sensor. This is a migration change: configurations that previously
used one sensor for percent and another for liters now have one authoritative
measurement. If the primary level is unavailable or expired, level and remaining
volume become unavailable; an unknown tank must not appear empty.

Finite valid readings are bounded to the physical 0–100% / 0–capacity range.
Unsupported configured units or invalid height calibration fail startup.
Malformed/non-finite readings and a nonempty HA unit that disagrees with the
configured unit are rejected as fresh evidence. A missing HA unit attribute is
allowed; the explicit configuration remains authoritative. Check logs and correct the configuration instead
of changing control thresholds to compensate for a unit error.

## Commissioning without toggling equipment

1. Inspect HA's current state and `unit_of_measurement` for the primary sensor
   and optional raw height. Record sanitized entity names, units and values.
2. Confirm vertical-cylinder geometry, actual usable capacity and empty offset.
   Keep `ENABLE_CONTROL=False` and retain the established HA control owner.
3. Compare at least empty, an intermediate fill and full measurements against
   known volume, when those observations are available through normal operation.
4. Calculate the expected percentage and liters, then compare fresh D-Bus and
   MQTT values, allowing for their rounding.
5. Check the boundary cases in offline tests before any on-device failure drill.
   Do not disconnect a real sensor or force an actuator merely to complete a
   documentation checklist.

Record the firmware/version, geometry, observations and test scope separately.
A calculation can establish conversion correctness for given inputs; only site
measurements can establish that those inputs model the real tank correctly.
