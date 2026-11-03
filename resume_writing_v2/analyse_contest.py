#!/usr/bin/env python3
"""Analyse the cheap-model writing contest.

Reports three things, in this order of importance:

1. TRUST CHECK — does the harness actually separate these models? If the score
   spread is small, the leaderboard is not usable and this script says so before
   printing any ranking.

2. THE HEADLINE QUESTION — is any cheap model actually better than DeepSeek
   V4.1 Flash on a real resume task, and by how much?

3. COST — quality points per dollar, so "cheaper" is evaluated against output
   quality rather than assumed.
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_writing_v2 import report
from resume_writing_v2.config import WORD_MIN, WORD_MAX

RESULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "results", "contest_cheap_r1.json")


def _gate_clean(r):
    g = r.get("gates") or {}
    return not g.get("critical_fails") and not g.get("non_critical_fails")


def main(path: str = RESULT) -> int:
    if not os.path.exists(path):
        print(f"no results at {path}")
        return 1
    payload = json.load(open(path))
    rows = payload["results"]
    meta = payload["meta"]

    ok = [r for r in rows if r.get("ok") and r.get("score") is not None]
    print("=" * 120)
    print("CHEAP-MODEL RESUME-WRITING CONTEST")
    print("=" * 120)
    print(f"models {meta['models']} | requests {meta['requests_planned']} "
          f"| completed {len(rows)} | spend ${meta['spent_usd']:.4f}")
    print(f"scored runs {len(ok)} | unscorable {len(rows) - len(ok)}")

    # ── 1. TRUST CHECK ───────────────────────────────────────────────────
    print("\n" + "=" * 120)
    print("1. TRUST CHECK — does this harness discriminate?")
    print("=" * 120)
    scores = [r["score"] for r in ok]
    if len(scores) < 4:
        print("  FAIL: too few scored runs to judge.")
        return 1
    spread = max(scores) - min(scores)
    print(f"  individual runs : n={len(scores)} min={min(scores):.1f} "
          f"max={max(scores):.1f} mean={st.mean(scores):.1f} sd={st.pstdev(scores):.2f}")
    print(f"  spread          : {spread:.1f} points")

    per_model = {}
    for r in ok:
        per_model.setdefault(r["model_id"], []).append(r)

    within = []
    for mid, rs in per_model.items():
        if len(rs) > 1:
            vals = [x["score"] for x in rs]
            within.append(max(vals) - min(vals))
    if within:
        print(f"  within-model sd : mean {st.mean(within):.1f} points across "
              f"{len(within)} models run twice")
        print("  (within-model noise must be smaller than between-model spread, "
              "or the ranking is noise)")
        verdict = "TRUSTWORTHY" if spread > 3 * st.mean(within) else "NOISY"
        print(f"  verdict         : {verdict} — spread {spread:.1f} vs "
              f"{st.mean(within):.1f} within-model repeat error")
    else:
        print("  only one run per model; cannot separate signal from repeat noise")

    # ceiling / floor check
    perfect = sum(1 for s in scores if s >= 99.5)
    print(f"  perfect scores  : {perfect}/{len(scores)}")

    # ── 2. LEADERBOARD ───────────────────────────────────────────────────
    print("\n" + "=" * 120)
    print("2. LEADERBOARD — mean of runs, gate-clean runs counted separately")
    print("=" * 120)
    report.print_report(payload)

    # ── 3. THE INCUMBENT COMPARISON ──────────────────────────────────────
    print("\n" + "=" * 120)
    print("3. AGAINST THE INCUMBENT — DeepSeek V4.1 Flash")
    print("=" * 120)
    base = None
    for mid, rs in per_model.items():
        if "deepseek-v4.1-flash" in mid and "vision" not in mid:
            base = rs
            break
    if not base:
        print("  incumbent did not produce a scorable run — cannot compare")
    else:
        bmean = st.mean([r["score"] for r in base])
        bcost = st.mean([r["cost_usd"] for r in base])
        print(f"  incumbent: {base[0]['label']}  mean score {bmean:.1f}  "
              f"${bcost:.5f}/run")
        print(f"\n  {'model':<40}{'score':>7}{'delta':>8}{'$/run':>10}{'cost x':>8}"
              f"  gate-clean")
        print("  " + "-" * 108)
        comp = []
        for mid, rs in per_model.items():
            if mid == base[0]["model_id"]:
                continue
            m = st.mean([r["score"] for r in rs])
            c = st.mean([r["cost_usd"] for r in rs])
            clean = all(_gate_clean(r) for r in rs)
            comp.append((m, rs[0]["label"], m - bmean, c, c / bcost if bcost else 0,
                         clean))
        for m, lab, d, c, ratio, clean in sorted(comp, reverse=True):
            print(f"  {str(lab)[:38]:<40}{m:>7.1f}{d:>+8.1f}{c:>10.5f}{ratio:>7.2f}x"
                  f"  {'yes' if clean else 'NO'}")

        winners = [(m, lab, c, r) for m, lab, d, c, r, cl in comp if d > 0]
        print(f"\n  models that BEAT the incumbent on score: {len(winners)}")
        for m, lab, c, r in sorted(winners, reverse=True):
            print(f"    {str(lab)[:38]:<40}{m:>7.1f}  ${c:.5f}/run "
                  f"({r:.2f}x incumbent cost)")

    # ── 4. COST EFFICIENCY ───────────────────────────────────────────────
    print("\n" + "=" * 120)
    print("4. COST EFFICIENCY — quality per dollar, gate-clean runs only")
    print("=" * 120)
    eff = []
    for mid, rs in per_model.items():
        goods = [r for r in rs if _gate_clean(r)]
        if not goods:
            continue
        m = st.mean([r["score"] for r in goods])
        c = st.mean([r["cost_usd"] for r in goods])
        eff.append((m / c if c else 0, rs[0]["label"], m, c))
    for ratio, lab, m, c in sorted(eff, reverse=True)[:20]:
        print(f"  {str(lab)[:38]:<40}{m:>7.1f}  ${c:.5f}/run  {ratio:>10.0f} pts/$")

    # ── 5. FAILURES ──────────────────────────────────────────────────────
    bad = [r for r in rows if not r.get("ok")]
    if bad:
        print("\n" + "=" * 120)
        print(f"5. UNSCORABLE RUNS ({len(bad)})")
        print("=" * 120)
        for r in bad:
            print(f"  {str(r['label'])[:36]:<38} {str(r.get('error'))[:76]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*(sys.argv[1:2] or [])))
