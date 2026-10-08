#!/usr/bin/env python3
"""Command line entry point.

    python -m engine \\
        --race web/data/comeback.json \\
        --corpus corpus/corpus.json \\
        --config configs/pieces/comeback-a.json \\
        --out output/comeback-a

Config resolution: configs/base.json is loaded first, then the --config file
overrides it (shallow merge). See docs/engine.md for the keys.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from .corpus import load as load_corpus  # noqa: E402
from .generate import generate, resolve_hooks  # noqa: E402
from .race import RaceRecording  # noqa: E402


def load_config(path: str | Path) -> dict:
    path = Path(path)
    base_path = ROOT / "configs" / "base.json"
    cfg = json.loads(base_path.read_text()) if base_path.exists() else {}
    if path.resolve() != base_path.resolve():
        if not path.exists():
            raise SystemExit(f"config not found: {path}")
        cfg.update(json.loads(path.read_text()))
    return cfg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate one piece for one race recording.")
    ap.add_argument("--race", required=True, help="gm-race/1 recording (e.g. web/data/comeback.json)")
    ap.add_argument("--corpus", default="corpus/corpus.json", help="gm-corpus/1 file")
    ap.add_argument("--config", default="configs/base.json", help="piece config (merged over configs/base.json)")
    ap.add_argument("--out", default=None, help="output directory (default: output/<piece name>)")
    ap.add_argument("--name", default=None, help="output file base name (default: race name)")
    ap.add_argument("--hooks", default=None, help="override hooks module (default from config)")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    if args.hooks:
        cfg["hooks"] = args.hooks
    out_dir = Path(args.out) if args.out else ROOT / "output" / Path(args.config).stem

    hooks = resolve_hooks(cfg.get("hooks", "engine.hooks"))
    race = RaceRecording.load(args.race)
    corpus = load_corpus(args.corpus)

    try:
        result = generate(race, corpus, cfg, hooks, out_dir, name=args.name)
    except NotImplementedError as exc:
        print(f"\nNot implemented yet: {exc}", file=sys.stderr)
        print("Hint: the holes you fill live in engine/hooks.py and engine/markov.py.",
              file=sys.stderr)
        return 2

    m = result["metrics"]
    print(f"wrote {result['midi'].relative_to(ROOT)}")
    print(f"wrote {result['sync'].relative_to(ROOT)}")
    print(f"  {m['bars']} bars, {m['music_s']}s, odd meter {m['odd_share']:.0%}, "
          f"tension mean {m['tension_mean']} max {m['tension_max']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
