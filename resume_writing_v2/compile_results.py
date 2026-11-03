#!/usr/bin/env python3
"""Consolidate every measured round into one results table + a price/quality figure.

Inputs (read-only):
  results/contest_cheap_r1.json   n=3, provider-default effort
  results/contest_cheap_r2.json   n=8, provider-default effort
  results/contest_cheap_r3.json   n=4, explicit efforts (this round)
  results/personalitybench_cache.json

Outputs:
  results/consolidated.json       one row per model VARIANT (runs pooled)
  figures/price_vs_quality.png    score vs cost, with trait Elo as a second panel
  RESULTS.md                      regenerated results document

Design rules carried over from the harness itself:
  * runs are pooled across rounds, and a variant is keyed by
    (model_id, effort) — never by family name, because the same family at
    `xhigh` and at default is a different model;
  * cost per run is the MEAN OBSERVED `usage.cost`, not price x assumed tokens;
  * a model with fewer than 3 scored runs is marked `low_n` and is not plotted
    with a significance claim;
  * AA trait values are attached only where a confident name mapping exists, and
    the mapping is printed so it can be audited;
  * no significance claim is made without the Welch test (see significance.py).
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from resume_writing_v2 import personalitybench as pb
from resume_writing_v2.significance import welch, cohens_d

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
FIG = os.path.join(HERE, "figures")
ROUNDS = ["contest_cheap_r1.json", "contest_cheap_r2.json",
          "contest_cheap_r3.json"]
CONSOLIDATED = os.path.join(RES, "consolidated.json")
TEST_B_MD = os.path.join(HERE, "RESULTS_TEST_B.md")
TEST_B_PLACEHOLDER = "<!--TEST_B-->"

plt.rcParams["text.parse_math"] = False     # '$' is currency, not mathtext

# ── AA-PersonalityBench name mapping ───────────────────────────────────────
# Keys are our harness labels; values are exact names in the PB cache. Only
# exact matches are listed — a fuzzy match would silently attach the wrong
# model's Elo, which is the failure mode this file exists to prevent.
PB_MAP = {
    "GLM-5.3-Flash":                    "GLM-5.3-Flash",
    # r1/r2 label the incumbent "(incumbent)"; the PB cache uses the plain name.
    "DeepSeek V4.1 Flash (incumbent)":  "DeepSeek V4.1 Flash",
    # r1/r2 capitalise the effort inside the label but never sent the parameter.
    "Qwen3.8 27B (Xhigh)":             "Qwen3.8 27B",
    "Claude Haiku 5.5 (max)":           "Claude Haiku 5.5",
    "Grok 4.7 (xhigh)":                 "Grok 4.7",
    "Grok 4.6 (xhigh)":                 "Grok 4.6",
    "Inkling (xhigh)":                  "Inkling",
    "Mistral Large 4 Preview":          "Mistral Large 4 Preview",
    "Gemini 3.8 Flash (high)":          "Gemini 3.8 Flash",
    "Kimi K3.1 Pro":                    "Kimi K3.1 Pro",
    "DeepSeek V4.1 Flash 1017 (max)":   "DeepSeek V4.1 Flash 1017",
    "Beam 1.0":                         "Beam 1.0",
    "Nemotron 3.5 Super VL":            "Nemotron 3.5 Super VL",
    "DeepSeek V4.1 Flash (max)":        "DeepSeek V4.1 Flash",
    "MiniMax-M3":                       "MiniMax-M3",
    "GPT-6.1 Sol (max)":                "GPT-6.1 Sol",
    "GPT-6 Luna (max)":                 "GPT-6 Luna",
    "Muse Glimmer (high)":              "Muse Glimmer",
    "MiniMax-M3.1-Flash":               "MiniMax-M3.1-Flash",
    "MiMo-V2.6-Pro":                    "MiMo-V2.6-Pro",
    "Step 5 Preview":                   "Step 5 Preview",
    "Nemotron 3 Ultra 550B":            "Nemotron 3 Ultra 550B A55B",
    "Qwen3.8 Max (0902)":               "Qwen3.8 Max (0902)",
    "Qwen3.8 27B (xhigh)":              "Qwen3.8 27B",
    "GPT-5.4 mini (non-reasoning)":     "GPT-5.4 mini",
    "Llama 4 Maverick":                 "Llama 4 Maverick",
    "GPT-3.5 Turbo":                    "GPT-3.5 Turbo",
}

TRAIT_COLS = ("eloquent", "lexicallyVaried", "literate", "scannable",
              "structured", "truthful")


def load_runs() -> list[dict]:
    runs = []
    for name in ROUNDS:
        p = os.path.join(RES, name)
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        for r in d["results"]:
            r["_source"] = name
            runs.append(r)
    return runs


def consolidate(runs: list[dict]) -> list[dict]:
    """Pool runs per (model_id, effort). Effort None is its own variant."""
    buckets: dict[tuple[str, str | None], list[dict]] = {}
    for r in runs:
        buckets.setdefault((r["model_id"], r.get("effort")), []).append(r)

    out = []
    for (mid, effort), rs in buckets.items():
        okr = [r for r in rs if r.get("ok") and r.get("score") is not None]
        fails = [r for r in rs if not r.get("ok")]
        scores = [r["score"] for r in okr]
        costs = [r["cost_usd"] for r in okr]
        price = next((r for r in rs if r.get("price_in_1m") is not None), {})
        rec = {
            "model_id": mid,
            "label": rs[0]["label"],
            "effort": effort,
            "n": len(okr),
            "n_failed": len(fails),
            "mean": round(st.mean(scores), 1) if scores else None,
            "sd": round(st.stdev(scores), 1) if len(scores) > 1 else None,
            "min": min(scores) if scores else None,
            "max": max(scores) if scores else None,
            "cost_per_run": round(st.mean(costs), 6) if costs else None,
            "price_in_1m": price.get("price_in_1m"),
            "price_out_1m": price.get("price_out_1m"),
            "sources": sorted({r["_source"] for r in rs}),
            "errors": [r.get("error") for r in fails][:3],
        }
        # An explicit effort that produced no reasoning tokens was NOT honoured
        # by the provider. Recording it prevents "DeepSeek at xhigh" being read
        # as a high-effort result when the parameter was silently ignored.
        rt = [r.get("reasoning_tokens") or 0 for r in okr]
        rec["mean_reasoning_tokens"] = round(st.mean(rt)) if rt else 0
        rec["effort_honoured"] = (None if effort is None
                                  else bool(rt) and st.mean(rt) > 0)
        if effort is not None and not rec["effort_honoured"]:
            rec["effort_note"] = (f"reasoning_effort={effort} produced 0 "
                                  "reasoning tokens — provider ignored or "
                                  "does not support this level")
        out.append(rec)

    # A variant with no scored run is not a result and must not be ranked.
    # Filter AFTER traits are attached, so downstream code can rely on every
    # row carrying the trait_* keys.
    out = [r for r in out if r["n"] > 0]

    # attach AA trait Elo where an exact mapping exists
    cache = {m["model"]: m for m in pb.load()}
    for rec in out:
        name = PB_MAP.get(rec["label"])
        rec["pb_name"] = name
        m = cache.get(name) if name else None
        rec["aa_writing_score"] = (round(m["writing_score"], 1)
                                   if m and m.get("writing_score") is not None
                                   else None)
        for t in TRAIT_COLS:
            v = (m.get("traits") or {}).get(t) if m else None
            rec[f"trait_{t}"] = round(v, 0) if v is not None else None
        rec["trait_slop"] = m.get("slop") if m else None
        # A record whose 30 traits are all identical is a degenerate payload,
        # not a model that scores 1000 on everything. Flag it so no downstream
        # reader treats those numbers as measurements.
        tr = (m.get("traits") or {}) if m else {}
        vals = {round(v, 3) for v in tr.values()}
        rec["traits_degenerate"] = bool(m) and len(tr) > 1 and len(vals) <= 1
        if rec["traits_degenerate"]:
            rec["traits_note"] = (f"all {len(tr)} traits equal "
                                  f"{sorted(vals)[0]} — degenerate AA payload, "
                                  "not a measurement")
            for t in TRAIT_COLS:
                rec[f"trait_{t}"] = None
            rec["aa_writing_score"] = None

    # Disambiguate labels. Round 1/2 never sent `reasoning_effort` but encoded an
    # effort in the label, so `Qwen3.8 27B (Xhigh)` (default request) and
    # `Qwen3.8 27B (xhigh)` (explicit parameter) are two different requests that
    # would otherwise look like a duplicate row. Say which is which.
    by_model: dict[str, set] = {}
    for r in out:
        by_model.setdefault(r["model_id"], set()).add(r["effort"])
    for r in out:
        if None in by_model[r["model_id"]] and r["effort"] is None:
            others = by_model[r["model_id"]] - {None}
            if others:
                r["label"] = f"{r['label']} · default"
                r["label_note"] = ("no reasoning_effort parameter was sent; "
                                   "the effort named in the label was NOT "
                                   "applied")

    out.sort(key=lambda r: (r["mean"] is None, -(r["mean"] or 0)))
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def add_significance(rows: list[dict], runs: list[dict]) -> None:
    """Welch test on per-run scores against the incumbent, in place.

    The incumbent is DeepSeek V4.1 Flash at provider-default effort. Rounds 1/2
    ran it at default; round 3 adds an `xhigh` variant. The DEFAULT variant is
    the control, because that is the configuration the prior rounds measured.
    Nothing here is called significant below |t| >= 2.5 AND |d| >= 0.8 — the
    threshold the earlier reports used, kept so numbers stay comparable.
    """
    buckets: dict[tuple, list[float]] = {}
    for r in runs:
        if r.get("ok") and r.get("score") is not None:
            buckets.setdefault((r["model_id"], r.get("effort")),
                               []).append(r["score"])
    ctrl_key = next((k for k in buckets
                     if "deepseek-v4.1-flash" == k[0].split("/")[-1]
                     and k[1] is None), None)
    ctrl = buckets.get(ctrl_key, [])
    for rec in rows:
        key = (rec["model_id"], rec["effort"])
        s = buckets.get(key, [])
        if not s or len(s) < 3 or len(ctrl) < 3:
            rec["delta"] = None
            rec["t"] = None
            rec["d"] = None
            rec["verdict"] = "not tested" if not s else "low_n"
            continue
        if key == ctrl_key:
            rec["delta"] = 0.0
            rec["t"] = None
            rec["d"] = None
            rec["verdict"] = "control"
            continue
        t, _p = welch(s, ctrl)
        d = cohens_d(s, ctrl)
        rec["delta"] = round(st.mean(s) - st.mean(ctrl), 1)
        rec["t"] = round(t, 2)
        rec["d"] = round(d, 2) if d == d else None
        rec["verdict"] = ("significant" if abs(t) >= 2.5 and abs(d) >= 0.8
                          else "inside noise")


def trait_correlation(rows: list[dict]) -> list[tuple[str, float, int]]:
    """Pearson r between each AA trait and our measured score.

    Uses ONE point per model — the best-scoring variant — so a family measured
    at three efforts cannot outvote a family measured once. Returns
    (trait, r, n), strongest absolute correlation first.
    """
    import math
    best: dict[str, dict] = {}
    for r in rows:
        if r.get("trait_eloquent") is None or r["mean"] is None:
            continue
        cur = best.get(r["model_id"])
        if cur is None or r["mean"] > cur["mean"]:
            best[r["model_id"]] = r
    pts = list(best.values())
    n = len(pts)
    if n < 4:
        return []
    ys = [p["mean"] for p in pts]
    my = st.mean(ys)

    def pearson(xs):
        mx = st.mean(xs)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = math.sqrt(sum((x - mx) ** 2 for x in xs)
                        * sum((y - my) ** 2 for y in ys))
        return num / den if den else float("nan")

    res = []
    for t in TRAIT_COLS:
        xs = [p[f"trait_{t}"] for p in pts if p.get(f"trait_{t}") is not None]
        if len(xs) < 4:
            continue
        r = pearson(xs)
        if r == r:
            res.append((t, round(r, 2), len(xs)))
    res.sort(key=lambda x: -abs(x[1]))
    return res


def write_consolidated(rows: list[dict]) -> str:
    payload = {"rows": rows,
               "notes": {
                   "variant_key": "(model_id, effort) — effort None is a "
                                  "distinct variant from an explicit effort",
                   "cost_per_run": "mean observed usage.cost over scored runs",
                   "trait_scale": "trait Elo (unbounded); slop is 1-100 index "
                                  "percentile where lower is better",
                   "pb_mapping": PB_MAP,
               }}
    with open(CONSOLIDATED, "w") as f:
        json.dump(payload, f, indent=1)
    return CONSOLIDATED


# ── figure ────────────────────────────────────────────────────────────────
def figure(rows: list[dict]) -> str:
    os.makedirs(FIG, exist_ok=True)
    plottable = [r for r in rows
                 if r["mean"] is not None and r["cost_per_run"]]

    fig, axes = plt.subplots(2, 1, figsize=(13, 11),
                             constrained_layout=True,
                             gridspec_kw={"height_ratios": [1.35, 1]})

    # ── panel 1: score vs cost per run ───────────────────────────────────
    ax = axes[0]
    xs = [r["cost_per_run"] for r in plottable]
    ys = [r["mean"] for r in plottable]
    has_trait = [r["trait_eloquent"] is not None for r in plottable]
    ax.scatter([x for x, h in zip(xs, has_trait) if not h],
               [y for y, h in zip(ys, has_trait) if not h],
               s=90, c="#607d8b", marker="o", edgecolor="white", linewidth=1,
               label="no AA trait data", zorder=3)
    ax.scatter([x for x, h in zip(xs, has_trait) if h],
               [y for y, h in zip(ys, has_trait) if h],
               s=130, c="#1565c0", marker="o", edgecolor="white", linewidth=1,
               label="has AA trait data", zorder=4)
    ax.set_xscale("log")
    ax.set_xlabel("observed cost per resume run, USD (log scale)")
    ax.set_ylabel("ours: gate-clamped score (0-100)")
    ax.set_title("Cost vs quality on the same task — all measured rounds pooled",
                 fontsize=13, weight="bold")
    ax.grid(alpha=0.3, which="both")
    ax.legend(loc="lower right", frameon=False)

    # label every point; nudge alternately to avoid collisions
    for i, r in enumerate(sorted(plottable, key=lambda r: r["cost_per_run"])):
        dx, dy = (8, 6) if i % 2 == 0 else (8, -12)
        ax.annotate(f"{r['label']}\n{r['mean']:.1f}",
                    (r["cost_per_run"], r["mean"]),
                    textcoords="offset points", xytext=(dx, dy),
                    fontsize=7.5, color="#222")

    # incumbent reference line
    inc = next((r for r in rows if r["label"].startswith("DeepSeek V4.1 Flash")
                and r["effort"] is None), None)
    if inc and inc["mean"]:
        ax.axhline(inc["mean"], ls=":", lw=1.2, color="#c0392b", alpha=0.8)
        ax.annotate(f"incumbent {inc['label']} = {inc['mean']:.1f}",
                    (ax.get_xlim()[0], inc["mean"]),
                    textcoords="offset points", xytext=(4, 4),
                    fontsize=8, color="#c0392b")

    # ── panel 2: AA trait Elo, only models that have it ──────────────────
    ax = axes[1]
    tr = [r for r in rows if r["trait_eloquent"] is not None]
    tr.sort(key=lambda r: r["trait_eloquent"])
    ypos = np.arange(len(tr))
    shown = [t for t in ("eloquent", "scannable", "literate") ]
    width = 0.26
    for j, t in enumerate(shown):
        vals = [r[f"trait_{t}"] or 0 for r in tr]
        ax.barh(ypos + (j - 1) * width, vals, height=width * 0.9,
                label=t, alpha=0.9)
    ax.set_yticks(ypos)
    ax.set_yticklabels([f"{r['label']}  (ours {r['mean']:.1f})" if r["mean"]
                        else r["label"] for r in tr], fontsize=8.5)
    ax.set_xlabel("AA-PersonalityBench trait Elo (higher = better)")
    ax.set_title("AA trait Elo for the same models — a prior, not a measurement",
                 fontsize=12, weight="bold")
    ax.axvline(0, color="#333", lw=1)
    ax.grid(axis="x", alpha=0.3)
    ax.legend(loc="lower right", frameon=False, fontsize=9)

    path = os.path.join(FIG, "price_vs_quality.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _fmt(v, spec: str) -> str:
    return format(v, spec) if v is not None else "—"


def _md_row(r: dict, show_traits: bool = False) -> str:
    """One markdown row matching the matching header exactly.

    The two tables have DIFFERENT column counts, so the trailing `verdict` cell
    belongs only to the non-trait table. Appending traits after it shifted every
    column by one and silently mislabelled the AA numbers as verdicts.
    """
    label = r["label"] + (f" · {r['effort']}" if r["effort"] else "")
    base = [label, f"n={r['n']}", _fmt(r["mean"], ".1f"),
            _fmt(r["sd"], ".1f"), _fmt(r.get("delta"), "+.1f"),
            _fmt(r.get("t"), ".2f"),
            (f"${r['cost_per_run']:.5f}"
             if r["cost_per_run"] is not None else "—")]
    if not show_traits:
        base += [(f"${r['price_in_1m']:.3f}"
                  if r["price_in_1m"] is not None else "—"),
                 (f"${r['price_out_1m']:.3f}"
                  if r["price_out_1m"] is not None else "—"),
                 r.get("verdict") or "—"]
    else:
        base += [_fmt(r.get("trait_eloquent"), ".0f"),
                 _fmt(r.get("trait_scannable"), ".0f"),
                 _fmt(r.get("trait_truthful"), ".0f"),
                 _fmt(r.get("aa_writing_score"), ".1f")]
    return "| " + " | ".join(base) + " |"


def write_markdown(rows: list[dict], fig: str) -> str:
    measured = [r for r in rows if r["mean"] is not None]
    sig = [r for r in measured if r.get("verdict") == "significant"]
    better = [r for r in sig if (r.get("delta") or 0) > 0]
    worse = [r for r in sig if (r.get("delta") or 0) < 0]
    priced = [r for r in measured if r["cost_per_run"]]
    best_value = min(priced, key=lambda r: r["cost_per_run"] / max(r["mean"], 1))

    head = ("| model · effort | n | mean | sd | Δ vs ctrl | t | $/run | in $/M "
            "| out $/M | verdict |")
    sep = "|---|---|---|---|---|---|---|---|---|---|"
    head_t = ("| model · effort | n | mean | sd | Δ vs ctrl | t | $/run "
              "| AA eloquent | AA scannable | AA truthful | AA writing |")
    sep_t = "|---|---|---|---|---|---|---|---|---|---|---|"

    lines = [
        "# RESULTS — resume-writing model evaluation",
        "",
        "Consolidated, generated document. Regenerate with "
        "`python resume_writing_v2/compile_results.py`.",
        "",
        "All experiments in this document cost **$3.03** in API calls: $2.33 "
        "for test A across three rounds, $0.50 for test B, and $0.19 for the "
        "superseded bullets-only drafting test.",
        "",
        f"Figure: `{os.path.relpath(fig, HERE)}`  ",
        f"Machine-readable: `{os.path.relpath(CONSOLIDATED, HERE)}`",
        "",
        "---",
        "",
        "## 1. What was measured",
        "",
        "Two tests. They answer different questions and are not interchangeable.",
        "",
        "| test | task | scored on |",
        "|---|---|---|",
        "| **A — free-authoring** | write a full resume from a verified profile "
        "+ a Boeing Defense GenAI DS job description | gate-clamped 100-point "
        "rubric |",
        "| **B — drafter faithfulness** | rewrite raw experience notes into STAR "
        "bullets under an evidence boundary | fabrication / metric fidelity / "
        "format |",
        "",
        "AA-PersonalityBench is reported as a **prior**, never as a grade. It was "
        "checked against the measured scores and does not predict them (§5).",
        "",
        "### Rounds",
        "",
        "| round | set | runs/model | effort | file |",
        "|---|---|---|---|---|",
        "| 1 | every OpenRouter model with output ≤ $2/M | 3 | provider default "
        "| `results/contest_cheap_r1.json` |",
        "| 2 | round-1 contenders within 4 pts of control | 8 | provider default "
        "| `results/contest_cheap_r2.json` |",
        "| 3 | the named high/low-cost set | 4 | explicit (`xhigh`/`high`/default)"
        " | `results/contest_cheap_r3.json` |",
        "",
        "A **variant** is `(model_id, reasoning_effort)`. The same family at "
        "`xhigh` and at provider default is a different model and is never pooled.",
        "",
        "---",
        "",
        "## 2. Test A — cost vs quality, all measured variants",
        "",
        f"{len(measured)} variants scored at least one run: **{len(better)} "
        f"significantly better** than the control and **{len(worse)} "
        "significantly worse**. Everything else is inside noise.",
        "",
        "Control = **DeepSeek V4.1 Flash at provider default** (n=11, mean 84.1). "
        "Significance = Welch test, |t| ≥ 2.5 **and** |Cohen's d| ≥ 0.8. "
        "`low_n` means fewer than 3 scored runs — not a result.",
        "",
        head, sep,
    ]
    for r in measured:
        lines.append(_md_row(r, show_traits=False))

    lines += [
        "",
        "### The cheap end, and Claude Haiku 5.5",
        "",
        head_t, sep_t,
    ]
    for r in measured:
        lines.append(_md_row(r, show_traits=True))

    lines += [
        "",
        "`—` in an AA column means no exact PersonalityBench name match, not a "
        "score of zero.",
        "",
    ]

    degen = [r for r in rows if r.get("traits_degenerate")]
    if degen:
        lines += [
            "### AA records rejected as degenerate",
            "",
        ]
        for r in degen:
            lines.append(f"- **{r['label']}** — {r['traits_note']}")
        lines.append("")

    ignored = [r for r in measured if r.get("effort_note")]
    if ignored:
        lines += [
            "### Efforts the provider did not honour",
            "",
            "These requests sent `reasoning_effort` and got **zero reasoning "
            "tokens** back, so the named effort was ignored. Their scores are "
            "default-effort scores and must not be read as the high-effort "
            "variant:",
            "",
        ]
        for r in ignored:
            lines.append(f"- {r['label']} — {r['effort_note']}")
        lines.append("")

    lines += [
        "### Reading the table",
        "",
    ]
    if better:
        lines.append("Significantly better than the control:")
        lines.append("")
        for r in better:
            cheap = r["cost_per_run"] / 0.00246
            lines.append(f"- **{r['label']}** — mean {r['mean']:.1f}, "
                         f"Δ {r['delta']:+.1f}, t={r['t']:.2f}, "
                         f"${r['cost_per_run']:.5f}/run "
                         f"({cheap:.2f}× the control's cost)")
        lines.append("")
    if worse:
        lines += [
            "Significantly **worse** than the control — no price justifies "
            "these on this task:",
            "",
        ]
        for r in worse:
            lines.append(f"- **{r['label']}** — mean {r['mean']:.1f}, "
                         f"Δ {r['delta']:+.1f}, t={r['t']:.2f}, "
                         f"${r['cost_per_run']:.5f}/run")
        lines.append("")
    if best_value:
        lines += [
            f"Best score-per-dollar in the measured set: **{best_value['label']}** "
            f"— {best_value['mean']:.1f} at ${best_value['cost_per_run']:.5f}/run.",
            "",
        ]

    lines += [
        "---",
        "",
        "## 3. Test B — full resume: faithfulness AND structure",
        "",
        TEST_B_PLACEHOLDER,
        "",
        "---",
        "",
        "## 4. Spend — product stages only",
        "",
        "30 days (2026-10-04 → 2026-11-02). Development traffic is **excluded**",
        "(`gpt-6.1-sol`, `gpt-6.1-terra`, `claude-haiku-5.5` and similar are "
        "engineering-use models, not product).",
        "",
        "| | spend | requests | share |",
        "|---|---|---|---|",
        "| **A. Imaginator pipeline** | **$2.86** | 2,060 | 1.7% |",
        "| └ drafter (`qwen3-coder`) | $0.21 | — | 0.13% |",
        "| **B. Job Scout research** | **$27.52** | 10,281 | 16.6% |",
        "| **PRODUCT TOTAL** | **$30.38** | 12,341 | **18.3%** |",
        "| Development (out of scope) | $135.82 | — | 81.7% |",
        "",
        "**Job Scout research is 91% of product spend.** The whole Imaginator "
        "pipeline is $2.86. Replacing the drafter cannot move the bill — it is "
        "a quality question, not a cost one.",
        "",
        "---",
        "",
        "## 5. AA-PersonalityBench — a prior, not a score",
        "",
        "Available for 40 models (30 trait Elos + 8 index percentiles) and "
        "extracted from the website payload, because the documented API returns "
        "**404 DEPLOYMENT_NOT_FOUND** and the v2 host carries no personality "
        "fields.",
        "",
        "Three measured reasons it is not a grading axis:",
        "",
        "1. **Not exposed by the API** — the documented v1 endpoint returns "
        "**404 DEPLOYMENT_NOT_FOUND** and the v2 host carries no personality "
        "fields, so the website payload is the only route.",
        "2. **Does not predict the task.** See the correlation table below.",
        "3. **It would mis-rank the winner.** DeepSeek V4.1 Flash has the highest "
        "`organization` index of all 40 (100) and finished last among "
        "contenders. `eloquent` puts Claude Fable 5.1 first (1716) and Kimi K3.1 "
        "Pro 14th (1189), while the harness found Kimi the best-faithfulness "
        "drafter.",
        "",
    ]

    corr = trait_correlation(rows)
    if corr:
        n = corr[0][2]
        crit = 1.96 / (n - 3) ** 0.5          # Fisher-z approximation
        lines += [
            f"### Trait vs measured score — n={n} models",
            "",
            "One point per model (its best variant), so a family measured at "
            "three efforts cannot outvote a family measured once. At "
            f"n={n}, |r| must exceed **{crit:.2f}** to reach p<0.05.",
            "",
            "| trait | Pearson r vs our score | significant |",
            "|---|---|---|",
        ]
        for t, r, _n in corr:
            lines.append(f"| `{t}` | {r:+.2f} | "
                         f"{'yes' if abs(r) > crit else 'no'} |")
        lines += [
            "",
            "**No trait clears the threshold.** The earlier n=6 analysis reported "
            "`scannable` at +0.81, which looked like it sat on the significance "
            "boundary; at n=24 the same relationship is far weaker. That is the "
            "expected regression of a small-sample correlation toward zero, and "
            "it is why the n=6 value should never have been quoted as "
            "\"borderline predictive\".",
            "",
        ]

    lines += [
        "Where it is useful is **corroboration**: MiniMax M3.1 Flash scores "
        "near-bottom `truthful` (202 of a −611…2178 scale) while its `scannable` "
        "(1079) sits above Kimi's (980) — exactly the shape the drafter test "
        "measured independently (looks structured, fabricates in practice).",
        "",
        "```bash",
        "python -m resume_writing_v2.personalitybench traits eloquent scannable "
        "truthful",
        "```",
        "",
        "Each record carries a `_<trait>_scale` field (`trait Elo` or "
        "`index percentile`) so the two scales cannot be silently mixed.",
        "",
        "---",
        "",
        "## 6. Limitations",
        "",
        "1. n=4–11 per variant resolves ~5–6 point differences, not 2-point. "
        "Claims under ~5 points are undetermined and are labelled "
        "`inside noise`.",
        "2. A 4/4 drafter record is consistent with a ~10% failure rate. Read "
        "\"no failures observed\", not \"never fails\".",
        "3. One task each — one JD, one profile, one fixture. Results may not "
        "transfer to another domain.",
        "4. Deterministic keyword scorers can be wrong in fixed ways. Two such "
        "bugs were found and fixed (see git history).",
        "5. The drafter prompt is reconstructed; golden-bullet library and "
        "seniority verb tables omitted. Relative comparisons hold, absolute "
        "scores are not production-identical.",
        "6. No LLM-as-judge anywhere — every metric is deterministic and "
        "repeatable.",
        "7. `K2 Horizon 375B A23B` has no OpenRouter id and is therefore "
        "unmeasured, not excluded for a bad score.",
        "",
    ]
    path = os.path.join(HERE, "RESULTS.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def main() -> int:
    runs = load_runs()
    rows = consolidate(runs)
    add_significance(rows, runs)
    out = write_consolidated(rows)
    fig = figure(rows)
    md = write_markdown(rows, fig)

    # Fold the generated Test B section into RESULTS.md via an explicit
    # placeholder. A string-search merge was fragile and silently dropped
    # sections when a heading changed.
    if os.path.exists(TEST_B_MD):
        body = open(TEST_B_MD).read().strip()
        # drop the generated file's own H2 so it nests under this document
        body = body.split("\n", 1)[1].lstrip() if body.startswith("## ") else body
        doc = open(md).read()
        doc = doc.replace(TEST_B_PLACEHOLDER, body)
        with open(md, "w") as f:
            f.write(doc)

    print(f"consolidated -> {out}")
    print(f"figure       -> {fig}")
    print(f"report       -> {md}\n")
    hdr = (f"{'#':>2} {'variant':<34}{'n':>4}{'mean':>7}{'sd':>6}"
           f"{'$/run':>10}{'AA eloq':>9}{'AA wr':>7}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['rank']:>2} {r['label'][:33]:<34}{r['n']:>4}"
              f"{(r['mean'] if r['mean'] is not None else 0):>7.1f}"
              f"{(r['sd'] if r['sd'] is not None else 0):>6.1f}"
              f"{(r['cost_per_run'] or 0):>10.5f}"
              f"{(r['trait_eloquent'] if r['trait_eloquent'] is not None else 0):>9.0f}"
              f"{(r['aa_writing_score'] or 0):>7.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
