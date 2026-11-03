#!/usr/bin/env python3
"""Visualise the resume-writing comparison — both contests.

Two separate questions, two separate figures, because they measure different
things and conflating them would repeat the mistake this work exists to avoid:

  FIGURE 1  DRAFTER FAITHFULNESS
    The Imaginator drafter's actual job: rewrite raw notes into STAR bullets
    without inventing anything. Scored on fabrication, metric fidelity, JSON
    schema, bullet-length band, strong-verb starts, company coverage.
    Prose beauty is deliberately NOT plotted: a fluent fabricator is worse than
    a plain faithful writer.

  FIGURE 2  FREE-AUTHORING QUALITY
    The earlier contest: full resume written from a profile, graded on the
    gate-clamped 100-point rubric, with significance verdicts.

Colour encodes the verdict, not the rank, so a high bar with a red label reads
as "high score, but not trustworthy" instead of looking like a win.
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

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
DRAFTER = os.path.join(RES, "drafter_faithfulness.json")
R1 = os.path.join(RES, "contest_cheap_r1.json")
R2 = os.path.join(RES, "contest_cheap_r2.json")
OUTDIR = os.path.join(HERE, "figures")

plt.rcParams["text.parse_math"] = False      # '$' in labels is currency, not TeX


def _fig1() -> str | None:
    if not os.path.exists(DRAFTER):
        print("figure 1 skipped: no drafter results")
        return None
    data = json.load(open(DRAFTER))["results"]
    by: dict[str, list[dict]] = {}
    for r in data:
        by.setdefault(r["label"], []).append(r)

    labs, clean_pct, fab, badnum, band, strong = [], [], [], [], [], []
    for lab, rs in by.items():
        ok = [r for r in rs if r.get("ok")]
        if not ok:
            continue
        labs.append(lab)
        clean_pct.append(sum(1 for r in ok if r["clean"]) / len(ok) * 100)
        fab.append(st.mean([len(r["fabricated_tech"]) + len(r["fabricated_company"])
                            for r in ok]))
        badnum.append(st.mean([len(r["bad_numbers"]) + len(r["unit_stripped"])
                               for r in ok]))
        band.append(st.mean([r["in_band_pct"] for r in ok]))
        strong.append(st.mean([r["strong_start_pct"] for r in ok]))

    order = np.argsort(clean_pct)
    labs = [labs[i] for i in order]
    clean_pct = [clean_pct[i] for i in order]
    fab = [fab[i] for i in order]
    badnum = [badnum[i] for i in order]
    band = [band[i] for i in order]
    strong = [strong[i] for i in order]

    fig, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)

    # (1) clean-run rate — the criterion that decides viability
    ax = axes[0, 0]
    cols = ["#2e7d32" if c >= 80 else "#f9a825" if c >= 40 else "#c0392b"
            for c in clean_pct]
    bars = ax.barh(labs, clean_pct, color=cols, edgecolor="black", linewidth=0.5)
    for b, v in zip(bars, clean_pct):
        ax.text(v + 2, b.get_y() + b.get_height() / 2, f"{v:.0f}%",
                va="center", fontsize=9, fontweight="bold")
    ax.set_xlim(0, 118)
    ax.set_xlabel("% of runs with ZERO fabrication and clean metrics")
    ax.set_title("1. Clean-run rate — the viability gate\n"
                 "(green >=80%, amber >=40%, red below)", fontsize=11)
    ax.grid(axis="x", alpha=0.3)

    # (2) fabrication count — lower is better
    ax = axes[0, 1]
    bars = ax.barh(labs, fab, color="#c0392b", edgecolor="black", linewidth=0.5)
    for b, v in zip(bars, fab):
        ax.text(v + 0.1, b.get_y() + b.get_height() / 2, f"{v:.1f}",
                va="center", fontsize=9)
    ax.set_xlabel("mean invented techs/companies per run  (0 = never invents)")
    ax.set_title("2. Fabrication — the auto-fail condition", fontsize=11)
    ax.grid(axis="x", alpha=0.3)

    # (3) format compliance
    ax = axes[1, 0]
    y = np.arange(len(labs))
    ax.barh(y + 0.2, band, height=0.4, label="bullets in 15-25 word band",
            color="#2f7ed8", edgecolor="black", linewidth=0.4)
    ax.barh(y - 0.2, strong, height=0.4, label="starts with strong verb",
            color="#e8833a", edgecolor="black", linewidth=0.4)
    ax.set_yticks(y)
    ax.set_yticklabels(labs)
    ax.set_xlim(0, 118)
    ax.set_xlabel("% of bullets")
    ax.set_title("3. Format compliance — the drafter spec", fontsize=11)
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(axis="x", alpha=0.3)

    # (4) metric fidelity
    ax = axes[1, 1]
    bars = ax.barh(labs, badnum, color="#8e44ad", edgecolor="black", linewidth=0.5)
    for b, v in zip(bars, badnum):
        ax.text(v + 0.05, b.get_y() + b.get_height() / 2, f"{v:.2f}",
                va="center", fontsize=9)
    ax.set_xlabel("mean unverified numbers / stripped units per run")
    ax.set_title("4. Metric fidelity — inventing or de-uniting a number", fontsize=11)
    ax.grid(axis="x", alpha=0.3)

    best = labs[int(np.argmax(clean_pct))]
    fig.suptitle(
        "Imaginator DRAFTER faithfulness — incumbent qwen3-coder vs heavyweight candidates\n"
        f"Higher clean-rate is better; lower fabrication/metric error is better. "
        f"Best clean-rate: {best}",
        fontsize=13, fontweight="bold")
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, "drafter_faithfulness.png")
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {path}")
    return path


def _fig2() -> str | None:
    if not (os.path.exists(R1) and os.path.exists(R2)):
        print("figure 2 skipped: contest results missing")
        return None

    def collect(p):
        out: dict[str, list[float]] = {}
        for r in json.load(open(p))["results"]:
            if r.get("ok") and r.get("score") is not None:
                out.setdefault(r["label"], []).append(r["score"])
        return out

    a, b = collect(R1), collect(R2)
    comb: dict[str, list[float]] = {}
    for src in (a, b):
        for k, v in src.items():
            comb.setdefault(k, []).extend(v)

    inc = next(k for k in comb if "incumbent" in k.lower())
    base = comb[inc]

    def welch(x, y):
        import math
        vx, vy = st.variance(x), st.variance(y)
        den = math.sqrt(vx / len(x) + vy / len(y))
        if den == 0:
            return 0.0
        t = (st.mean(x) - st.mean(y)) / den
        return t

    rows = []
    for k, v in comb.items():
        if k == inc or len(v) < 4:
            continue
        rows.append((st.mean(v), k, len(v), welch(v, base)))
    rows.sort(reverse=True)

    labs = [inc] + [r[1] for r in rows]
    means = [st.mean(base)] + [r[0] for r in rows]
    ns = [len(base)] + [r[2] for r in rows]
    ts = [0.0] + [r[3] for r in rows]
    colours = ["#555555"] + ["#2e7d32" if abs(t) >= 2.5 else "#9aa5b1"
                              for t in ts[1:]]

    fig, axes = plt.subplots(1, 2, figsize=(17, 8), constrained_layout=True)

    # (1) mean score with significance colouring
    ax = axes[0]
    y = np.arange(len(labs))[::-1]
    ax.barh(y, means, color=colours, edgecolor="black", linewidth=0.5)
    ax.axvline(st.mean(base), color="#c0392b", ls="--", lw=1.6,
               label=f"incumbent mean {st.mean(base):.1f}")
    for yy, m, t, n in zip(y, means, ts, ns):
        tag = "" if t == 0 else ("  SIGNIF" if abs(t) >= 2.5 else "  (noise)")
        ax.text(m + 0.5, yy, f"{m:.1f} (n={n}){tag}", va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels([l[:34] for l in labs], fontsize=8)
    ax.set_xlim(0, max(means) * 1.35)
    ax.set_xlabel("mean writing score (gate-clamped rubric, 0-100)")
    ax.set_title("Free-authoring contest — green = significantly different from\n"
                 "incumbent (|t| >= 2.5), grey = inside repeat noise", fontsize=11)
    ax.legend(fontsize=9, loc="lower right")
    ax.grid(axis="x", alpha=0.3)

    # (2) distribution, so the noise is visible next to the means
    ax = axes[1]
    data = [comb[l] for l in labs]
    bp = ax.boxplot(data, vert=False, labels=[l[:30] for l in labs],
                    patch_artist=True, widths=0.6)
    for i, patch in enumerate(bp["boxes"]):
        patch.set_facecolor(colours[i] if i < len(colours) else "#9aa5b1")
        patch.set_alpha(0.75)
    ax.axvline(st.mean(base), color="#c0392b", ls="--", lw=1.4)
    ax.set_xlabel("individual run scores — overlap IS the noise")
    ax.set_title("Run-to-run spread per model\n"
                 "(wide boxes mean the model is unreliable, not good)", fontsize=11)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(axis="x", alpha=0.3)

    fig.suptitle("Resume-writing contest — quality vs the DeepSeek V4.1 Flash incumbent",
                 fontsize=13, fontweight="bold")
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, "free_authoring_contest.png")
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {path}")
    return path


if __name__ == "__main__":
    p1 = _fig1()
    p2 = _fig2()
    print("\ndone:", p1, p2)
