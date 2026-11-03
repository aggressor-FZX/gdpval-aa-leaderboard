#!/usr/bin/env python3
"""Round 2 — focused, higher-n run on the contenders that were inside noise.

Round 1 (n=3) could not resolve the question: 7 models had positive deltas of
+1.2 to +3.7 over the incumbent, but every one had |t| < 0.9, because the
incumbent's own repeat sd is 5.4. Reporting those as "winners" would repeat the
v4 mistake of publishing noise as a ranking.

This round re-runs only the models whose delta was positive or very close, with
n=8 per model, plus the incumbent as the control. That gives enough runs to
resolve a 3-point difference if it is real.

Selection rule (stated so it cannot be accused of cherry-picking):
  every model whose round-1 mean was >= incumbent mean - 4 points.
Models significantly WORSE in round 1 are excluded: they cannot become
contenders and re-measuring them wastes budget.
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_writing_v2 import runner, task
from resume_writing_v2.config import ModelEntry

HERE = os.path.dirname(os.path.abspath(__file__))
R1 = os.path.join(HERE, "results", "contest_cheap_r1.json")
OUT = os.path.join(HERE, "results", "contest_cheap_r2.json")
INCUMBENT = "deepseek-v4.1-flash"
MARGIN = 4.0          # include anyone within 4 points of the incumbent
N_RUNS = 8


def contenders() -> list[ModelEntry]:
    payload = json.load(open(R1))
    ok = [r for r in payload["results"]
          if r.get("ok") and r.get("score") is not None]
    by: dict[str, list[dict]] = {}
    for r in ok:
        by.setdefault(r["model_id"], []).append(r)

    inc = next(v for k, v in by.items() if INCUMBENT in k and "vision" not in k)
    inc_mean = st.mean([r["score"] for r in inc])

    keep = []
    for mid, rs in by.items():
        mean = st.mean([r["score"] for r in rs])
        if mid == inc[0]["model_id"]:
            keep.append((mid, rs[0]["label"], mean))
        elif mean >= inc_mean - MARGIN:
            keep.append((mid, rs[0]["label"], mean))

    keep.sort(key=lambda x: -x[2])
    print(f"incumbent mean {inc_mean:.1f}; including models >= {inc_mean - MARGIN:.1f}")
    print(f"{'included':<40}{'r1 mean':>9}")
    print("-" * 52)
    for mid, lab, mean in keep:
        print(f"{str(lab)[:38]:<40}{mean:>9.1f}")
    print(f"\n{len(keep)} models x {N_RUNS} runs = {len(keep) * N_RUNS} requests")

    return [ModelEntry(model_id=m, label=lab, group="round2", max_tokens=16384)
            for m, lab, _ in keep]


def main() -> int:
    ents = contenders()
    payload = runner.run(ents, task.build_prompt(), task.SYSTEM_PROMPT,
                         runs=N_RUNS, budget_usd=3.00, out_path=OUT)
    print(f"\nspent ${payload['meta']['spent_usd']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
