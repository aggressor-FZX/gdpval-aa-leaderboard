"""Reporting: statistics per model + an explicit saturation verdict.

The point of this module is to make a non-discriminating result IMPOSSIBLE to
mistake for a ranking. v4 printed a leaderboard of 88-100 scores with no
warning; v2 computes the field's score spread and says plainly whether the
harness separated the models or not.
"""
from __future__ import annotations

import statistics as st


def _f(value, fmt="{:.1f}", dash="-"):
    """Format a possibly-None number, so the table never shows a bare 'None'."""
    return dash if value is None else fmt.format(value)


def summarise(payload: dict) -> list[dict]:
    """Aggregate per-model statistics across runs."""
    by_model: dict[str, list[dict]] = {}
    for r in payload.get("results", []):
        by_model.setdefault(r["model_id"], []).append(r)

    rows = []
    for mid, runs in by_model.items():
        ok = [r for r in runs if r.get("ok") and r.get("score") is not None]
        scores = [float(r["score"]) for r in ok]
        costs = [float(r["cost_usd"]) for r in runs if r.get("cost_usd") is not None]
        lat = [float(r["latency_s"]) for r in runs if r.get("latency_s")]
        gate_clean = [r for r in ok
                      if not r["gates"]["critical_fails"]
                      and not r["gates"]["non_critical_fails"]]
        rows.append({
            "model_id": mid,
            "label": runs[0]["label"],
            "effort": runs[0].get("effort"),
            "group": runs[0].get("group"),
            "n": len(runs),
            "n_ok": len(ok),
            "pass_rate": round(len(gate_clean) / len(ok), 2) if ok else 0.0,
            "mean": round(st.mean(scores), 1) if scores else None,
            "min": round(min(scores), 1) if scores else None,
            "max": round(max(scores), 1) if scores else None,
            "std": round(st.pstdev(scores), 1) if len(scores) > 1 else 0.0,
            "clamped": sum(1 for r in ok if r.get("clamped")),
            "cost_total": round(sum(costs), 5),
            "cost_per_run": round(st.mean(costs), 5) if costs else None,
            "latency_mean": round(st.mean(lat), 1) if lat else None,
        })
    rows.sort(key=lambda r: (r["mean"] is None, -(r["mean"] or 0)))
    return rows


def print_report(payload: dict) -> None:
    rows = summarise(payload)
    meta = payload.get("meta", {})
    ok_scores = [r["score"] for r in payload.get("results", [])
                 if r.get("ok") and r.get("score") is not None]

    print("\n" + "=" * 120)
    print("LEADERBOARD — v2 harness")
    print("=" * 120)
    print(f"{'#':<3}{'model':<38}{'eff':<7}{'n':>3}{'pass':>6}{'mean':>7}"
          f"{'min':>6}{'max':>6}{'std':>6}{'clamp':>6}{'$/run':>10}{'s':>6}")
    print("-" * 120)
    for i, r in enumerate(rows, 1):
        print(f"{i:<3}{str(r['label'])[:36]:<38}{str(r['effort'] or '-'):<7}"
              f"{r['n_ok']:>3}{r['pass_rate']:>6.2f}"
              f"{_f(r['mean'], '{:.1f}'):>7}"
              f"{_f(r['min'], '{:.1f}'):>6}"
              f"{_f(r['max'], '{:.1f}'):>6}"
              f"{r['std']:>6.1f}{r['clamped']:>6}"
              f"{_f(r['cost_per_run'], '${:.5f}'):>10}"
              f"{_f(r['latency_mean'], '{:.0f}'):>6}")

    # ── saturation verdict ────────────────────────────────────────────────
    print("\n" + "=" * 120)
    print("SATURATION CHECK — does this harness actually separate the models?")
    print("=" * 120)
    if len(ok_scores) < 2:
        print("  Too few successful runs to assess separation.")
    else:
        spread = max(ok_scores) - min(ok_scores)
        stdev = st.pstdev(ok_scores)
        perfect = sum(1 for s in ok_scores if s >= 99.5)
        print(f"  scores           : n={len(ok_scores)}  min={min(ok_scores):.1f}  "
              f"max={max(ok_scores):.1f}  mean={st.mean(ok_scores):.1f}")
        print(f"  spread           : {spread:.1f} points   std dev {stdev:.2f}")
        print(f"  perfect (>=99.5) : {perfect}/{len(ok_scores)}")
        if spread < 15:
            print("\n  VERDICT: NOT DISCRIMINATING.")
            print("  Spread is under 15 points, so these rankings should not be used")
            print("  to choose between models. Widen task difficulty, add a harder")
            print("  discriminator, or report the tie honestly. v4 spanned 88-100")
            print("  (12 points) with 9 perfect scores and published it as a")
            print("  leaderboard anyway; v2 flags this instead.")
        else:
            print(f"\n  VERDICT: discriminating ({spread:.1f}-point spread).")

    # ── cost efficiency ───────────────────────────────────────────────────
    ranked = [r for r in rows if r["mean"] and r["cost_per_run"]]
    if ranked:
        print("\n" + "=" * 120)
        print("COST EFFICIENCY — quality points per dollar")
        print("=" * 120)
        eff = sorted(ranked, key=lambda r: -(r["mean"] / max(r["cost_per_run"], 1e-9)))
        print(f"{'model':<38}{'mean score':>11}{'$/run':>12}{'pts/$':>10}")
        print("-" * 120)
        for r in eff:
            pts = r["mean"] / max(r["cost_per_run"], 1e-9)
            print(f"{str(r['label'])[:36]:<38}{r['mean']:>11.1f}"
                  f"{r['cost_per_run']:>12.5f}{pts:>10.0f}")

    if meta.get("spent_usd") is not None:
        print(f"\n  spent ${meta['spent_usd']:.4f} of "
              f"${meta.get('budget_ceiling_usd', 0):.2f} ceiling"
              f" | skipped {meta.get('requests_skipped_budget', 0)} request(s)")
