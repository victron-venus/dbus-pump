# Installation, updates and recovery

[Operator guide](README.md) · [Configuration](configuration.md) · [Troubleshooting](troubleshooting.md)

## Requirements

Use Venus OS with system Python **3.12.x**, `requests`, `dbus` and GI/GLib. The
project pins local development to 3.12.13. Keep the interpreter paired with the
firmware's native libraries. The installer does not run `pip` or upgrade the OS.
Check again after firmware updates:

```sh
python3 --version
python3 -c "import requests, dbus; from gi.repository import GLib"
```

The GX must reach Home Assistant's REST API. Use a private long-lived HA token,
correct switch entities and explicit sensor units. Confirm actual actuator
ownership before starting: manual D-Bus requests and graceful shutdown can send
commands even with `ENABLE_CONTROL=False`.

## First installation

Place the package in `/data/dbus-pump`, including `setup` and `version`. Copy
`local_config.example.py` to `local_config.py`, fill in site-specific values and
leave automatic control disabled. Install through SetupHelper PackageManager or:

```sh
/data/dbus-pump/setup install
```

The persistent service directory is `/data/dbus-pump/service/dbus-pump`.
Its supervisor link is **`/service/dbus-pump-ha`**; logs live at
`/var/log/dbus-pump-ha/current`. The native firmware service
`/service/dbus-pump` is separate and may be inactive with a `down` marker. Do not
delete it, change its marker or replace its directory to repair this bridge.

## Verify the result

```sh
svstat /service/dbus-pump-ha /service/dbus-pump-ha/log
readlink /service/dbus-pump-ha
tail -n 40 /var/log/dbus-pump-ha/current
```

The link target must be `/data/dbus-pump/service/dbus-pump`. Check fresh D-Bus
telemetry against HA: `/Connected`, `/Level`, `/Remaining`, pump `/State` and
valve `/State`. Native service registration creates all paths before publishing
names; startup remains disconnected until a valid snapshot arrives. Process
uptime and a heartbeat alone do not prove HA connectivity or correct units.

## Deploying from a workstation

With the repository available locally and an SSH host alias `Cerbo`:

```sh
./deploy.sh Cerbo
```

This script streams the repository, invokes `update.sh`, and waits for a fresh
heartbeat and supervisor `up` state. **A workstation `local_config.py` is sent
and replaces device configuration** because deployment sets `PUSH_LOCAL_CONFIG=1`.
Review that private file first; a clean checkout without it preserves the device
configuration. Ordinary package installation/update preserves `local_config.py`.
A deployment changes the running service and can close the valve during shutdown.

## Autostart and supervision

`update.sh` installs `boot.sh` and a managed call in `/data/rc.local`, before an
existing `exit 0`. The helper runs after the Venus service overlay is mounted;
it waits up to 20 seconds for `/service` and retries startup requests for up to
20 seconds. A directory check alone is not proof that an early boot overlay is
ready. It preserves owned service directories and supervisor handles.

For a missing owned link or stopped service, after inspecting logs and ownership:

```sh
sh /data/dbus-pump/boot.sh
```

This is idempotent recovery, not a restart or a non-actuating health probe. It
may start the bridge. Unknown links and occupied paths fail closed. Migration
from the legacy name occurs only for an exact symlink to this project's service.
Reconstructing a removed link does not establish successful recovery after a
complete hardware reboot.

## Update, rollback and uninstall

Updates stage under volatile `/tmp` before stopping the application, so updating
from the installed directory is supported. Existing service/log directory
inodes, supervisor state and ownership are preserved; run scripts are replaced
atomically. The updater waits for termination, applies one supervisor-scoped
kill after 20 seconds, and aborts after 25 seconds if termination is unconfirmed.
It does not restart PackageManager. A healthy logger is retained unless its run
script changes. `update.sh` requests startup; callers still need the checks above.

Keep a private backup of the accepted package and configuration, plus its exact
version/checksum. Restore an accepted package with a compatible autostart layout
and recheck telemetry. Releases before 0.1.6 use the conflicting native service
name; copying back old scripts alone is not a reliable rollback.

```sh
/data/dbus-pump/setup uninstall
```

Uninstall stops/detaches positively identified project links and removes the
managed boot call. It preserves device configuration and native firmware files.
Stopping or restarting retains the graceful-shutdown valve-close attempt; plan
it with the operator responsible for HA automation.

The heartbeat is volatile under `/run/dbus-pump/heartbeat`. Logs use bounded
`multilog` rotation (`s25000 n4`). On the previously audited image, `/var/log`
resolves to persistent `/data/log`, so logging writes flash. Consult
[historical deployment evidence](../DEPLOYMENT-NOTES.md) for the tested image.
