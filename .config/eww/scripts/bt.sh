#!/usr/bin/env bash
powered() { bluetoothctl show 2>/dev/null | grep -q "Powered: yes"; }

case "$1" in
    icon)
        if powered; then printf '%s' $'\uf293'; else printf '%s' $'\uf294'; fi ;;
    state)
        if powered; then printf 'on'; else printf 'off'; fi ;;
    toggle)
        if powered; then bluetoothctl power off; else bluetoothctl power on; fi ;;
esac
