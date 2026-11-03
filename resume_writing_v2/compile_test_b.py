#!/usr/bin/env python3
"""Analyse Test B (full-resume) and write the figure + RESULTS section.

Reports per variant, in this order of importance:

  1. PASS RATE — both contracts satisfied (faithful AND structurally correct).
     This is the only number worth ranking on.
  2. FAITHFULNESS — invented tech / company / number / stripped unit.
  3. STRUCTURE — sections, chronology, employment dates, education years,
     certification dates, formatting.

The two are reported separately because they fail independently: a resume can
be factually perfect and chronologically wrong, and the fix is different.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
OUT = os.path.join(RES, "drafter_fullresume.json")
FIG = os.path.join(HERE, "figures")
CONSOLIDATED = os.path.join(RES, "consolidated.json")

plt.rcParams["text.parse_math"] = False

def _budget(row: dict) -> tuple[int, str]:
    """(max_tokens sent, note). Mirrors round_b_fullresume.MAX_TOK_CAP."""
    if row.get("model_id") == "openai/gpt-3.5-turbo-0613":
        return 1200, "small-context model"
    return 8192, "standard"


CHECKS = [
    ("fabricated_tech", "invented technology"),
    ("fabricated_company", "invented company"),
    ("bad_numbers", "unverified number"),
    ("unit_stripped", "unit stripped"),
]


def aggregate(rows: list[dict]) -> list[dict]:
    by: dict[tuple, list[dict]] = {}
    for r in rows:
        if not r.get("ok") or not r.get("faith"):
            continue
        by.setdefault((r["model_id"], r.get("effort")), []).append(r)

    means = {(r["model_id"], r["effort"]): r
             for r in json.load(open(CONSOLIDATED))["rows"]}
    out = []
    for key, rs in by.items():
        n = len(rs)
        faith_clean = sum(1 for r in rs if r["faith"]["clean"])
        struct_clean = sum(1 for r in rs if r["struct"]["structural_clean"])
        passed = sum(1 for r in rs if r.get("pass"))
        rec = {
            "model_id": key[0], "effort": key[1],
            "label": rs[0]["label"],
            "n": n,
            "pass_rate": round(passed / n * 100, 0),
            "faith_clean": faith_clean,
            "struct_clean": struct_clean,
            "cost_per_run": round(
                sum((r.get("cost_usd") or 0) for r in rs) / n, 6),
            "test_a": (means.get(key) or {}).get("mean"),
            # A run that consumed its whole max_tokens budget was cut off. That
            # is a distinct failure from a wrong date: the model never finished.
            # 98% of budget, not 100%: a run that stops at 8188 of 8192 was cut
            # off just as surely as one that reaches 8192.
            "truncated_runs": sum(
                1 for r in rs
                if (r.get("completion_tokens") or 0) >= 0.98 * _budget(r)[0]),
            "bullet_band_pct": round(
                sum(r["faith"]["in_band_pct"] for r in rs) / n, 0),
            "one_per_line_pct": round(
                sum(1 for r in rs if r["faith"]["one_thought_per_line"])
                / n * 100, 0),
            "styles": sorted({r["faith"]["bullet_style"] for r in rs}),
            "failures": {},
        }
        for fk, label in CHECKS:
            rec["failures"][label] = sum(
                1 for r in rs if r["faith"].get(fk))
        rec["failures"]["missing section"] = sum(
            1 for r in rs if r["struct"]["missing_sections"])
        rec["failures"]["wrong chronology"] = sum(
            1 for r in rs if r["struct"]["order_ok"] is False)
        rec["failures"]["wrong employment dates"] = sum(
            1 for r in rs if not r["struct"]["dates_ok"])
        rec["failures"]["wrong education years"] = sum(
            1 for r in rs if not r["struct"]["education_ok"])
        rec["failures"]["wrong cert dates"] = sum(
            1 for r in rs if not r["struct"]["certs_ok"])
        rec["failures"]["bad formatting"] = sum(
            1 for r in rs if not r["struct"]["formatting_ok"])
        out.append(rec)

    out.sort(key=lambda r: (-r["pass_rate"], -(r["test_a"] or 0)))
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def figure(agg: list[dict]) -> str:
    os.makedirs(FIG, exist_ok=True)
    shown = [r for r in agg if r["n"] >= 2]
    shown = sorted(shown, key=lambda r: r["pass_rate"])

    fig, axes = plt.subplots(1, 2, figsize=(15, max(6, len(shown) * 0.32)),
                             constrained_layout=True,
                             gridspec_kw={"width_ratios": [1.15, 1]})
    y = np.arange(len(shown))

    ax = axes[0]
    pr = [r["pass_rate"] for r in shown]
    cols = ["#2e7d32" if p >= 100 else "#f9a825" if p >= 50 else "#c0392b"
            for p in pr]
    ax.barh(y, pr, color=cols, height=0.72)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{r['label']}"
                        + (f" · {r['effort']}" if r["effort"] else "")
                        + f"  (n={r['n']})" for r in shown], fontsize=8)
    ax.set_xlim(0, 105)
    ax.set_xlabel("% of runs satisfying BOTH faithfulness and structure")
    ax.set_title("Test B — full-resume pass rate\n"
                 "(faithful AND structurally correct)", fontsize=12,
                 weight="bold")
    ax.grid(axis="x", alpha=0.3)
    for i, r in enumerate(shown):
        ax.annotate(f" {r['pass_rate']:.0f}%", (r["pass_rate"], i),
                    va="center", fontsize=7.5)

    ax = axes[1]
    checks = ["invented technology", "unverified number", "missing section",
              "wrong chronology", "wrong employment dates",
              "wrong education years", "wrong cert dates"]
    mat = np.array([[r["failures"].get(c, 0) for c in checks] for r in shown],
                   dtype=float)
    im = ax.imshow(mat, aspect="auto", cmap="Reds", vmin=0,
                   vmax=max(1.0, mat.max()))
    ax.set_xticks(np.arange(len(checks)))
    ax.set_xticklabels(checks, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels([])
    ax.set_title("Which check failed, and how often\n"
                 "(cell = runs, out of n shown on the left)", fontsize=12,
                 weight="bold")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            if mat[i, j]:
                ax.text(j, i, int(mat[i, j]), ha="center", va="center",
                        fontsize=7,
                        color="white" if mat[i, j] > mat.max() * 0.6 else "#222")
    fig.colorbar(im, ax=ax, shrink=0.6, label="failed runs")

    path = os.path.join(FIG, "drafter_fullresume.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def write_markdown(agg: list[dict], meta: dict, fig: str) -> str:
    perfect = [r for r in agg if r["pass_rate"] == 100]
    partial = [r for r in agg if 0 < r["pass_rate"] < 100]
    zero = [r for r in agg if r["pass_rate"] == 0]

    L = [
        "## 3. Test B — full resume: faithfulness AND structure",
        "",
        "The task is the drafter's real job extended to a whole document: rewrite "
        "the source history into a complete resume with three required sections, "
        "reverse-chronological jobs, dates copied exactly, education years exact, "
        "certification dates exact, and ATS-parseable plain text.",
        "",
        "Two contracts are scored **separately** and both must hold to pass. They "
        "fail independently, and the fix differs:",
        "",
        "| contract | checks |",
        "|---|---|",
        "| **faithfulness** | no invented technology, no invented company, no "
        "unverified number, no unit stripped |",
        "| **structure** | required sections present, reverse-chronological "
        "order, employment dates exact, education years exact, cert dates exact, "
        "plain text (no markdown tables/fences) |",
        "",
        f"{len(agg)} variants, {sum(r['n'] for r in agg)} scored runs, "
        f"**${meta['spent_usd']:.2f}**. Figure: `figures/drafter_fullresume.png`.",
        "",
        f"**{len(perfect)} variants passed every run.** {len(partial)} passed "
        f"some, {len(zero)} passed none.",
        "",
        "### Ranking — pass rate over 3 runs",
        "",
        "| # | variant | n | pass | faith | struct | truncated | 15–25w band "
        "| $/run | Test A |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in agg:
        A = f"{r['test_a']:.1f}" if r["test_a"] is not None else "—"
        L.append(
            f"| {r['rank']} | {r['label']}"
            + (f" · {r['effort']}" if r["effort"] else "")
            + f" | {r['n']} | **{r['pass_rate']:.0f}%** "
            f"| {r['faith_clean']}/{r['n']} | {r['struct_clean']}/{r['n']} "
            f"| {r['truncated_runs']}/{r['n']} "
            f"| {r['bullet_band_pct']:.0f}% | ${r['cost_per_run']:.5f} | {A} |")
    L += [
        "",
        "`pass` = faithfulness-clean AND structurally-clean on the same run.",
        "`faith`/`struct` are counts of clean runs out of n.",
        "",
    ]

    if zero or partial:
        L += [
            "### Variants that did not hold the contract",
            "",
        ]
        for r in (zero + partial):
            worst = sorted(r["failures"].items(), key=lambda kv: -kv[1])
            worst = [f"{k} ({v}/{r['n']})" for k, v in worst if v]
            L.append(f"- **{r['label']}** — {r['pass_rate']:.0f}% pass. "
                     + (", ".join(worst) if worst else "no failure recorded"))
        L.append("")

    L += [
        "### What this says",
        "",
        "1. **The full-resume structure is not hard when it is specified.** Most "
        "variants copied every date and year exactly. That is a genuine finding, "
        "and it means the *earlier* bullets-only task was the harder one — it "
        "asked for JSON and a word band with no document structure to lean on.",
        "",
        "2. **The word band is the real differentiator.** Several models passed "
        "structure perfectly and failed the 15–25 word band almost totally "
        "(see the band column: 0%, 4%, 7%). Structure and prose discipline are "
        "unrelated skills.",
        "",
        "3. **A reasoning leak is a hard failure.** One variant emitted its "
        "internal word-count deliberation instead of a resume — no sections, no "
        "dates, no bullets. It is scored as a total failure, correctly: reasoning "
        "text in a user-facing field is a production incident.",
        "",
        "4. **Test A score does not predict Test B.** The seed of the ranking is "
        "similar because both reward competence, but failures here cut across "
        "price: cheap models pass, and one expensive model failed outright.",
        "",
        "### Excluded by request",
        "",
        "Five variants were skipped because Test A found them significantly "
        "**worse** than the incumbent at a higher price per run — spending on "
        "them would not change any decision:",
        "",
        "| variant | Test A | $/run | Δ vs control |",
        "|---|---|---|---|",
        "| Claude Haiku 5.5 (high) | 73.8 | $0.00159 | −10.3 |",
        "| Kimi K3.1 Pro | 73.5 | $0.03803 | −10.6 |",
        "| Grok 4.7 (xhigh) | 72.0 | $0.16239 | −12.1 |",
        "| Grok 4.6 (xhigh) | 71.2 | $0.03602 | −12.8 |",
        "| GPT-6 Luna (xhigh) | 71.2 | $0.00394 | −12.9 |",
        "",
        "### Why this replaced the earlier bullets-only test",
        "",
        "The first Test B asked for JSON bullets only. It could not see a wrong "
        "graduation year, a reordered job history, or a missing section, because "
        "it never asked for them. It is superseded here, and its five-model "
        "result is kept in `results/drafter_faithfulness.json` as history, not "
        "as a current ranking.",
        "",
        "### Scorer integrity",
        "",
        "`python resume_writing_v2/test_scorers.py` asserts the scorers fire on "
        "known-bad input and stay quiet on known-good input. Six silent bugs "
        "were caught this way during this round, each of which would have "
        "produced a confidently wrong ranking:",
        "",
        "| bug | wrong conclusion it produced |",
        "|---|---|",
        "| plain-text resumes scored with the JSON scorer | all 43 variants "
        "failed faithfulness |",
        "| `04/2024` parsed as the numbers 4 and 2024 | correct dates flagged "
        "as fabricated metrics |",
        "| unmarked bullets not extracted | models that wrote 7 good bullets "
        "scored 0 |",
        "| education/cert lines counted as bullets | in-band compliance "
        "artificially 0% |",
        "| character window instead of line | adjacent credentials shared "
        "years, reported as invented |",
        "| dates searched only below the company | correct layouts marked "
        "failed |",
        "",
    ]
    return "\n".join(L)


def main() -> int:
    payload = json.load(open(OUT))
    rows = payload["results"]
    agg = aggregate(rows)
    fig = figure(agg)

    with open(os.path.join(RES, "drafter_fullresume_summary.json"), "w") as f:
        json.dump({"meta": payload["meta"], "variants": agg}, f, indent=1)

    md = write_markdown(agg, payload["meta"], fig)
    md_path = os.path.join(HERE, "RESULTS_TEST_B.md")
    with open(md_path, "w") as f:
        f.write(md)

    perfect = [r for r in agg if r["pass_rate"] == 100 and r["n"] >= 2]
    zero = [r for r in agg if r["pass_rate"] == 0]

    print(f"figure -> {fig}")
    print(f"variants {len(agg)} | runs {sum(r['n'] for r in agg)} | "
          f"spent ${payload['meta']['spent_usd']:.4f}")
    print(f"100% pass: {len(perfect)} variants | 0% pass: {len(zero)} variants\n")

    hdr = (f"{'#':>2} {'variant':<34}{'n':>3}{'pass':>6}{'faith':>7}"
           f"{'struct':>7}{'band%':>7}{'$/run':>10}{'testA':>7}")
    print(hdr)
    print("-" * len(hdr))
    for r in agg:
        print(f"{r['rank']:>2} {r['label'][:33]:<34}{r['n']:>3}"
              f"{r['pass_rate']:>5.0f}%{r['faith_clean']:>7}{r['struct_clean']:>7}"
              f"{r['bullet_band_pct']:>7.0f}"
              f"{r['cost_per_run']:>10.5f}"
              f"{(r['test_a'] or 0):>7.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
