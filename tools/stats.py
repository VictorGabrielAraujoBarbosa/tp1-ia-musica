#!/usr/bin/env python3
"""Summarise generated trace logs (`gm-sync/1`) as a markdown table.

    python3 tools/stats.py output/*/*.sync.json

Columns include meter share, layer on-time, tension and gap ranges, and the
odd-meter share while behind (a simple reactivity check) — handy for the
Results section of the report.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

METER_STEPS = {(4, 4): 16, (7, 8): 14}
BEHIND = -0.03


def summarise(path: Path) -> dict:
    d = json.loads(path.read_text())
    bars = d["bars"]
    bpm = d["bpm"]
    quarter = 60.0 / bpm
    music_s = sum(METER_STEPS[tuple(b["meter"])] / 4.0 * quarter for b in bars)
    behind = [b for b in bars if b["state"]["gap"] < BEHIND]
    gaps = [b["state"]["gap"] for b in bars]
    phases = [b["state"]["phase"] for b in bars]
    odd = [b for b in bars if tuple(b["meter"]) == (7, 8)]
    return {
        "piece": f"{path.parent.name}/{path.stem.replace('.sync', '')}",
        "bars": len(bars),
        "music_s": music_s,
        "odd_share": len(odd) / len(bars),
        "odd_when_behind": sum(1 for b in behind if tuple(b["meter"]) == (7, 8)) / len(behind)
        if behind else None,
        "stem_share": {k: sum(1 for b in bars if b["layers"][k]) / len(bars)
                       for k in ("drums", "bass", "pad", "lead")},
        "tension_mean": sum(b["tension"] for b in bars) / len(bars),
        "tension_max": max(b["tension"] for b in bars),
        "gap_range": (min(gaps), max(gaps)),
        "phase_max": max(phases),
    }


def fmt(v: float) -> str:
    return f"{v * 100:.0f}%"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()

    rows = [summarise(p) for p in args.files if p.exists()]
    print("| piece | bars | music s | odd % | odd\u2228behind % | drums | lead | tension mean | tension max | gap min | gap max |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        owb = "\u2014" if r["odd_when_behind"] is None else fmt(r["odd_when_behind"])
        print(f"| {r['piece']} | {r['bars']} | {r['music_s']:.0f} | {fmt(r['odd_share'])} "
              f"| {owb} | {fmt(r['stem_share']['drums'])} | {fmt(r['stem_share']['lead'])} "
              f"| {r['tension_mean']:.2f} | {r['tension_max']:.2f} "
              f"| {r['gap_range'][0]:+.2f} | {r['gap_range'][1]:+.2f} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
