#!/usr/bin/env bash
ssid=$(nmcli -t -f ACTIVE,SSID dev wifi | awk -F: '$1=="yes"{print $2; exit}')
if [ -n "$ssid" ]; then echo "$ssid"; else echo "Sin red"; fi
