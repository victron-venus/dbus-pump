#!/bin/sh
# Own only the HA bridge's service link; Venus OS owns /service/dbus-pump.
set -eu

TARGET=/data/dbus-pump/service/dbus-pump
LINK=/service/dbus-pump-ha
LEGACY=/service/dbus-pump

owned_link() {
    owned_link_path="$1"
    [ -L "$owned_link_path" ] && [ "$(readlink "$owned_link_path")" = "$TARGET" ]
}

check_layout() {
    if [ -L /data/rc.local ]; then
        echo "Refusing an indirect boot configuration: /data/rc.local" >&2
        return 1
    fi
    for directory in /data/dbus-pump/service "$TARGET" "$TARGET/log"; do
        if [ -L "$directory" ] || { [ -e "$directory" ] && [ ! -d "$directory" ]; }; then
            echo "Unexpected service directory: $directory" >&2
            return 1
        fi
    done
    if { [ -e "$LINK" ] || [ -L "$LINK" ]; } && ! owned_link "$LINK"; then
        echo "Refusing to replace an unowned service: $LINK" >&2
        return 1
    fi
    # A real legacy directory is the firmware service, not this package's link.
    if [ -L "$LEGACY" ] && ! owned_link "$LEGACY"; then
        echo "Refusing an ambiguous legacy service symlink: $LEGACY" >&2
        return 1
    fi
}

start_service() {
    start_service_path="$1"
    waited=0
    while [ "$waited" -lt 20 ]; do
        if svc -u "$start_service_path" 2>/dev/null; then
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done
    echo "Supervisor did not accept startup within 20 seconds: $start_service_path" >&2
    return 1
}

stop_service() {
    stop_service_path="$1"
    svc -d "$stop_service_path"
    waited=0
    while [ "$waited" -lt 25 ]; do
        status=$(svstat "$stop_service_path" 2>/dev/null || true)
        case "$status" in *": down "*) return 0 ;; esac
        sleep 1
        waited=$((waited + 1))
    done
    echo "Service did not stop; its link was preserved: $stop_service_path" >&2
    return 1
}

check_layout
case "${1:-boot}" in
    check) exit 0 ;;
    restart)
        owned_link "$LINK" || { echo "Owned service link is missing: $LINK" >&2; exit 1; }
        exec svc -t "$LINK"
        ;;
    uninstall)
        # A stopped marker prevents svscan from bringing an exiting supervisor
        # back up while its owned link is being detached. Never touch firmware.
        active=""
        if owned_link "$LINK"; then
            active="$LINK"
        elif owned_link "$LEGACY"; then
            active="$LEGACY"
        fi
        if [ -n "$active" ]; then
            # Duplicate owned aliases share one supervisor: stop it only once.
            if [ -d "$TARGET" ]; then
                touch "$TARGET/down" "$TARGET/log/down"
                stop_service "$active"
                stop_service "$active/log"
                svc -x "$active/log" "$active"
            fi
            for candidate in "$LINK" "$LEGACY"; do
                if owned_link "$candidate"; then
                    rm "$candidate"
                fi
            done
        fi
        exit 0
        ;;
    boot) ;;
    *) echo "Usage: $0 [check|boot|restart|uninstall]" >&2; exit 2 ;;
esac

for run_file in "$TARGET/run" "$TARGET/log/run"; do
    if [ ! -x "$run_file" ]; then
        echo "Missing executable service definition: $run_file" >&2
        exit 1
    fi
done

# The rc.local entry runs after Venus has mounted its service overlay. Wait for
# directory availability, without creating it; this is not a mount readiness
# probe and is not an entry point for an earlier pre-overlay boot stage.
waited=0
while [ ! -d /service ] && [ "$waited" -lt 20 ]; do
    sleep 1
    waited=$((waited + 1))
done
[ -d /service ] || { echo "/service is not available" >&2; exit 1; }

# Recheck after waiting. Moving an owned symlink keeps the persistent service
# directory and its running supervisors intact; it never moves a firmware dir.
check_layout
if ! owned_link "$LINK"; then
    if owned_link "$LEGACY"; then
        mv "$LEGACY" "$LINK"
    else
        ln -s "$TARGET" "$LINK"
    fi
elif owned_link "$LEGACY"; then
    rm "$LEGACY"
fi
rm -f "$TARGET/down" "$TARGET/log/down"
start_service "$LINK/log"
start_service "$LINK"
