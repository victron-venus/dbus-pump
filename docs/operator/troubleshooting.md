# Troubleshooting and acceptance checks

[Operator guide](README.md) · [Installation](installation.md) · [Configuration](configuration.md)

Start with observation. Do not restart the bridge, disable a real sensor or write
`/Mode` merely as a health check: those actions can affect the valve.

## Service appears stopped or missing

```sh
svstat /service/dbus-pump-ha /service/dbus-pump-ha/log
readlink /service/dbus-pump-ha
tail -n 40 /var/log/dbus-pump-ha/current
```

Inspect **`dbus-pump-ha`**, not the firmware's `/service/dbus-pump`.
The correct link target is `/data/dbus-pump/service/dbus-pump`. If an owned link
is missing, follow [boot recovery](installation.md); occupied or unknown paths
require inspection, not deletion. Check Python 3.12 and native dependencies after
firmware updates. A heartbeat under `/run` proves main-loop progress, not HA access.

## Tank percentage equals a centimetre reading

Check the sensor's `unit_of_measurement` in HA. Configure
`HA_WATER_LEVEL_UNIT="cm"`, finite positive capacity/radius and the measured empty
offset. With the documented example, 93 cm should be about 77.0%, not 93%.
Do not fix this by changing valve thresholds. See [calibration](calibration.md).

## Volume looks wrong or stays at zero

`/Capacity` and `/Remaining` are in m³: `0.387` is 387 L. Verify capacity, radius
versus diameter, offset direction and sensor orientation. In `%` mode, volume is capacity times percentage; the optional raw-height
entity is diagnostic only and no longer overrides volume. A fresh invalid/expired primary
level makes volume unavailable rather than a measured empty tank.

## Level unavailable, stale or disconnected

Check the HA endpoint/token locally without sharing the token. Confirm all
entity IDs still exist and inspect `unknown`, `unavailable`, malformed or
non-finite sensor states. Invalid samples do not refresh the original deadline;
expired tank data publishes unavailable `/Level` and `/Remaining` with
`/Status=4`. `/Connected=0` also occurs during startup before valid evidence.

After five consecutive request failures (default), the circuit breaker waits
60 seconds before retrying. Repeated error messages are throttled. D-Bus can
remain responsive while a worker request is slow. An HTTP success is not
independent proof that a physical sensor has recently sampled water height.

## Pump or valve does not obey an expected rule

Determine who currently controls the switch. With `ENABLE_CONTROL=False`, the
bridge does not run valve AUTO. HA automations may still operate normally.
The pump has no automatic level policy in this bridge. Inspect `/Mode`, known
switch state, freshness, minimum transition interval, queue/circuit errors and
HA permissions before issuing another command. Manual ON bypasses stale-level
closure. A queued request or HA service success does not prove valve movement.

## Labels remain in English or clients lose a device

Set `LANGUAGE` in the device's `local_config.py` and load it during an appropriate
restart window. See [localization](localization.md) for supported locales and
fallback behavior. Language selection does not rename services, instances,
entities, MQTT paths or `/Serial`; if a device disappears, inspect those
identities and registration errors rather than translating client match rules.

## Acceptance record

Keep a short private record of version/commit, firmware, source entity units,
calibration inputs, service link, fresh HA/D-Bus/MQTT comparisons and known
control owner. Distinguish offline regression tests, live read-only checks and
operator-approved physical failure drills. Never claim a complete reboot,
physical closure or outage recovery from a mocked test or status command alone.
