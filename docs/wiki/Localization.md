# Localization

[Wiki home](Home.md)

[English](../../README.md) · [Русский](../../README.ru.md) ·
[Deutsch](../../README.de.md) · [Nederlands](../../README.nl.md)

Set `LANGUAGE = "en"`, `"ru"`, `"de"` or `"nl"` in `local_config.py`.
Locale variants normalize to their base language; unsupported languages use
English. Reload configuration during an appropriate restart window because
shutdown can attempt valve closure.

Runtime localization covers display names and human-readable `GetText` for
state, mode, status and connection values. Bus names, paths, HA entities,
instances, serials, MQTT topics, raw numbers and English logs stay stable.
Clients may have their own language or cached display labels.

Each root README includes real setup, unit-conversion, control, troubleshooting
and development guidance. Detailed wiki/operator prose and SVG labels are English;
translated READMEs provide localized alternative text for the diagrams. Historical
release evidence is not claimed to be translated.

[Full translation workflow and catalog](../operator/localization.md).
