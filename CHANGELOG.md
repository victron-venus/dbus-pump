# Changelog

All notable changes to this project will be documented in this file.

## [0.1.8] - 2026-10-14

### Changed

- Require positive fuzz engine execution counts, instrumented production code and validated seed corpora before accepting RC evidence.
- Add regression tests for malformed reports, unsafe corpora and incomplete seed replay; retain the existing coverage requirements.
- Keep mutation campaigns restricted to public RCs and use deterministic seed checks in ordinary CI.

### Upgrade

Use the documented update procedure and preserve local configuration. No application configuration or data migration is introduced. Keep the previous accepted package available for rollback; the exact candidate still requires applicable device and integration acceptance.

### Security

RC publication rejects absent or invalid source-bound fuzz reports. The fuzz runner bounds corpus paths, file types and size. No application vulnerability or new target-device acceptance is claimed by these tooling changes.

## [0.1.7] - Development line

### Maintenance

- Require bounded fuzzing on public release candidates, with source-bound reports and retained diagnostics; beta and ordinary CI do not run mutation campaigns.

### Upgrade

Use the documented update procedure and retain local configuration. Automated tests do not establish target-device acceptance.

### Security

Release qualification now requires isolated fuzzing against the candidate source. Report findings through SECURITY.md.

## [0.1.6] - Development line

### Fixed
- Preserve the stale-close valve latch while fresh tank readings recover inside
  the hysteresis band; respect the existing minimum interval before reopening
  below the start threshold.
- Give the Home Assistant bridge its own `dbus-pump-ha` supervisor and log names,
  avoiding the native Venus OS pump service restored at every boot.
- Install one persistent, idempotent boot hook with bounded supervisor retries;
  migrate only a positively owned legacy symlink and preserve device settings.
- Keep firmware service files and native stop markers untouched during install,
  restart, boot recovery and uninstall. Reject ambiguous service layouts.
- Require the firmware Python 3.12 runtime before stopping an existing worker.

### Documentation
- Describe autostart verification, native coexistence, migration and rollback
  limits, including the unchanged shutdown valve-close behavior.

### Maintenance

- Support explicit `DESTDIR` package staging and uninstall without live service actions, preserving operator-owned configuration.
- Treat Python test warnings as failures and apply broad Python lint checks with documented, narrow compatibility exceptions.

- Enable isolated keyless release signing and authenticated verification of the complete artifact inventory and reviewed source archive.

- Use SPDX license metadata and include LICENSE explicitly, removing the
  setuptools deprecation warning without changing the project license.

- Measure application code and release helpers with one
  explicit Python source inventory and an 80% statement-coverage gate.
- Exercise deterministic native packaging, untracked-file exclusion, required
  inputs, version validation and refusal to reuse stale output directories.
- Document governance, conduct, roadmap, security assurance and dated quality
  evidence, including the outstanding continuity requirement.

- Record test and build dependencies in `uv.lock` for reproducible Python checks, preserving the existing locked runtime versions.
- Separate manual callbacks and automatic valve commands from snapshot publication while preserving freshness deadlines and in-flight compensation.
- Publish reviewed release notes from the exact source commit used to build each candidate, preserving build provenance.
- Document contribution checks, confidential security reporting and the project-specific trust boundaries.

### Upgrade

The Home Assistant worker uses dbus-pump-ha rather than the native Venus OS pump supervisor. The installer preserves settings and only migrates a positively identified old service. Review the documented boot recovery and rollback limits before updating; native firmware pump service files remain untouched.

### Security

Private vulnerability reporting and response policy are documented in SECURITY.md. This maintenance update strengthens release evidence and review instructions; it does not replace deployment authentication, network isolation or independent equipment safeguards. No new project CVE is announced by these changes.

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
