#!/usr/bin/env python3
import json
import subprocess

out = subprocess.run(["niri", "msg", "-j", "workspaces"],
                     capture_output=True, text=True).stdout
try:
    data = json.loads(out)
except json.JSONDecodeError:
    data = []

states = ["empty"] * 6
for w in data:
    i = w.get("idx", 0)
    if 1 <= i <= 6:
        if w.get("is_focused") or w.get("is_active"):
            states[i - 1] = "active"
        elif w.get("active_window_id") is not None and states[i - 1] != "active":
            states[i - 1] = "occupied"

print(json.dumps(states))
