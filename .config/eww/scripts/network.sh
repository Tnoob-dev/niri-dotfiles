#!/usr/bin/env bash
ssid=$(nmcli -t -f ACTIVE,SSID dev wifi | awk -F: '$1=="yes"{print $2; exit}')
eth=$(nmcli -t -f DEVICE,TYPE,STATE dev | awk -F: '$2=="ethernet" && $3=="connected"{print $1; exit}')

if [ -n "$ssid" ]; then
    icon=$'\uf1eb'; text="$ssid"
elif [ -n "$eth" ]; then
    icon=$'\uf0ac'; text="$eth"
else
    icon=$'\uf05e'; text="Sin red"
fi

if [ "$1" = icon ]; then printf '%s' "$icon"; else printf '%s' "$text"; fi

