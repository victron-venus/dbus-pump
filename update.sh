#!/bin/sh
#
# dbus-pump self-update script.
#
# Ships inside the release tarball and runs ON the Venus OS device to install
# the release into INSTALL_DIR (default /data/dbus-pump). It is invoked
# by SetupHelper or manually:
#
#     sh update.sh [INSTALL_DIR]
#
# This script owns all layout knowledge (runtime files, daemontools services,
# /service symlinks, device-local file preservation, restart order) so that
# callers never need to hardcode where files go. Adding a new
# module or a new daemontools service requires a change here only.

set -eu

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${1:-/data/dbus-pump}"

# Unit commands and boot hooks use this canonical persistent location.
if [ "$INSTALL_DIR" != "/data/dbus-pump" ]; then
    echo "Unsupported install directory: use /data/dbus-pump" >&2
    exit 2
fi

# Device-local files that must never be overwritten by an update.
LOCAL_ONLY="local_config.py"

# Runtime items shipped at the repo root and installed at INSTALL_DIR root.
RUNTIME_ITEMS="update.sh boot.sh restart.sh dbus_pump version setup gitHubInfo local_config.example.py"

# Flat-file leftovers that must never survive an update (we run `python3 -m
# dbus_pump`; a stale root main.py would shadow the package).
STALE_TOP_LEVEL="main.py inverter_control"

sep() { echo "=== dbus-pump update: $*"; }

# Fail before stopping the existing service if the firmware lacks dependencies.
# Provision packages separately; never modify the system Python during an update.
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PYTHON'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit("The firmware Python 3.12 runtime is required")
import requests, dbus
sys.path.insert(0, "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python")
from gi.repository import GLib
from vedbus import VeDbusService
PYTHON

command -v svc >/dev/null
command -v svstat >/dev/null

# Stage the release before stopping anything. SetupHelper runs this script from
# the installed package tree, which must not be deleted while it is our source.
# /tmp is volatile on Venus OS and avoids writing an extra release to flash.
STAGING_DIR=$(mktemp -d /tmp/dbus-pump-update.XXXXXX)
trap 'rm -rf "$STAGING_DIR"' EXIT
trap 'exit 1' HUP INT TERM
mkdir -p "$STAGING_DIR/source" "$STAGING_DIR/backup"
for item in $RUNTIME_ITEMS $LOCAL_ONLY service services; do
    [ ! -e "$SRC_DIR/$item" ] || cp -a "$SRC_DIR/$item" "$STAGING_DIR/source/$item"
done
# Supervise state belongs to the old process, not the release payload.
find "$STAGING_DIR/source" -type d -name supervise -prune -exec rm -rf {} \;
SRC_DIR="$STAGING_DIR/source"
cd "$STAGING_DIR"

# Validate the owned service layout before stopping a healthy worker. Ordinary
# updates preserve the service/log directories and their live supervisors.
SERVICE_TARGET="$INSTALL_DIR/service/dbus-pump"
SERVICE_LINK="/service/dbus-pump-ha"
LEGACY_LINK="/service/dbus-pump"
UNIT_SOURCE="$SRC_DIR/service/dbus-pump"
[ -d "$UNIT_SOURCE" ] || UNIT_SOURCE="$SRC_DIR/services/dbus-pump"
for run_file in run log/run; do
    if [ ! -f "$UNIT_SOURCE/$run_file" ]; then
        echo "Missing service definition: $UNIT_SOURCE/$run_file" >&2
        exit 1
    fi
done
# Preflight the release helper before any service or runtime mutation.
sh "$SRC_DIR/boot.sh" check
ACTIVE_LINK="$SERVICE_LINK"
if [ ! -L "$SERVICE_LINK" ] && [ -L "$LEGACY_LINK" ] && \
        [ "$(readlink "$LEGACY_LINK")" = "$SERVICE_TARGET" ]; then
    ACTIVE_LINK="$LEGACY_LINK"
fi

# Stop only the application; its existing logger and supervisors stay alive.
# Verify termination before replacing Python files. A stuck worker gets one
# supervisor-scoped kill after twenty seconds; unrelated processes are untouched.
stop_worker() {
    service_path="$1"
    [ -e "$service_path" ] || return 0
    svc -d "$service_path" || return 1
    waited=0
    while [ "$waited" -lt 25 ]; do
        status=$(svstat "$service_path" 2>/dev/null || true)
        case "$status" in *": down "*) return 0 ;; esac
        if [ "$waited" -eq 20 ]; then
            svc -k "$service_path" || return 1
        fi
        sleep 1
        waited=$((waited + 1))
    done
    echo "Service did not stop; runtime files were not changed: $service_path" >&2
    return 1
}
# A real /service/dbus-pump belongs to firmware and is never stopped here.
if [ -L "$ACTIVE_LINK" ]; then
    stop_worker "$ACTIVE_LINK"
    # Only a changed logger definition needs a restart (e.g. the migration to
    # a private log directory). Ordinary updates keep the logger running.
    if ! cmp -s "$SERVICE_TARGET/log/run" "$UNIT_SOURCE/log/run"; then
        stop_worker "$ACTIVE_LINK/log"
    fi
fi

mkdir -p "$INSTALL_DIR"
sep "installing from $SRC_DIR into $INSTALL_DIR"

# 2. Back up device-local files so the wholesale copy below can restore them.
TMP_BACKUP="$STAGING_DIR/backup"
mkdir -p "$TMP_BACKUP"
for f in $LOCAL_ONLY; do
    [ -f "$INSTALL_DIR/$f" ] && cp -p "$INSTALL_DIR/$f" "$TMP_BACKUP/"
done

# 3. Install runtime items (replace wholesale to also drop stale files).
for item in $RUNTIME_ITEMS; do
    [ -n "$item" ] || continue
    if [ -e "$SRC_DIR/$item" ]; then
        rm -rf "${INSTALL_DIR:?}/$item"
        cp -a "$SRC_DIR/$item" "$INSTALL_DIR/$item"
    fi
done

# Replace only the two owned run scripts, using rename in each destination
# directory. Open files, log pipes, directory ownership and supervise state
# survive the update. A running multilog uses the new script on its next start.
mkdir -p "$SERVICE_TARGET/log"
for run_file in run log/run; do
    destination="$SERVICE_TARGET/$run_file"
    temporary=$(mktemp "$(dirname "$destination")/.run.XXXXXX")
    if [ -f "$destination" ]; then
        cp -p "$destination" "$temporary"
    fi
    cat "$UNIT_SOURCE/$run_file" > "$temporary"
    chmod 755 "$temporary"
    mv -f "$temporary" "$destination"
done
rm -f "$SERVICE_TARGET/down" "$SERVICE_TARGET/log/down"

# 5. Restore device-local files and drop stale flat-file leftovers.
for f in $LOCAL_ONLY; do
    [ -f "$TMP_BACKUP/$f" ] && cp -p "$TMP_BACKUP/$f" "$INSTALL_DIR/$f"
done
rm -rf "$TMP_BACKUP"
for f in $STALE_TOP_LEVEL; do
    rm -rf "${INSTALL_DIR:?}/$f"
done

# 5b. Optional: push the developer's local_config.py instead of keeping the
#     device copy (used by deploy.sh, where the dev machine is authoritative).
if [ "${PUSH_LOCAL_CONFIG:-0}" = "1" ] && [ -f "$SRC_DIR/local_config.py" ]; then
    SETUP_OPTIONS_DIR="/data/setupOptions/dbus-pump"
    mkdir -p "$SETUP_OPTIONS_DIR"
    cp -p "$SRC_DIR/local_config.py" "$INSTALL_DIR/local_config.py"
    cp -p "$SRC_DIR/local_config.py" "$SETUP_OPTIONS_DIR/local_config.py"
    sep "pushed local_config.py (PUSH_LOCAL_CONFIG=1)"
fi

# Refresh the boot hook before an existing exit statement. On boot it creates
# a missing canonical link, without deleting a directory or unexpected link.
RC_LOCAL="/data/rc.local"
if [ ! -f "$RC_LOCAL" ]; then
    printf '#!/bin/sh\n' > "$RC_LOCAL"
    chmod +x "$RC_LOCAL"
fi
sed -i '/# === dbus-pump service persistence ===/,/# === end dbus-pump ===/d' "$RC_LOCAL" 2>/dev/null || true
RC_BLOCK="$STAGING_DIR/rc.block"
cat > "$RC_BLOCK" << 'RCEOF'

# === dbus-pump service persistence ===
sh /data/dbus-pump/boot.sh
# === end dbus-pump ===
RCEOF
# An existing rc.local may end in "exit 0"; boot hooks appended after it never run.
awk -v block="$RC_BLOCK" '
    !inserted && /^exit[ \t]+0[ \t]*$/ {
        while ((getline line < block) > 0) print line
        close(block)
        inserted = 1
    }
    { print }
    END { if (!inserted) while ((getline line < block) > 0) print line }
' "$RC_LOCAL" > "$STAGING_DIR/rc.local"
cat "$STAGING_DIR/rc.local" > "$RC_LOCAL"
chmod +x "$RC_LOCAL"
sep "refreshed rc.local boot persistence block"

# The same bounded boot path handles first install, an owned old alias, and
# a firmware-created legacy service directory without replacing that directory.
sh "$INSTALL_DIR/boot.sh"

sep "installed version $(cat "$INSTALL_DIR/version" 2>/dev/null || echo unknown)"
