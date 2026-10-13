# Architecture and trust boundaries

`dbus_pump/config.py` loads operator configuration. `ha_client.py` reads the
configured Home Assistant entities and requests state changes; `worker.py` keeps
network work outside the D-Bus event loop. `main.py` reconciles the latest snapshot
with the requested pump/valve modes. `control.py` implements hysteresis, sample
freshness and the minimum switching interval. `service.py` publishes the tank,
pump and valve paths on separate private system-bus connections.

The administrator controls local configuration, Home Assistant credentials and
entity mappings. Network values are external input: missing or non-finite
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
