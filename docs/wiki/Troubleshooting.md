# Troubleshooting

[Wiki home](Home.md) · [Installation](Installation.md)

Use observations first. A restart may close the valve.

- **Wrong percent:** inspect HA `unit_of_measurement`, set the explicit source
  unit and verify capacity/radius/empty offset. 93 cm is about 77% for the example.
- **Wrong liters:** D-Bus volume is m³. The optional cm entity is diagnostic only;
  both published outputs derive from the primary measurement.
- **Unavailable tank:** check HA reachability, credentials, entity names and
  invalid readings. They do not refresh the monotonic deadline. Unknown is not empty.
- **Service missing:** inspect `/service/dbus-pump-ha` and its logger, not the
  firmware's native `/service/dbus-pump`. Verify the owned symlink and dependencies.
- **Unexpected switching:** inspect `/Mode`, HA automations and other writers.
  `ENABLE_CONTROL=False` suppresses AUTO, not manual/shutdown requests.
- **English labels:** inspect `LANGUAGE`, language fallback and client caching.
  D-Bus IDs never change with language.

Record software/firmware versions, sanitized units/configuration and fresh
HA/D-Bus comparisons. Distinguish local mocked tests from physical device checks.
[Complete diagnosis and acceptance guide](../operator/troubleshooting.md).
