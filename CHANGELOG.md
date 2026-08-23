# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-08-23

### Added
- HA-backed water tank/pump/valve D-Bus bridge for Venus OS.
- Three services: `com.victronenergy.tank.ha_tank<N>`, two `pump.startstop`
  instances (pump + city-water valve) with writable `/Mode`.
- Hysteresis valve automation (open ≤ START, close ≥ STOP), stale-sensor
  fail-safe (force CLOSED), manual `/Mode` override, anti-chatter interval,
  valve force-closed on SIGTERM/SIGINT.
- HA REST client with circuit breaker (5 failures → 60 s open), last-known
  values while unreachable, once/min error throttle.
- deploy.sh / update.sh / restart.sh trio; daemontools unit with multilog.
- CI via venus-os-ci-toolkit python workflow + secrets-template validation.

### Verified on device (Cerbo GX, Venus v3.75)
- All three services register; tank level live on MQTT
  (`N/<portal>/tank/21/Level`).
- Failure drill: HA unreachable → circuit breaker opens, `/Status` fault,
  `/Connected` 0; auto-recovery after restore.
- Keep-alive dump from laptop broker works (9255 msgs).

### Known limitations
- Round-trip control drill pending `switch.shutoff_valve` hardware back
  online (entity currently unavailable in HA; automation correctly refuses
  to command an unknown state).
