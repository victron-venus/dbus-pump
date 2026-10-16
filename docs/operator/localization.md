# Localization and translation guide

[Operator guide](README.md) · [English](../../README.md) · [Русский](../../README.ru.md) · [Deutsch](../../README.de.md) · [Nederlands](../../README.nl.md)

## Select a language

Set `LANGUAGE` in private `local_config.py`:

```python
LANGUAGE = "ru"  # en, ru, de, nl
```

The default is English. Locale variants are normalized to the supported base
language (for example `de-DE` and `nl_NL`); unknown languages fall back to
English. Configuration is loaded at startup, so apply a language change during
a suitable restart window. Shutdown may close the valve even when AUTO is disabled.

## What is translated

The runtime catalog translates tank/pump/valve display names (`/ProductName`,
`/CustomName`) and human-readable D-Bus `GetText` labels for numeric `/State`,
`/Mode`, `/Status` and `/Connected` values. Consumers that display these texts
can show the selected language. A GX/VRM/client may also use its own vocabulary
or cache a display name; the bridge does not configure that application's locale.

English operational logs, configuration keys, HA entity IDs, bus names, D-Bus
paths, numeric state/mode values, `/Serial`, device instances and MQTT topics
remain stable. Do not match a device by translated display name. For example,
`com.victronenergy.pump.startstop1` stays the pump service in all languages.

## Documentation coverage

The root README has substantive English, Russian, German and Dutch versions,
each with installation, configuration, units, safety, troubleshooting and links.
The detailed operator guide and maintained wiki source are currently English;
links from translated READMEs identify that scope. SVG text is English, with
translated Markdown alternative text in each README and embedded SVG title/description.
This is explicit partial documentation localization, not a claim that every
historical release/evidence document has been translated.

## Contribute a language or improve a translation

1. Edit the runtime catalog in [`dbus_pump/i18n.py`](../../dbus_pump/i18n.py).
   Translate every catalog key; preserve placeholders and control meaning.
2. Keep protocol identity and numeric values unchanged. ON/OFF/AUTO wording
   must distinguish a requested mode from observed physical state.
3. Add or update a substantive root `README.<language>.md` with the same
   installation, unit-conversion and safety facts as the English README.
4. Update language navigation in every README, this guide and wiki pages.
5. Run localization regression tests and the normal project checks in
   [CONTRIBUTING.md](../../CONTRIBUTING.md). Verify English fallback, normalized
   locale variants, complete keys, translated `GetText`, and stable identities.
6. Ask a native-language reviewer to check terminology, especially stale data,
   valve closure, manual override and the distinction between cm, %, L and m³.

Changing a diagram's numbers requires regenerating SVG from
[`docs/assets/generate.py`](../assets/generate.py). Keep visible labels,
alternative text and adjacent explanations consistent. Do not convert numeric
D-Bus values into locale-dependent strings or alter the decimal format expected
by machine consumers.
