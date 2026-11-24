#!/usr/bin/env python3
import json
import subprocess


def title():
    try:
        out = subprocess.run(["niri", "msg", "-j", "focused-window"],
                             capture_output=True, text=True, timeout=2).stdout
        data = json.loads(out)
        t = (data or {}).get("title") or ""
    except Exception:
        t = ""
    return t[:48]


print(title(), flush=True)
p = subprocess.Popen(["niri", "msg", "event-stream"],
                     stdout=subprocess.PIPE, text=True)
for line in p.stdout:
    if "Window" in line or "Workspace" in line:
        print(title(), flush=True)
