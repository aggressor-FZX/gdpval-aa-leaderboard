#!/usr/bin/env python3
"""Entry point for the v2 resume-writing competition.

Usage:
    python resume_writing_v2/run_competition.py --shortlist
    python resume_writing_v2/run_competition.py --dry-run
    python resume_writing_v2/run_competition.py --models shortlist --runs 3 --budget 2.00

Nothing spends money without --dry-run being omitted AND a budget being set.
"""
from __future__ import annotations

import argparse
import os
import sys

# allow running as a plain script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_writing_v2.config import (ModelEntry, RUNS_PER_MODEL, MAX_SPEND_USD,
                                      api_key, aa_key)
from resume_writing_v2.task import build_prompt, SYSTEM_PROMPT
from resume_writing_v2 import runner, report, shortlist

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def _entries_from_shortlist(rows, limit: int, group: str = "shortlist"):
    out = []
    for r in rows[:limit]:
        out.append(ModelEntry(model_id=r["or_id"], label=r["aa_name"],
                              effort=None, group=group))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="v2 resume-writing competition harness")
    ap.add_argument("--shortlist", action="store_true",
                    help="print the AA writing-adjacent proxy shortlist and exit")
    ap.add_argument("--shortlist-limit", type=int, default=12,
                    help="how many shortlist models to compete (default 12)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show the plan and cost estimate; make no API calls")
    ap.add_argument("--runs", type=int, default=RUNS_PER_MODEL)
    ap.add_argument("--budget", type=float, default=MAX_SPEND_USD,
                    help=f"hard spend ceiling in USD (default {MAX_SPEND_USD:.2f})")
    ap.add_argument("--models", default="shortlist", choices=["shortlist"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    key = api_key()          # OpenRouter — for inference
    akey = aa_key()          # Artificial Analysis — for the proxy shortlist

    print("Building resume-writing shortlist ...")
    rows = shortlist.build(akey)
    rows = shortlist.attach_personality(rows)          # real scores replace the proxy
    rows.sort(key=lambda r: -(r.get("writing_score") or 0))
    shortlist.print_shortlist(rows, limit=25)
    print(f"\nshortlist size (AA + OpenRouter reachable): {len(rows)}")

    if args.shortlist:
        return 0

    entries = _entries_from_shortlist(rows, args.shortlist_limit)
    prompt = build_prompt()
    out = args.out or os.path.join(RESULTS_DIR, "resume_v2_results.json")

    payload = runner.run(entries, prompt, SYSTEM_PROMPT, runs=args.runs,
                         budget_usd=args.budget, out_path=None if args.dry_run else out,
                         dry_run=args.dry_run)
    if not args.dry_run:
        report.print_report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
