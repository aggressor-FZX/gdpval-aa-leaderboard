#!/usr/bin/env python3
"""Significance analysis — is any model GENUINELY better than the incumbent?

The first pass reported "7 models beat DeepSeek V4.1 Flash" from raw mean
deltas of +1.2 to +3.7. That is not supportable: the incumbent's own run-to-run
standard deviation is 5.4 points, so a +1.2 mean difference is well inside its
own repeat noise.

This script answers the question that actually matters — is the difference
larger than the combined measurement error? — using Welch's t-test on the
per-run scores, and reports effect size (Cohen's d) alongside.

It also separates two things the raw leaderboard conflates:
  * SCORE     — points earned, which the gate clamp caps at 89
  * GATE RATE — how often the run was publishable at all
A model that scores 90 in one run out of three has a different problem from one
that scores 89 every time.
"""
from __future__ import annotations

import json
import math
import os
import statistics as st
import sys

RESULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "results", "contest_cheap_r1.json")
INCUMBENT_MATCH = "deepseek-v4.1-flash"
ALPHA = 0.05


def welch(a: list[float], b: list[float]) -> tuple[float, float]:
    """Welch t statistic and a two-sided p from the t distribution (normal approx).

    n=3 per group is small. A normal approximation is used deliberately and is
    reported as approximate; the conservative interpretation is that anything
    under ~2.5 in |t| is not evidence, and the script says so rather than
    pretending to a precise p-value.
    """
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan")
    va, vb = st.variance(a), st.variance(b)
    denom = math.sqrt(va / len(a) + vb / len(b))
    if denom == 0:
        return float("inf") if st.mean(a) != st.mean(b) else 0.0, 0.0
    t = (st.mean(a) - st.mean(b)) / denom
    # two-sided normal tail
    p = math.erfc(abs(t) / math.sqrt(2))
    return t, p


def cohens_d(a: list[float], b: list[float]) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    pooled = math.sqrt((st.variance(a) * (len(a) - 1) + st.variance(b) * (len(b) - 1))
                       / (len(a) + len(b) - 2))
    return (st.mean(a) - st.mean(b)) / pooled if pooled else float("nan")


def main(path: str = RESULT) -> int:
    payload = json.load(open(path))
    rows = payload["results"]
    ok = [r for r in rows if r.get("ok") and r.get("score") is not None]

    by_model: dict[str, list[dict]] = {}
    for r in ok:
        by_model.setdefault(r["model_id"], []).append(r)

    inc = next((v for k, v in by_model.items()
                if INCUMBENT_MATCH in k and "vision" not in k), None)
    if not inc:
        print("incumbent missing")
        return 1
    inc_scores = [r["score"] for r in inc]
    inc_lab = inc[0]["label"]
    print("=" * 108)
    print("SIGNIFICANCE TEST — is the difference bigger than the measurement noise?")
    print("=" * 108)
    print(f"incumbent: {inc_lab}")
    print(f"  scores {inc_scores}  mean {st.mean(inc_scores):.1f}  "
          f"sd {st.pstdev(inc_scores):.1f}  n={len(inc_scores)}")
    print(f"\n  A delta smaller than the incumbent's own spread cannot be trusted.")
    print(f"  With n=3 per model this test is weak; it is used to DISQUALIFY")
    print(f"  claims, not to certify winners. |t| < 2.5 => not evidence either way.\n")

    print(f"{'model':<34}{'n':>3}{'mean':>7}{'delta':>7}{'sd':>6}{'t':>7}"
          f"{'p':>7}{'d':>7}  verdict")
    print("-" * 108)

    rows_out = []
    for mid, rs in by_model.items():
        if mid == inc[0]["model_id"]:
            continue
        sc = [r["score"] for r in rs]
        if len(sc) < 2:
            print(f"{str(rs[0]['label'])[:32]:<34}{len(sc):>3}"
                  f"{st.mean(sc):>7.1f}{st.mean(sc)-st.mean(inc_scores):>+7.1f}"
                  f"{'-':>6}{'-':>7}{'-':>7}{'-':>7}  single run, untestable")
            continue
        t, p = welch(sc, inc_scores)
        d = cohens_d(sc, inc_scores)
        delta = st.mean(sc) - st.mean(inc_scores)
        if abs(t) >= 2.5 and p < ALPHA and abs(d) >= 0.8:
            verdict = "BETTER (significant)" if delta > 0 else "WORSE (significant)"
        elif delta > 0:
            verdict = "better? within noise"
        else:
            verdict = "no difference / worse"
        rows_out.append((delta, rs[0]["label"], st.mean(sc), len(sc),
                         st.pstdev(sc), t, p, d, verdict))
        print(f"{str(rs[0]['label'])[:32]:<34}{len(sc):>3}{st.mean(sc):>7.1f}"
              f"{delta:>+7.1f}{st.pstdev(sc):>6.1f}{t:>7.2f}{p:>7.3f}{d:>7.2f}  {verdict}")

    print("\n" + "=" * 108)
    print("CONCLUSION")
    print("=" * 108)
    sig_better = [r for r in rows_out if r[8].startswith("BETTER")]
    sig_worse = [r for r in rows_out if r[8].startswith("WORSE")]
    noise = [r for r in rows_out if "noise" in r[8]]
    print(f"  significantly better than the incumbent : {len(sig_better)}")
    for r in sorted(sig_better, reverse=True):
        print(f"    {str(r[1])[:40]:<42}{r[2]:>7.1f}  (t={r[5]:.1f}, d={r[7]:.1f})")
    print(f"  significantly worse                     : {len(sig_worse)}")
    print(f"  difference inside the noise             : {len(noise)}")
    for r in noise:
        print(f"    {str(r[1])[:40]:<42}{r[2]:>7.1f}  delta {r[0]:+.1f} "
              f"(t={r[5]:.1f} — inside repeat noise)")

    # ── gate reliability, separated from score ───────────────────────────
    print("\n" + "=" * 108)
    print("GATE RELIABILITY — separate from score, because the clamp caps it")
    print("=" * 108)
    print(f"{'model':<40}{'runs':>5}{'clean':>7}{'clean%':>8}{'mean':>7}")
    print("-" * 108)
    rel = []
    for mid, rs in by_model.items():
        clean = sum(1 for r in rs if not (r["gates"]["critical_fails"]
                                          or r["gates"]["non_critical_fails"]))
        rel.append((clean / len(rs), rs[0]["label"], len(rs), clean,
                    st.mean([r["score"] for r in rs])))
    for pct, lab, n, clean, mean in sorted(rel, reverse=True):
        print(f"{str(lab)[:38]:<40}{n:>5}{clean:>7}{pct*100:>7.0f}%{mean:>7.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*(sys.argv[1:2] or [])))
