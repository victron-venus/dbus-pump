# dbus-pump deployment notes

Findings from the first bring-up (2026-08-23), Cerbo GX on Raspberry Pi 3,
Venus OS v3.75, portal ID `b827ebea1ece`.

## Device facts

- Native GX "Pump start/stop" feature **disabled** (relay function 0 free) →
  no conflict; we took `tank` instance 21 and `pump.startstop1` (pump) /
  `pump.startstop2` (valve).
- Services run under daemontools at `/data/dbus-pump`, symlinked from
  `/service/dbus-pump`; logs in `/var/log/dbus-pump` via multilog.
- Deploy path: `./deploy.sh` from a dev machine (rsync + on-device
  `update.sh`), or the auto-deploy webhook from inverter-monitoring.

## vedbus / Venus gotchas hit during bring-up

| Symptom | Cause | Fix |
|---|---|---|
| `Invalid bus name 'com.victronenergy.tank.21'` | bus names forbid digits after the last dot | text suffix (`tank.ha_tank21`); instance only in `/DeviceInstance` |
| `KeyError: Can't register object-path '/'` on 2nd service | VeDbusService defaults to the shared bus and exports `/` | one `dbus.SystemBus(private=True)` per service |
| `add_path() unexpected kwarg 'onchange'` | vedbus API is `onchangecallback=path,value` | aligned mock + real signature |
| `'VeDbusService' has no attribute 'items'` | it's not a dict | mirror values as instance attributes |
| empty multilog | stderr not captured | `exec 2>&1` in service run script |
| CI-only failure: first valve command suppressed | fresh `time.monotonic()` ≈ small value + `_last_transition = 0.0` looks like a recent transition | init `_last_transition = clock() - min_switch_interval` |
| crash-loop after update: stale supervise/run processes with `(deleted)` cwd | daemontools inode churn across updates | `update.sh` reaps by `/proc/*/cwd` scan before reinstall |

## Verification results

- MQTT dump on device: `N/b827ebea1ece/tank/21/Level {"value":66.0}`,
  `pump/1/State 1`, `pump/2/State 0` ✓
- Keepalive round trip from laptop: publish `R/<portal>/keepalive` → full
  dump ends with `full_publish_completed` ✓
- Failure drills: HA down → circuit breaker opens after 5 consecutive
  failures, `/Status=4`, `/Connected=0`, valve fail-closed; HA back → auto
  recovery ✓
- Round-trip valve control deferred until `switch.shutoff_valve` is online
  again in HA (app correctly refused to command an unknown-state switch).

## Desktop consumer (inverter-desktop ≥ PR #258)

Water section is Cerbo-MQTT-first: subscribes
`N/<portal>/tank/+/Level` + `N/<portal>/pump/+/State`, maps
`pump/<water_pump_instance>` → pump, `pump/<water_valve_instance>` → valve
(defaults 1/2). Falls back to direct HA entities only when no MQTT data
arrives. Valve/pump toggles from the desktop still route via HA REST
(unchanged); single-control-plane writes over `W/...//Mode` were evaluated
and skipped.

## Residual risks

- Cerbo power loss while valve open: SIGTERM handler closes it, but a hard
  power cut cannot command the valve closed (documented in README).
- Two writers to HA switches (desktop toggle vs automation) are
  last-write-wins by design.
