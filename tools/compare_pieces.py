#!/usr/bin/env python3
"""Step-by-step comparison of two generated pieces.

Same-configuration seed pairs should show low token agreement, which is the
evidence that the system produces different pieces from one configuration.

    python3 tools/compare_pieces.py output/comeback-a output/comeback-a2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.corpus import read_midi_tokens  # noqa: E402
from tools.memorization import find_one, piece_config  # noqa: E402


def load_piece(src: Path) -> tuple[list[dict], dict]:
    cfg = piece_config(src)
    stems_cfg = cfg.get("stems", {"drums": {"drum": True}, "lead": {}})
    sync = json.loads(find_one(src, "*.sync.json").read_text())
    bars = read_midi_tokens(find_one(src, "*.mid"), sync, stems_cfg)
    return bars, stems_cfg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    args = ap.parse_args()

    bars_a, stems_cfg = load_piece(args.a)
    bars_b, _ = load_piece(args.b)
    if len(bars_a) != len(bars_b):
        raise SystemExit(f"different bar counts: {len(bars_a)} vs {len(bars_b)}")

    print("| stem | compared steps | identical | agreement |")
    print("|---|---|---|---|")
    for stem in stems_cfg:
        same = total = 0
        for ba, bb in zip(bars_a, bars_b):
            if not (ba["layers"].get(stem) and bb["layers"].get(stem)):
                continue
            for ta, tb in zip(ba["tokens"][stem], bb["tokens"][stem]):
                total += 1
                same += ta == tb
        pct = same / total if total else 0.0
        print(f"| {stem} | {total} | {same} | {pct:.0%} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
