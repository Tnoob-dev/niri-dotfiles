#!/usr/bin/env bash
SINK=@DEFAULT_SINK@

case "$1" in
    toggle) pactl set-sink-mute "$SINK" toggle; exit 0 ;;
    up|down)
        cur=$(pactl get-sink-volume "$SINK" | grep -oE '[0-9]+%' | head -n1 | tr -d '%')
        if [ "$1" = up ]; then new=$(( cur + 5 )); else new=$(( cur - 5 )); fi
        [ "$new" -gt 150 ] && new=150
        [ "$new" -lt 0 ] && new=0
        pactl set-sink-volume "$SINK" "${new}%"
        exit 0 ;;
    icon|text) ;;
    *) exit 0 ;;
esac

muted=$(pactl get-sink-mute "$SINK" | grep -c yes)
vol=$(pactl get-sink-volume "$SINK" | grep -oE '[0-9]+%' | head -n1 | tr -d '%')

if [ "$1" = icon ]; then
    if [ "$muted" -eq 1 ]; then
        printf '%s' $'\uf2e2'
    elif [ "$vol" -lt 34 ]; then
        printf '%s' $'\uf026'
    elif [ "$vol" -lt 67 ]; then
        printf '%s' $'\uf027'
    else
        printf '%s' $'\uf028'
    fi
else
    if [ "$muted" -eq 1 ]; then
        printf '%s' 'Mudo'
    else
        printf '%s%%' "$vol"
    fi
fi
