#!/usr/bin/env bash
BAT=/sys/class/power_supply/BAT0
cap=$(cat "$BAT/capacity" 2>/dev/null || echo 0)
status=$(cat "$BAT/status" 2>/dev/null)

case "$1" in
    pct)
        printf '%s%%' "$cap" ;;
    state)
        if [ "$status" = Charging ] || [ "$status" = Full ] || [ "$status" = "Not charging" ]; then
            printf 'charging'
        elif [ "$cap" -le 15 ]; then printf 'critical'
        elif [ "$cap" -le 30 ]; then printf 'warning'
        else printf 'normal'
        fi ;;
    icon)
        if [ "$status" = Charging ]; then printf '%s' $'\uf0e7'
        elif [ "$status" = Full ]; then printf '%s' $'\uf240'
        elif [ "$status" = "Not charging" ]; then printf '%s' $'\uf1e6'
        elif [ "$cap" -le 15 ]; then printf '%s' $'\uf071'
        else
            icons=($'\uf244' $'\uf243' $'\uf242' $'\uf241' $'\uf240')
            idx=$(( cap * 5 / 101 ))
            printf '%s' "${icons[$idx]}"
        fi ;;
esac
