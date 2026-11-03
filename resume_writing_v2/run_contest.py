#!/usr/bin/env python3
"""Run the cheap-model writing contest, writing progress to a log file.

Run as a plain script (not a heredoc) so output is line-buffered to a file and
progress is observable while it runs.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_writing_v2 import contestants, runner, task

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "contest_cheap_r1.json")
LOG = os.path.join(HERE, "results", "contest_cheap_r1.log")

RUNS = int(os.environ.get("RUNS", "3"))
BUDGET = float(os.environ.get("BUDGET", "4.00"))
MAX_MODELS = int(os.environ.get("MAX_MODELS", "0"))     # 0 = all


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)


def main() -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    ents = contestants.build(verbose=False)
    if MAX_MODELS:
        ents = ents[:MAX_MODELS]
    log(f"{len(ents)} models x {RUNS} runs, budget ${BUDGET:.2f}")

    payload = runner.run(ents, task.build_prompt(), task.SYSTEM_PROMPT,
                         runs=RUNS, budget_usd=BUDGET, out_path=OUT)
    log(f"done: spent ${payload['meta']['spent_usd']:.4f} "
        f"of ${payload['meta']['budget_ceiling_usd']:.2f}")
    ok = sum(1 for r in payload["results"] if r.get("ok"))
    log(f"scorable runs {ok}/{len(payload['results'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
