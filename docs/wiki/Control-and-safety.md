# Control and safety

[Wiki home](Home.md) · [Troubleshooting](Troubleshooting.md)

HA automations own pump/valve control at the configured installation. Leave
`ENABLE_CONTROL=False` unless that responsibility is intentionally transferred.
There is no arbitration across HA, this bridge and other switch writers.

The flag suppresses AUTO only. Manual `/Mode` commands and the shutdown
valve-close attempt remain active. A health check should read state, not restart
the service or toggle modes.

![Valve hysteresis and freshness defaults](../assets/hysteresis.svg)

When AUTO is enabled, default valve thresholds are open at ≤30%, close at ≥85%,
and hold between them. Normal transitions wait at least 60 seconds. At 120
seconds without fresh data, AUTO requests closure. Recovery in the middle band
retains the closed decision. Manual ON takes priority over the stale-level rule.
The pump has no automatic level policy.

A queued command or HA acknowledgement does not prove physical closure.
Power loss, unreachable HA and physical failure require suitable hardware
safeguards. [Full command, queue and failure model](../operator/control.md).
