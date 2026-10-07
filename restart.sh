#!/bin/sh
# Restarting preserves the configured shutdown valve-close behavior.
ssh "${1:-Cerbo}" 'sh /data/dbus-pump/boot.sh restart'
