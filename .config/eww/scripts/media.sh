#!/usr/bin/env bash
out=$(playerctl metadata --format '{{ artist }} - {{ title }}' 2>/dev/null)
if [ -n "$out" ] && [ "$out" != " - " ]; then echo "$out"; else echo "Nothing playing"; fi
