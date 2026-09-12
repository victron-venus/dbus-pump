# Changelog

All notable changes to this project will be documented in this file.

## [0.1.3] - 2026-09-12

### Fixed
- Defer native D-Bus name registration until all mandatory and device paths, configured initial values, and callbacks are ready. Register each private-bus service once.
- Publish the production service as disconnected until a valid source snapshot arrives; preserve control defaults and existing freshness deadlines.
- Verify native registration order, configured values, idempotence and failure before publication with isolated fake-bus regressions.

## 0.1.2

- Preserve request-start monotonic freshness so delayed replies cannot renew expired telemetry.

- Handle missing sensor values without interrupting the main-loop callback.
- Reject non-finite level/height and malformed HA template responses.
- Keep the existing monotonic stale-sensor deadline and manual mode priority; invalid measurements cannot refresh the deadline.
- Publish unavailable remaining volume for unknown or expired level instead of a false empty-tank value.
- Cover invalidity, the original stale-close timing, recovery, and installer tests from arbitrarily named worktrees.

## [Unreleased]

### Added
- `TANK_CAPACITY_LITERS` config → `/Capacity` on the tank service; GUIv2 now
  renders the gauge in liters.
- Remaining liters computed locally from the raw water-column sensor
  (`TANK_WATER_CM_ENTITY`) using configured tank geometry (`TANK_OFFSET_CM`,
  `TANK_RADIUS_CM`) — no HA-side template sensor; falls back to
  `Capacity × Level` when the raw sensor is unavailable.

## [Unreleased]

### Documentation
- README: full water data-flow diagram (HA sensors → dbus-pump → D-Bus → Cerbo
  MQTT topics → consumers) and valve hysteresis sequence diagram; consumer table.

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
