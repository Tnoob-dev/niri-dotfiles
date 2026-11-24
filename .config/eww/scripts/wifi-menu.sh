#!/bin/bash

MENU="wofi --dmenu -i -p"

ACTION=$(printf "Cambiar de red\nOlvidar red\nDesconectar\nEditor de conexiones" | $MENU "Wi-Fi")

case "$ACTION" in
    "Cambiar de red")
        SSID=$(nmcli -t -f SSID device wifi list --rescan auto | awk 'NF && !seen[$0]++' | $MENU "Redes")
        [ -n "$SSID" ] && nmcli device wifi connect "$SSID"
        ;;
    "Olvidar red")
        SSID=$(nmcli -t -f NAME,TYPE connection show | awk -F: '$2=="802-11-wireless"{print $1}' | $MENU "Olvidar")
        [ -n "$SSID" ] && nmcli connection delete id "$SSID"
        ;;
    "Desconectar")
        DEV=$(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="wifi"{print $1}')
        [ -n "$DEV" ] && nmcli device disconnect "$DEV"
        ;;
    "Editor de conexiones")
        nm-connection-editor &
        ;;
esac
