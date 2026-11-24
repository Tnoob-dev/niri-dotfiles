#!/usr/bin/env python3
import os
import subprocess
import sys
import time

UNITS = ["B/s", "KB/s", "MB/s", "GB/s"]


def iface():
    try:
        words = subprocess.run(["ip", "route", "show", "default"],
                               capture_output=True, text=True).stdout.split()
        return words[words.index("dev") + 1]
    except (ValueError, IndexError):
        return None


def counters(dev):
    with open("/proc/net/dev") as f:
        for line in f:
            if line.strip().startswith(dev + ":"):
                p = line.split(":", 1)[1].split()
                return int(p[0]), int(p[8])
    return 0, 0


def human(bps):
    i = 0
    while bps >= 1024 and i < len(UNITS) - 1:
        bps /= 1024
        i += 1
    return f"{bps:.0f} {UNITS[i]}" if i == 0 else f"{bps:.1f} {UNITS[i]}"


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "down"
    cache = os.path.expanduser(f"~/.cache/eww-netrate-{which}")
    os.makedirs(os.path.dirname(cache), exist_ok=True)

    dev = iface()
    if not dev:
        print("-", flush=True)
        return

    rx, tx = counters(dev)
    now = time.time()
    try:
        t0, rx0, tx0 = open(cache).read().split()
        dt = max(now - float(t0), 0.001)
        rate_rx = max((rx - int(rx0)) / dt, 0)
        rate_tx = max((tx - int(tx0)) / dt, 0)
    except (OSError, ValueError):
        rate_rx = rate_tx = 0

    with open(cache, "w") as f:
        f.write(f"{now} {rx} {tx}")

    if which == "down":
        print(f"\uf063 {human(rate_rx)}", flush=True)
    else:
        print(f"\uf062 {human(rate_tx)}", flush=True)


if __name__ == "__main__":
    main()
