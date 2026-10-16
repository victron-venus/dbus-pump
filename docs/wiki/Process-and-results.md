# Measurement process and recorded result

[Wiki home](Home.md) · [Calibration](Calibration.md) · [Troubleshooting](Troubleshooting.md)

The bridge validates the primary HA reading and its declared unit before using
calibrated vertical-cylinder geometry to compute volume and percentage. Both
D-Bus outputs derive from the same measurement. An invalid sample does not
renew freshness; the last valid measurement becomes unavailable when its
freshness deadline expires. The optional secondary height sensor remains
diagnostic only.

![Measurement process from HA unit validation through cylinder conversion to consistent D-Bus outputs](../assets/measurement-process.svg)

## Recorded Cerbo check

A read-only check at **2026-10-16 03:13:49 UTC** observed:

- Primary input: **49 cm**, with the configured 18 cm empty offset, 35.56 cm radius
  and 387 L capacity.
- Calculated level: **31.8217534%**; published `/Level`: **31.8%**.
- Published `/Remaining`: **0.123 m³**, equivalent to **123 L** after rounding.
- Reported connection `1`, pump state `1`, valve state `0`; heartbeat age `0.98 s`.
- Development build `0.1.7+units.2c5045f`, `ENABLE_CONTROL=False`, `LANGUAGE="en"`.

![Dated Cerbo snapshot showing 49 cm input, 31.8 percent and 123 liters, with reported switch and connection states](../assets/measured-result.svg)

The process chart is explanatory and mathematical. The result panel records one
observation; it is not live telemetry, a physical actuator acceptance test or
proof of uninterrupted service. Logs also contained transient HA connection and
timeout errors. No stable release or CI outcome is inferred from this check.

The earlier 48 cm → 30.8% → 119 L observation is a separate historical snapshot;
it must not be mixed with the 49 cm reading above. HA automations remained the
site's automatic control owner, and this read-only check did not exercise pump
or valve actuation.

[Full process, calculations and verification scope](../operator/process-and-results.md) ·
[Machine-readable check record](../evidence/cerbo-unit-verification-2026-10-16.json) ·
[SVG sources and regeneration](../assets/README.md)
