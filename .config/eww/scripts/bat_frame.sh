#!/usr/bin/env bash
D="$HOME/.config/eww/assets/bat"
C="$HOME/.cache/eww-bat-frame"
mkdir -p "$HOME/.cache"
i=$(cat "$C" 2>/dev/null || echo 0)
echo $(( (i + 1) % 4 )) > "$C"
echo "$D/frame_$i.png"
