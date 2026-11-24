#!/usr/bin/env bash
S="$HOME/.cache/eww-bat-state"
MAX=550
STEP=10
mkdir -p "$HOME/.cache"
read -r pos dir < <(cat "$S" 2>/dev/null || echo "0 1")
pos=$(( pos + dir * STEP ))
if [ "$pos" -ge "$MAX" ]; then pos=$MAX; dir=-1; fi
if [ "$pos" -le 0 ]; then pos=0; dir=1; fi
echo "$pos $dir" > "$S"
echo "$pos"
