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

Regenerate with Python's standard library only:

```sh
python3 docs/assets/generate.py
python3 docs/assets/generate.py --check
```

The generator is deterministic and uses no live device or network data. The
calibration chart uses 387 L capacity, an 18 cm empty offset and a 35.56 cm
radius. It illustrates the configured model, not a measured sensor history or
physical acceptance test. Keep numeric inputs, output SVGs, alt text and
[calibration documentation](../operator/calibration.md) consistent when editing.
