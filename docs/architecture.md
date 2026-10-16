# Architecture and trust boundaries

![Architecture and actual site command ownership](assets/architecture.svg)

`dbus_pump/config.py` loads operator configuration, including the explicit HA
source unit and display language. The level-normalization layer converts one
authoritative sample into percentage and volume; a nonempty HA unit must match
the configured unit. The optional raw-height entity is diagnostic only. `ha_client.py` reads the
configured Home Assistant entities and requests state changes; `worker.py` keeps
network work outside the D-Bus event loop. `main.py` reconciles the latest normalized snapshot
with the requested pump/valve modes. `control.py` implements hysteresis, sample
freshness and the minimum switching interval. `service.py` publishes the tank,
pump and valve paths on separate private system-bus connections.

The administrator controls local configuration, Home Assistant credentials and
entity mappings. At the configured installation, HA automations own water
actuation and bridge AUTO remains disabled. `ENABLE_CONTROL=False` does not
suppress explicit manual commands or shutdown closure. No cross-host lock
arbitrates between switch writers. Display localization changes labels and
`GetText` output only; protocol identities and numeric values stay stable. Network values are external input: missing or non-finite
telemetry must remain unavailable, and a stale-closed valve must not reopen merely
because a fresh value returns inside the hysteresis band. Manual modes and
physical protections are explicit operator responsibilities. The D-Bus service
runs in the trusted Venus OS host; host compromise is outside this service's
protection boundary.

`update.sh`, `boot.sh` and the service scripts maintain persistent installation
and supervised startup. They must preserve the firmware's native pump service,
reject unexpected layouts and wait only a bounded time for shutdown/startup.
The isolated installer harness checks these filesystem/supervisor contracts.

## Delivery boundary

The Python application and native archive use the dependency locks and declared
package inventory. CI combines application, release and workflow tests; the
coverage inventory explicitly includes never-imported helpers. Release checks,
builds, signing and publication have separate responsibilities. Signing occurs
only after successful checks/builds, and publication verifies the source identity
and original artifact inventory. See [signature verification](release-signatures.md)
and [quality evidence](quality-evidence.md).

The [security assurance argument](security-assurance.md) links these boundaries
to implementation and negative tests. Mocks and desktop fixtures do not establish
physical equipment behavior or every deployed Venus OS firmware configuration.

## Operator references

[Configuration](operator/configuration.md) · [Calibration](operator/calibration.md) ·
[Control and failure model](operator/control.md) · [Localization](operator/localization.md) ·
[Wiki source](wiki/Home.md)
