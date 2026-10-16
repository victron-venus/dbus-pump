# Installation

[Wiki home](Home.md) · [Configuration](Configuration.md)

Use system Python 3.12.x and the matching Venus D-Bus/GI libraries. Put the package
under `/data/dbus-pump`, copy `local_config.example.py` to private `local_config.py`
and configure HA entities, units and tank dimensions. Keep AUTO disabled until
ownership and measurements have been checked.

```sh
python3 --version
python3 -c "import requests, dbus; from gi.repository import GLib"
/data/dbus-pump/setup install
svstat /service/dbus-pump-ha /service/dbus-pump-ha/log
readlink /service/dbus-pump-ha
tail -n 40 /var/log/dbus-pump-ha/current
```

`/service/dbus-pump-ha` must point at `/data/dbus-pump/service/dbus-pump`.
The firmware's `/service/dbus-pump` is separate; do not delete it or its `down`
marker. Check actual HA/D-Bus values after startup, not only process status.

`deploy.sh` sends a workstation `local_config.py` when present and replaces the
device copy. Package updates normally preserve device configuration. A restart
can send a valve-close request even with AUTO disabled.

[Full installation, firmware coexistence, rollback and uninstall guide](../operator/installation.md).
