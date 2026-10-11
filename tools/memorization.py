#!/usr/bin/env python3
"""Verbatim-memorization analysis for generated pieces.

Reconstructs each piece's step tokens from its .mid + sync log and measures
the longest run of tokens that matches a training sequence exactly, per
(stem, meter), plus the fraction of steps covered by matches of >= MIN_RUN
steps. Long runs at high order are the memorization risk discussed in the
report's order trade-off.

    python3 tools/memorization.py output/[!_]*/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.corpus import load, read_midi_tokens, training_sequences  # noqa: E402

MIN_RUN = 4


def find_one(src: Path, pattern: str) -> Path:
    matches = sorted(src.glob(pattern))
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one {pattern} in {src}, found {len(matches)}")
    return matches[0]


def piece_config(src: Path) -> dict:
    runs = sorted(src.glob("*.run.json"))
    return json.loads(runs[0].read_text())["config"] if runs else {}


def meter_runs(bars: list[dict], stem: str) -> list[tuple[str, list]]:
    """Consecutive same-meter stretches where the stem is playing."""
    runs: list[tuple[str, list]] = []
    cur_meter: str | None = None
    cur: list = []
    for bar in bars:
        if not bar["layers"].get(stem, False):
            if cur:
                runs.append((cur_meter, cur))
                cur, cur_meter = [], None
            continue
        if bar["meter"] != cur_meter:
            if cur:
                runs.append((cur_meter, cur))
            cur, cur_meter = [], bar["meter"]
        cur.extend(bar["tokens"][stem])
    if cur:
        runs.append((cur_meter, cur))
    return runs


def match_stats(gen: list, train_seqs: list[list], min_run: int = MIN_RUN) -> tuple[int, float]:
    """(longest verbatim run, fraction of steps covered by runs >= min_run)."""
    n = len(gen)
    covered = [False] * n
    longest = 0
    for train in train_seqs:
        m = len(train)
        prev = [0] * (m + 1)
        for i in range(1, n + 1):
            cur = [0] * (m + 1)
            token = gen[i - 1]
            best = 0
            for j in range(1, m + 1):
                if token == train[j - 1]:
                    v = prev[j - 1] + 1
                    cur[j] = v
                    if v > best:
                        best = v
            if best >= min_run:
                for k in range(i - best, i):
                    covered[k] = True
                longest = max(longest, best)
            prev = cur
    return longest, (sum(covered) / n if n else 0.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pieces", nargs="*", type=Path,
                    help="piece output directories (default: every output/[!_]*/ directory)")
    args = ap.parse_args()
    pieces = args.pieces or sorted(p for p in (ROOT / "output").glob("[!_]*") if p.is_dir())
    corpus = load(ROOT / "corpus" / "corpus.json")

    detailed = []
    for src in pieces:
        cfg = piece_config(src)
        stems_cfg = cfg.get("stems", {"drums": {"drum": True}, "lead": {}})
        sync = json.loads(find_one(src, "*.sync.json").read_text())
        bars = read_midi_tokens(find_one(src, "*.mid"), sync, stems_cfg)
        for stem in stems_cfg:
            for meter, gen in meter_runs(bars, stem):
                train = training_sequences(corpus, meter, stem)
                if not train or not gen:
                    continue
                longest, coverage = match_stats(gen, train)
                detailed.append({
                    "piece": src.name, "order": cfg.get("order"),
                    "stem": stem, "meter": meter, "gen": len(gen),
                    "corpus": sum(len(s) for s in train),
                    "longest": longest, "coverage": coverage,
                })

    print("| piece | order | gen steps | longest verbatim run | coverage (runs >= 4 steps) |")
    print("|---|---|---|---|---|")
    for src in pieces:
        rows = [r for r in detailed if r["piece"] == src.name]
        if not rows:
            continue
        gen = sum(r["gen"] for r in rows)
        longest = max(r["longest"] for r in rows)
        cov = sum(r["coverage"] * r["gen"] for r in rows) / gen if gen else 0.0
        print(f"| {src.name} | {rows[0]['order']} | {gen} | {longest} steps | {cov:.0%} |")
    print()
    print("| piece | stem/meter | gen steps | corpus steps | longest run | coverage (runs >= 4 steps) |")
    print("|---|---|---|---|---|---|")
    for r in detailed:
        print(f"| {r['piece']} | {r['stem']}/{r['meter']} | {r['gen']} | {r['corpus']} "
              f"| {r['longest']} steps | {r['coverage']:.0%} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
