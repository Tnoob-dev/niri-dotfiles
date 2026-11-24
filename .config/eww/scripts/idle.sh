#!/usr/bin/env bash
PIDFILE="$HOME/.cache/eww-idle.pid"
mkdir -p "$HOME/.cache"

active() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

case "$1" in
    toggle)
        if active; then
            kill "$(cat "$PIDFILE")"; rm -f "$PIDFILE"
        else
            systemd-inhibit --what=idle --who=eww --why="Pantalla activa" sleep infinity >/dev/null 2>&1 &
            echo $! > "$PIDFILE"
        fi ;;
    icon)
        if active; then printf '%s' $'\uf06e'; else printf '%s' $'\uf070'; fi ;;
esac
