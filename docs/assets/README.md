# Documentation diagrams

[Project](../../README.md) · [Operator guide](../operator/README.md)

These native SVG files contain editable vector shapes/text, a `viewBox`, an
accessible `<title>` and `<desc>`, and no remote resources or executable content.
The root READMEs provide translated alternative text. Visible SVG labels are English.

- [Architecture](architecture.svg): HA → worker/normalization → D-Bus → displays/MQTT;
  command path and actual site ownership shown separately.
- [Calibration](calibration.svg): calculated vertical-cylinder curve, percent and
  liter axes, empty/full bounds and the 93 cm example.
- [Hysteresis](hysteresis.svg): default thresholds, hold band, stale closure and
  manual priority, with explicit percent and second units.
- [Measurement process](measurement-process.svg): five colored stages from the
  authoritative HA source through validation, normalization and D-Bus publication
  to the display. Separate panels explain rejected samples, freshness, control
  ownership and the read-only dry-run. The diagram describes the configured
  design; it is not live telemetry.
- [Measured result](measured-result.svg): the mathematical raw-cm-as-percent
  mistake and calibrated model appear as distinct dashed/solid curves. A separate
  panel records the read-only observation at **2026-10-16T03:13:49Z**:
  **49 cm → 31.8% → 123 L**, observed version `0.1.7+units.2c5045f`, connected `1`,
  pump `1`, valve `0`, automatic control `false`, heartbeat age `0.98 s`.
  The old mapping is a counterfactual comparison, not an earlier measurement.
  The saved observation is not live and does not verify physical valve position
  or water level. The reported `0.123 m³` is 123 L; the model before publication
  rounding gives 123.15 L.

Regenerate with Python's standard library only:

```sh
python3 docs/assets/generate.py
python3 docs/assets/generate.py --check
```

The generator is deterministic and performs no device or network access. The
calibration chart uses 387 L capacity, an 18 cm empty offset and a 35.56 cm
radius. It illustrates the configured model, not a measured sensor history or
physical acceptance test. Keep numeric inputs, output SVGs, alt text and
[calibration documentation](../operator/calibration.md) consistent when editing.
The result diagram embeds the fixed, timestamped observation above; regeneration
does not refresh that observation. It must only change with new recorded evidence.

All five images use high-contrast text, explicit labels, and accessible title and
description elements. Color reinforces the labels; the model comparison also
uses line patterns so its series remain distinguishable without color. SVGs
contain no JavaScript, embedded raster images, remote fonts or external resources.
