#!/usr/bin/env python3
import json
import subprocess


def state():
    try:
        out = subprocess.run(["niri", "msg", "-j", "workspaces"],
                             capture_output=True, text=True, timeout=2).stdout
        data = json.loads(out)
    except Exception:
        data = []

    used = [0] * 6  # 0 vacío, 1 ocupado, 2 activo
    last = 0
    for w in data:
        i = w.get("idx", 0)
        if 1 <= i <= 6:
            if w.get("is_focused") or w.get("is_active"):
                used[i - 1] = 2
            elif w.get("active_window_id") is not None and used[i - 1] != 2:
                used[i - 1] = 1
            if used[i - 1]:
                last = max(last, i)

    for k, v in enumerate(used):
        if v == 2:
            last = max(last, k + 1)

    count = min(6, last + 1)  # workspaces usados + uno vacío
    s = []
    for k in range(6):
        if k >= count:
            s.append("hidden")
        elif used[k] == 2:
            s.append("active")
        elif used[k] == 1:
            s.append("occupied")
        else:
            s.append("empty")
    return json.dumps(s)


def main():
    last = state()
    print(last, flush=True)
    p = subprocess.Popen(["niri", "msg", "event-stream"],
                         stdout=subprocess.PIPE, text=True)
    for _ in p.stdout:
        cur = state()
        if cur != last:
            print(cur, flush=True)
            last = cur


if __name__ == "__main__":
    main()
