#!/usr/bin/env python3
"""Terramon deploy fingerprint — stable output per deployed build.

Used as a cron monitor_script: the cron scheduler hashes this script's stdout
every tick. UNCHANGED output = no new deploy -> agent run is SUPPRESSED
(silent no_change tick, zero tokens). CHANGED output (new bundle hash, health
change, or recovery from error) = a successful build went live -> the KPI
play-to-win agent runs and reports.

Design rules (monitor-mode):
- Output MUST be stable when nothing changed: no timestamps, fixed order.
- On any network error print exactly "ERROR" (stable) so one outage fires
  the agent once, then stays silent until recovery.
"""

import hashlib
import re
import urllib.request

URL = "https://terramon-tma-production.up.railway.app/"


def _get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "terramon-kpi-monitor/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def main() -> None:
    try:
        html = _get(URL)
        bundles = sorted(set(re.findall(r"assets/[A-Za-z0-9_./-]+\.js", html)))
        try:
            health = _get(URL + "health", timeout=15).strip()
        except Exception:
            health = "health:unreachable"
        fp = "|".join(bundles) + "|" + health
        digest = hashlib.sha256(fp.encode()).hexdigest()[:16]
        print(f"{digest}|{','.join(bundles)}|{health}")
    except Exception:
        # Stable single word: fires the agent once on outage, silent after.
        print("ERROR")


if __name__ == "__main__":
    main()
