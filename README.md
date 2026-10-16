# dbus-pump

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Nederlands](README.nl.md)

**Version scope:** the explicit unit contract, diagnostic-only secondary sensor, runtime
localization and command-validation changes below are **unreleased development
changes**. Use them with this source revision or a later release that includes
them; older installed releases may behave differently. See [CHANGELOG.md](CHANGELOG.md).

[![Fuzzing: RC only](https://img.shields.io/badge/Fuzzing-RC%20only-blue)](docs/fuzzing.md)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15438/badge)](https://www.bestpractices.dev/projects/15438)

A Home Assistant water-tank, pump and valve bridge for **Victron Venus OS**.
It runs on the Cerbo GX, reads HA entities and publishes native D-Bus services
for GX displays and Cerbo MQTT consumers. Optional valve automation uses level
hysteresis; pump control is manual.

![HA readings pass through unit conversion on Cerbo to native tank and pump services; optional commands return to HA.](docs/assets/architecture.svg)

**Choose the sensor unit explicitly.** A reading of `93 cm` must not become
`93%`. Set `HA_WATER_LEVEL_UNIT = "cm"` for a height sensor or `"%"` for an
already normalized percentage. The [calibration guide](docs/operator/calibration.md)
explains the conversion and its limits.

## Quick start

Use the system **Python 3.12.x** and its matching D-Bus/GI libraries on Venus
OS. Development is pinned to Python 3.12.13 in [`.python-version`](.python-version).
The installer does not install Python packages or replace firmware Python.

1. Place the package under `/data/dbus-pump` on the GX.
2. Copy `local_config.example.py` to `local_config.py`, then set your HA URL,
   token, entities, source unit and measured tank dimensions. Keep the token
   private; `local_config.py` is ignored by Git.
3. Leave `ENABLE_CONTROL = False` while verifying telemetry and ownership.
4. Check dependencies and install:

```sh
python3 --version
python3 -c "import requests, dbus; from gi.repository import GLib"
/data/dbus-pump/setup install
svstat /service/dbus-pump-ha /service/dbus-pump-ha/log
readlink /service/dbus-pump-ha
tail -n 40 /var/log/dbus-pump-ha/current
```

The symlink must target `/data/dbus-pump/service/dbus-pump`. The firmware's
separate `/service/dbus-pump` is not this bridge. A running process is only the
first check: also verify fresh `/Level`, `/Remaining`, `/Connected` and switch
states against HA. See [installation, updates and rollback](docs/operator/installation.md).

## Configuration example

These entity names and dimensions describe the configured installation; verify
them against your own HA entity registry and physical tank before reuse.

```python
HA_URL = "http://homeassistant.local:8123"
HA_TOKEN = "replace_with_private_long_lived_token"
HA_WATER_LEVEL_ENTITY = "sensor.water_level_2_water_level"
HA_WATER_LEVEL_UNIT = "cm"
HA_PUMP_SWITCH_ENTITY = "switch.pump_power_enable"
HA_VALVE_SWITCH_ENTITY = "switch.shutoff_valve"
TANK_CAPACITY_LITERS = 387.0
TANK_WATER_CM_ENTITY = "sensor.water_cm"
TANK_OFFSET_CM = 18.0
TANK_RADIUS_CM = 35.56
LANGUAGE = "en"  # en, ru, de, nl
ENABLE_CONTROL = False
```

For this vertical cylindrical tank, `93 cm` represents approximately **297.94 L
and 76.99%**, not 93%. `/Capacity` and `/Remaining` use **m³** on D-Bus; `/Level`
always uses **%**. See the [complete configuration reference](docs/operator/configuration.md).

![Calibration curve for a 387 L vertical cylinder with an 18 cm empty offset and 35.56 cm radius.](docs/assets/calibration.svg)

## Interfaces and control ownership

Default D-Bus identities are stable across languages:

- Tank: `com.victronenergy.tank.ha_tank21`, instance `21`.
- Pump: `com.victronenergy.pump.startstop1`, instance `1`.
- City-water valve: `com.victronenergy.pump.startstop2`, instance `2`.
- MQTT telemetry: `N/<portal>/tank/21/Level`,
  `N/<portal>/pump/1/State`, `N/<portal>/pump/2/State`.

`/Mode` is `0` AUTO, `1` ON, `2` OFF. `/State` is `0` stopped/closed,
`1` running/open, or unavailable when unknown. Language selection translates
display labels, never entity IDs, D-Bus names/paths or numeric values.

**`ENABLE_CONTROL=False` disables automatic decisions only.** Manual D-Bus
requests and graceful-shutdown valve closure can still actuate equipment.
The configured installation has HA automations controlling the pump and valve;
the bridge must remain with AUTO disabled unless an operator deliberately
transfers ownership. There is no lock or arbitration between competing writers.

When enabled, valve AUTO opens at ≤30% and closes at ≥85% by default, with
60 seconds between normal transitions. Stale data triggers a close request
after 120 seconds. Manual ON overrides the automatic stale-level policy.
Power loss or unreachable HA can prevent physical closure. Read the
[control and failure model](docs/operator/control.md) before enabling automation.

![Valve hysteresis holds its previous state between 30 and 85 percent; stale AUTO data requests closure.](docs/assets/hysteresis.svg)

## Operations and troubleshooting

- Wrong percentage or liters: verify HA units, configured capacity and geometry;
  do not infer a unit from an entity name. [Calibration](docs/operator/calibration.md).
- Unavailable/frozen level: check HA connectivity, token and sensor state. Invalid
  readings do not renew the freshness deadline. [Troubleshooting](docs/operator/troubleshooting.md).
- Service missing after boot: inspect `dbus-pump-ha`, then use the documented boot
  recovery procedure. Do not remove the native firmware service.
- A restart may close the valve. Use status and telemetry reads for health checks.

## Documentation and languages

- [Operator guide](docs/operator/README.md): installation, configuration,
  calibration, control, troubleshooting and localization.
- [Wiki source](docs/wiki/Home.md) and [wiki publication](docs/wiki/README.md):
  version-controlled pages and navigation for the GitHub wiki.
- [Architecture and trust boundaries](docs/architecture.md),
  [historical deployment evidence](docs/DEPLOYMENT-NOTES.md).
- [Localization guide](docs/operator/localization.md): runtime labels,
  translation scope and adding a language.
- [SVG source and regeneration](docs/assets/README.md).

## Development and releases

See [CONTRIBUTING.md](CONTRIBUTING.md) for the pinned environment and all required
checks. A focused application run uses:

```sh
.venv/bin/python -m pytest tests/
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
python3 docs/assets/generate.py --check
```

Tests use controlled fixtures off-device. A passing test or generated diagram
does not establish physical valve closure or a completed hardware reboot.

<!-- ci-release-process:start -->
See the [release strategy](RELEASING.md) for validation, nightly, beta, RC and stable promotion rules, and the [operator runbook](docs/release-workflow.md) for local commands.
<!-- ci-release-process:end -->

[Changelog](CHANGELOG.md) · [Security](SECURITY.md) ·
[Quality evidence](docs/quality-evidence.md) · [OpenSSF evidence](docs/openssf-evidence.md) ·
[Governance](GOVERNANCE.md) · [Code of conduct](CODE_OF_CONDUCT.md) ·
[Roadmap](ROADMAP.md) · [RC fuzzing](docs/fuzzing.md)

MIT — see [LICENSE](LICENSE).
