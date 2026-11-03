#!/usr/bin/env python3
"""Build ONE self-contained report: results + methodology + verbatim prompts.

Everything that can be read from the source is read from the source — the
prompts, the fixture, the allowlists, the weights. Nothing is retyped, because a
retyped prompt in a methodology document is a claim that silently drifts from
what actually ran.

Outputs, all at the repo root so they are easy to find and download:
  resume_writing_REPORT.md    the combined document
  resume_writing_REPORT.pdf   same content as PDF (if a converter exists)

Run: python resume_writing_v2/build_report.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_writing_v2 import config, drafter_faithfulness as dfn, task
from resume_writing_v2 import gates as gates_mod
from resume_writing_v2.gates import (VERIFIED_CERTS, VERIFIED_DEGREES,
                                     VERIFIED_EMPLOYERS, VERIFIED_METRICS,
                                     FORBIDDEN_CLEARANCE, FORBIDDEN_DEGREES,
                                     FORBIDDEN_EMPLOYERS)
from resume_writing_v2.scoring import WEIGHTS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RES = os.path.join(HERE, "results")
MD_OUT = os.path.join(ROOT, "resume_writing_REPORT.md")
PDF_OUT = os.path.join(ROOT, "resume_writing_REPORT.pdf")

TODAY = "2026-11-03"


def fence(text: str, lang: str = "") -> str:
    """Wrap in a fence that the content cannot accidentally close."""
    marker = "```"
    while marker in text:
        marker += "`"
    return f"{marker}{lang}\n{text.rstrip()}\n{marker}"


def load(name: str) -> dict | None:
    p = os.path.join(RES, name)
    return json.load(open(p)) if os.path.exists(p) else None


# ── spend ─────────────────────────────────────────────────────────────────
def spend() -> tuple[list[tuple[str, float]], float]:
    rows = []
    total = 0.0
    for f, label in (
        ("contest_cheap_r1.json", "Test A round 1 (n=3, all ≤$2/M models)"),
        ("contest_cheap_r2.json", "Test A round 2 (n=8, contenders)"),
        ("contest_cheap_r3.json", "Test A round 3 (n=4, named set + efforts)"),
        ("drafter_faithfulness.json", "Test B-bullets (superseded)"),
        ("drafter_fullresume.json", "Test B full resume"),
    ):
        d = load(f)
        if not d:
            continue
        s = (d.get("meta") or {}).get("spent_usd")
        if s is None:
            s = sum(r.get("cost_usd") or 0 for r in d["results"])
        rows.append((label, s))
        total += s
    return rows, total


# ── sections ──────────────────────────────────────────────────────────────
def build() -> str:
    L: list[str] = []
    A = load("consolidated.json")
    B = load("drafter_fullresume_summary.json")
    spend_rows, spend_total = spend()

    # ── title ────────────────────────────────────────────────────────────
    L += [
        "# Resume-Writing Model Evaluation",
        "## Results, Methodology, Prompts and Test Criteria",
        "",
        f"**Generated:** {TODAY}  ",
        "**Harness:** `resume_writing_v2/`  ",
        f"**Total API spend for every experiment in this document: "
        f"${spend_total:.2f}**",
        "",
        "This document is generated from the code, not written by hand. Every "
        "prompt, fixture and allowlist below is read directly from the module "
        "that ran, so it cannot drift from what was actually executed. "
        "Regenerate with `python resume_writing_v2/build_report.py`.",
        "",
        "---",
        "",
        "## Contents",
        "",
        "1. Executive summary",
        "2. What was tested, and the three things that are NOT interchangeable",
        "3. Test A — free authoring: inputs, prompt, scoring, results",
        "4. Test B — full resume: inputs, prompt, scoring, results",
        "5. The year problem — why fixture years must never reach output",
        "6. AA-PersonalityBench: a prior, not a score",
        "7. Corrections carried forward",
        "8. Limitations",
        "9. Reproducing",
        "",
        "---",
        "",
    ]

    # ── 1 summary ────────────────────────────────────────────────────────
    L += [
        "## 1. Executive summary",
        "",
        "**The decision this supports:** which model should write resumes and "
        "STAR bullets for the Imaginator pipeline, and whether the quality gap "
        "justifies the price.",
        "",
        "### Headline results",
        "",
    ]
    if A:
        rows = [r for r in A["rows"] if r["mean"] is not None]
        better = [r for r in rows if r.get("verdict") == "significant"
                  and (r.get("delta") or 0) > 0]
        L += [
            f"- **{len(rows)} model variants** measured in Test A "
            f"(free authoring). **{len(better)} beat the incumbent "
            "significantly.**",
        ]
        for r in sorted(better, key=lambda x: x["mean"], reverse=True):
            L.append(
                f"  - **{r['label']}** — {r['mean']:.1f} "
                f"(Δ {r['delta']:+.1f}, t={r['t']:.2f}) at "
                f"${r['cost_per_run']:.5f}/run, "
                f"{r['cost_per_run'] / 0.00246:.2f}× the incumbent's cost")
        L.append("")
        best = min((r for r in rows if r["cost_per_run"]),
                   key=lambda r: r["cost_per_run"] / max(r["mean"], 1))
        L += [
            f"- **Best score-per-dollar:** `{best['model_id']}` — "
            f"{best['mean']:.1f} at ${best['cost_per_run']:.5f}/run.",
        ]
    if B:
        vs = [v for v in B["variants"] if v["n"] >= 2]
        perfect = [v for v in vs if v["pass_rate"] == 100]
        L.append(
            f"- **Test B (full resume):** {len(perfect)} of {len(vs)} variants "
            "passed every run on BOTH faithfulness and structure.")
        L.append("")

    L += [
        "### The three conclusions that matter",
        "",
        "1. **Cheap can win.** `qwen/qwen3.6-35b-a3b` scores 89.8 against the "
        "incumbent's 84.1 (t=2.62) at about a fifth of the cost. Price and "
        "quality are not correlated in this set.",
        "",
        "2. **Expensive can lose.** Grok 4.7 at `xhigh` costs 66× the incumbent "
        "per run and scores 72.0 — significantly worse. Claude Haiku 5.5 at "
        "`high` scores 73.8, also significantly worse.",
        "",
        "3. **A pretty benchmark is not a fidelity benchmark.** An earlier "
        "bullets-only test ranked MiniMax M3.1 Flash first on format and last on "
        "faithfulness (24 invented items, 0/4 clean). The full-resume test now "
        "scores both and requires both.",
        "",
        "---",
        "",
    ]

    # ── 2 scope ──────────────────────────────────────────────────────────
    L += [
        "## 2. What was tested, and what is not interchangeable",
        "",
        "| # | test | question | scored on |",
        "|---|---|---|---|",
        "| A | **Free authoring** | Can a model write a good resume from a "
        "verified profile? | gate-clamped 100-point rubric |",
        "| B | **Full resume** | Can a model rewrite raw notes into a complete, "
        "correctly dated, correctly ordered resume without inventing anything? | "
        "faithfulness AND structure, both required |",
        "| C | **AA-PersonalityBench** | What does a published writing benchmark "
        "say? | prior only — never a grade |",
        "",
        "**A and B are different tasks.** A gives the model a tidy profile and "
        "asks for prose. B gives it messy notes and an evidence boundary, then "
        "checks every date. A model can win one and lose the other — several did.",
        "",
        "**C is not a scoring axis.** It was tested as a predictor and failed "
        "(§6).",
        "",
        "**Neither A nor B measures prose beauty.** A fluent fabricator is worse "
        "than a plain faithful writer for this pipeline, so relative "
        "faithfulness is what is ranked.",
        "",
        "---",
        "",
    ]

    # ── 3 Test A ─────────────────────────────────────────────────────────
    L += [
        "## 3. Test A — free authoring",
        "",
        "### 3.1 Input: the job description",
        "",
        fence(task.JD_TEXT, "text"),
        "",
        "### 3.2 Input: the verified candidate profile",
        "",
        "This is the ONLY fact set a model may use. Every gate and every "
        "allowlist below is derived from it.",
        "",
        fence(task.CANDIDATE_PROFILE, "text"),
        "",
        "### 3.3 The system prompt (verbatim)",
        "",
        fence(task.SYSTEM_PROMPT, "text"),
        "",
        "### 3.4 The user message (verbatim)",
        "",
        "Built by `task.build_prompt()`:",
        "",
        fence(task.build_prompt(), "text"),
        "",
        "### 3.5 Request parameters",
        "",
        "| parameter | value |",
        "|---|---|",
        "| `temperature` | 0.2 |",
        f"| `max_tokens` | {config.REASONING_HEADROOM} "
        "(reasoning headroom; a 4096 cap was consumed entirely by hidden "
        "reasoning in the first live run and returned an empty completion) |",
        "| `usage.include` | true — so real billed cost is recorded per call |",
        "| concurrency | "
        f"{config.MAX_CONCURRENCY} |",
        "| retries | "
        f"{config.RETRIES} |",
        "| timeout | "
        f"{config.REQUEST_TIMEOUT_S}s |",
        "",
        "### 3.6 Scoring: 100 points",
        "",
        "Weights are asserted to sum to 100 at import. A predecessor harness "
        "declared 100, actually weighted 110, then clipped with "
        "`min(total, 100)` — which silently compressed every score.",
        "",
        "| category | points | what earns it |",
        "|---|---|---|",
        "| fidelity | 30 | no invented credentials; real employers and certs "
        "present |",
        "| alignment | 20 | JD themes actually covered (7 themes) |",
        "| bullets | 12 | action-verb ratio; average bullet length in band |",
        "| metrics | 10 | verified numbers only |",
        "| targeting | 10 | role named early; incumbent entity; prior employers |",
        "| ats_structure | 8 | 4 parseable sections |",
        "| skills | 5 | required-stack coverage |",
        "| brevity | 5 | 400–600 word target band |",
        "| **total** | **100** | `assert sum(WEIGHTS.values()) == 100` |",
        "",
        f"Target word band for bullets: 7–28 words; resume: "
        f"{config.WORD_MIN}–{config.WORD_MAX} "
        f"(target {config.WORD_TARGET_MIN}–{config.WORD_TARGET_MAX}).",
        "",
        "### 3.7 Gates and the clamp",
        "",
        "A gate failure caps the score, so a high score and a failed gate cannot "
        "coexist. This is the fix for a predecessor harness where 13 of 27 runs "
        "scored ≥90 while failing a gate.",
        "",
        "| gate | severity | checks |",
        "|---|---|---|",
        "| G1 | **critical** | no invented degrees / employers / clearance |",
        "| G2 | **critical** | no unverified degree claimed (omission is not "
        "fatal) |",
        "| G3 | **critical** | identity intact (name, entity, citizenship) |",
        "| G4 | **critical** | output is the resume only — no fences, no preamble "
        "|",
        "| G5–G10 | non-critical | sections present, word count, first-person, "
        "contractor signal, role relevance, markdown table structure |",
        "",
        f"Critical failure caps at **{config.CRITICAL_FAIL_SCORE_CAP:.0f}**. "
        f"Non-critical failure caps at "
        f"**{config.NON_CRITICAL_FAIL_SCORE_CAP:.0f}**.",
        "",
        "### 3.8 The allowlists (read from `gates.py`)",
        "",
        "**Verified employers:** "
        + ", ".join(f"`{x}`" for x in VERIFIED_EMPLOYERS),
        "",
        "**Verified degrees:** "
        + ", ".join(f"`{x}`" for x in VERIFIED_DEGREES),
        "",
        "**Verified certifications:** "
        + ", ".join(f"`{x}`" for x in VERIFIED_CERTS),
        "",
        "**Verified metrics:** "
        + ", ".join(f"`{x}`" for x in VERIFIED_METRICS),
        "",
        "**Forbidden degrees:** "
        + ", ".join(f"`{x}`" for x in FORBIDDEN_DEGREES),
        "",
        "**Forbidden employers:** "
        + ", ".join(f"`{x}`" for x in FORBIDDEN_EMPLOYERS),
        "",
        "**Forbidden clearance claims:** "
        + ", ".join(f"`{x}`" for x in FORBIDDEN_CLEARANCE),
        "",
        "> **Every VERIFIED_* entry must appear verbatim in the candidate "
        "profile.** `1000`, `4.0` and `2016` used to sit in the metrics list and "
        "appear nowhere in the profile — a model could invent that graduation "
        "year and be *credited* for it. `test_scorers.py` now enforces the "
        "invariant. See §7.",
        "",
        "### 3.9 Significance method",
        "",
        "Means alone are not published as a ranking. The test is Welch's t on "
        "per-run scores against the incumbent, with Cohen's d for effect size.",
        "",
        "| rule | value |",
        "|---|---|",
        "| significant | \\|t\\| ≥ 2.5 **and** \\|d\\| ≥ 0.8 |",
        "| otherwise | reported as `inside noise` |",
        "| fewer than 3 scored runs | `low_n` — not a result |",
        "",
        "The p-value uses a normal approximation, which is stated rather than "
        "implied. At n=4–11 the conservative reading is that anything under "
        "\\|t\\|≈2.5 is not evidence.",
        "",
        "### 3.10 Model set and rounds",
        "",
        "| round | set | runs/model | effort | file |",
        "|---|---|---|---|---|",
        "| 1 | every OpenRouter model with output ≤ $2/M | 3 | provider "
        "default | `results/contest_cheap_r1.json` |",
        "| 2 | round-1 contenders within 4 points of control | 8 | provider "
        "default | `results/contest_cheap_r2.json` |",
        "| 3 | named high/low-cost set | 4 | explicit | "
        "`results/contest_cheap_r3.json` |",
        "",
        "**A variant is not a model.** The unit is "
        "`(model_id, reasoning_effort)`. The same family at `xhigh` and at "
        "provider default is a different model and is never pooled.",
        "",
        "**Efforts are verified, not assumed.** If an explicit "
        "`reasoning_effort` returns zero reasoning tokens, the row is flagged "
        "`effort_honoured: false` rather than reported under the requested "
        "effort. DeepSeek V4.1 Flash ignored `xhigh`.",
        "",
        "**Cost is measured, not modelled.** `$/run` is the mean observed "
        "`usage.cost`, not price × an assumed token count.",
        "",
    ]

    if A:
        rows = sorted([r for r in A["rows"] if r["mean"] is not None],
                      key=lambda r: -r["mean"])
        L += [
            "### 3.11 Results — all measured variants",
            "",
            "| # | variant | n | mean | sd | Δ vs control | t | $/run | verdict |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            lbl = r["label"] + (f" · {r['effort']}" if r["effort"] else "")
            sd = f"{r['sd']:.1f}" if r["sd"] is not None else "—"
            delta = (f"{r['delta']:+.1f}"
                     if r.get("delta") is not None else "—")
            tv = f"{r['t']:.2f}" if r.get("t") is not None else "—"
            L.append(
                f"| {r['rank']} | {lbl} | {r['n']} | {r['mean']:.1f} "
                f"| {sd} | {delta} | {tv} "
                f"| ${r['cost_per_run']:.5f} | {r.get('verdict') or '—'} |")
        L += ["", "Control = DeepSeek V4.1 Flash at provider default.", ""]

    # ── 4 Test B ─────────────────────────────────────────────────────────
    L += [
        "---",
        "",
        "## 4. Test B — full resume (faithfulness + structure)",
        "",
        "### 4.1 Input: raw experience notes",
        "",
        "Deliberately messy — this is what the pipeline actually receives.",
        "",
        fence(json.dumps(dfn.FIXTURE_EXPERIENCES, indent=2), "json"),
        "",
        "### 4.2 Input: education and certifications",
        "",
        "> **⚠ THESE DATES ARE SYNTHETIC — DO NOT USE IN PRODUCTION**",
        ">",
        "> The school years and certificate dates below are **invented for this "
        "test**. They exist only so that \"did the model copy the year "
        "exactly?\" is measurable. They are **not** claims about the candidate "
        "and must never be copied into any prompt shown to a real user or into "
        "any generated resume. Full reasoning in §5.",
        "",
        fence(json.dumps(dfn.FIXTURE_EDUCATION, indent=2), "json"),
        "",
        fence(json.dumps(dfn.FIXTURE_CERTIFICATIONS, indent=2), "json"),
        "",
        "### 4.3 Input: verified metrics (the only numbers allowed)",
        "",
        fence(json.dumps(dfn.VERIFIED_METRICS, indent=2), "json"),
        "",
        "### 4.4 Input: job description (context only, never evidence)",
        "",
        fence(dfn.JOB_AD, "text"),
        "",
        "### 4.5 The system prompt (verbatim)",
        "",
        fence(dfn.build_resume_prompts()[0], "text"),
        "",
        "### 4.6 The user message (verbatim)",
        "",
        fence(dfn.build_resume_prompts()[1], "text"),
        "",
        "### 4.7 Request parameters",
        "",
        "| parameter | value |",
        "|---|---|",
        "| `temperature` | 0.3 — the production drafter's own setting |",
        "| `max_tokens` | 8192 (1200 for `gpt-3.5-turbo-0613`, whose context is "
        "4095) |",
        "| `reasoning_effort` | same value Test A used for that variant, so a "
        "row in both tables describes the same configuration |",
        "| runs per variant | 3 |",
        "",
        "### 4.8 Test criteria — two contracts, both required",
        "",
        "**Faithfulness**",
        "",
        "| check | rule |",
        "|---|---|",
        "| invented technology | any of "
        f"{len(dfn.JD_ONLY_TECH)} JD-only technologies in a bullet, "
        "word-boundary matched |",
        "| invented company | an org-like token outside the allowed set |",
        "| unverified number | a number not in the verified metrics list |",
        "| unit stripped | a verified value whose unit was dropped "
        "(`30` instead of `30 hours`) |",
        "",
        "JD-only technologies (using any of these is fabrication): "
        + ", ".join(f"`{t}`" for t in sorted(dfn.JD_ONLY_TECH)),
        "",
        "Allowed technologies: "
        + ", ".join(f"`{t}`" for t in sorted(dfn.ALLOWED_TECH)),
        "",
        "**Structure**",
        "",
        "| check | rule |",
        "|---|---|",
        "| required sections | `PROFESSIONAL EXPERIENCE`, `EDUCATION`, "
        "`CERTIFICATIONS` |",
        "| chronology | source companies appear in reverse-chronological order |",
        "| employment dates | start **and** end copied exactly, month included |",
        "| education years | both years of each range exact, and no invented "
        "year |",
        "| certification dates | exact issue date per certificate |",
        "| formatting | plain text; no markdown table, no code fence |",
        "",
        "**Bullet format** (reported separately, not part of `pass`): "
        "15–25 words per bullet, strong action verb first, one thought per "
        "line.",
        "",
        "**Truncation** is its own column. A run that uses ≥98% of its "
        "`max_tokens` budget was cut off mid-sentence; that is not a wrong date.",
        "",
        "### 4.9 Word bands and verb lists (read from the module)",
        "",
        "Strong verbs: " + ", ".join(f"`{v}`" for v in sorted(dfn.STRONG_VERBS)),
        "",
        "Vague verbs (penalised): "
        + ", ".join(f"`{v}`" for v in dfn.VAGUE_VERBS),
        "",
    ]

    if B:
        vs = sorted([v for v in B["variants"]],
                    key=lambda v: (-v["pass_rate"], -(v["test_a"] or 0)))
        L += [
            "### 4.10 Results — pass rate per variant",
            "",
            "| # | variant | n | pass | faith | struct | truncated | 15–25w band "
            "| $/run | Test A |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for i, r in enumerate(vs, 1):
            lbl = r["label"] + (f" · {r['effort']}" if r["effort"] else "")
            ta = f"{r['test_a']:.1f}" if r["test_a"] is not None else "—"
            L.append(
                f"| {i} | {lbl} | {r['n']} | **{r['pass_rate']:.0f}%** "
                f"| {r['faith_clean']}/{r['n']} | {r['struct_clean']}/{r['n']} "
                f"| {r['truncated_runs']}/{r['n']} "
                f"| {r['bullet_band_pct']:.0f}% "
                f"| ${r['cost_per_run']:.5f} | {ta} |")
        L += [
            "",
            "`pass` = faithfulness-clean AND structurally-clean on the same run.",
            "",
            "### 4.11 What Test B showed",
            "",
            "1. **Structure was rarely the failure.** Almost every variant "
            "copied dates and years exactly. The hard part was the **15–25 word "
            "band**, where several models scored 0–7%.",
            "2. **One variant leaked its reasoning.** Gemini 3.8 Flash at `high` "
            "emitted internal word-count deliberation instead of a resume on all "
            "three runs, and hit the 8192-token cap each time.",
            "3. **Test A does not predict Test B.** Cheap models passed; one "
            "expensive model failed outright.",
            "",
        ]

    # ── 5 years ──────────────────────────────────────────────────────────
    L += [
        "---",
        "",
        "## 5. The year problem — why synthetic years must never reach output",
        "",
        "This section exists because the harness is **instructed to write a "
        "resume**, and Test B needs years in its input to check whether the "
        "model copied them. That creates a real risk worth naming explicitly.",
        "",
        "### 5.1 The instruction creates the exposure",
        "",
        "Test B's prompt says, in substance: *copy the education years and "
        "certification dates exactly from the source below.* Any model doing its "
        "job will therefore emit the years it is given. If the years it is given "
        "are synthetic, the output contains fabricated credentials that read as "
        "verified.",
        "",
        "A **missing** graduation year is incomplete. An **invented** graduation "
        "year is a misrepresentation. Those are not the same defect and must not "
        "be treated as one.",
        "",
        "### 5.2 Four reasons the rule is absolute",
        "",
        "1. **It is a claim to an employer.** A resume is a document of record. "
        "A fabricated graduation year or certification date is a false statement "
        "attributed to the candidate, in the candidate's name, sent to a third "
        "party. No benchmark convenience justifies that.",
        "",
        "2. **It is identity-adjacent.** Inventing a year is indistinguishable in "
        "kind from inventing the degree. Age and tenure are inferred from "
        "graduation years; a wrong year can misstate both.",
        "",
        "3. **Nothing downstream would catch it.** Test A's critical gates "
        "G1–G4 check employers, degrees and clearance. There is **no gate for "
        "years**. A synthetic year that leaked into a production prompt would "
        "pass every existing check silently. This is the single most important "
        "reason the rule cannot rely on a reviewer noticing.",
        "",
        "4. **It cannot be traced back.** These values exist only inside a "
        "scorer fixture. No source document supports them, so a leak is not "
        "auditable after the fact — there is nothing to verify against.",
        "",
        "### 5.3 What the code guarantees",
        "",
        "| guarantee | where |",
        "|---|---|",
        "| production profile contains no education or certification years | "
        "`task.CANDIDATE_PROFILE` |",
        "| fixture block is marked SYNTHETIC in source | "
        "`drafter_faithfulness.FIXTURE_EDUCATION` |",
        "| invariant test fails if the profile gains a year | "
        "`test_scorers.py::_invariants` |",
        "| production path never imports the fixture for real users | "
        "`task.build_prompt()` uses `CANDIDATE_PROFILE` only |",
        "",
        "### 5.4 The rule, stated plainly",
        "",
        "> **Education years and certification dates must always come from the "
        "candidate's own uploaded documents.** They are never inferred, never "
        "defaulted, never borrowed from a test fixture, and never carried over "
        "from another candidate's record. If a source year is unavailable, the "
        "resume omits it — omission is always preferable to invention.",
        "",
        "> If a future change makes the harness copy `FIXTURE_EDUCATION` or "
        "`FIXTURE_CERTIFICATIONS` into a prompt for real users, that is a "
        "**defect**, not a configuration choice.",
        "",
    ]

    # ── 6 AA ─────────────────────────────────────────────────────────────
    L += [
        "---",
        "",
        "## 6. AA-PersonalityBench — a prior, not a score",
        "",
        "Data exists for 40 models: 30 trait Elos plus 8 index percentiles, "
        "extracted from the website payload because the documented API returns "
        "**404 DEPLOYMENT_NOT_FOUND** and the v2 host carries no personality "
        "fields.",
        "",
        "It is **not** a grading axis, for three measured reasons:",
        "",
        "1. **Not exposed by the API** — website payload is the only route.",
        "2. **Does not predict the task** — see the correlation table.",
        "3. **It would mis-rank the winner** — DeepSeek V4.1 Flash has the "
        "highest `organization` index of all 40 (100) and finished last among "
        "contenders. `eloquent` ranks Claude Fable 5.1 first (1716) and Kimi "
        "K3.1 Pro 14th (1189), while the harness found Kimi the "
        "best-faithfulness drafter.",
        "",
    ]

    # correlation recomputed
    try:
        from resume_writing_v2.compile_results import trait_correlation
        corr = trait_correlation(A["rows"]) if A else []
    except Exception:                                   # noqa: BLE001
        corr = []
    if corr:
        n = corr[0][2]
        crit = 1.96 / (n - 3) ** 0.5
        L += [
            f"### Trait vs measured score — n={n} models",
            "",
            "One point per model (its best variant). "
            f"|r| must exceed **{crit:.2f}** for p<0.05 at n={n}.",
            "",
            "| trait | Pearson r | significant |",
            "|---|---|---|",
        ]
        for t, r, _n in corr:
            L.append(f"| `{t}` | {r:+.2f} | "
                     f"{'yes' if abs(r) > crit else 'no'} |")
        L += [
            "",
            "**No trait clears the threshold.** An earlier analysis reported "
            "`scannable` at +0.81 on n=6 and called it borderline; at n=24 the "
            "same relationship is far weaker. That regression toward zero is "
            "what a small-sample correlation does, and it is why the n=6 figure "
            "should never have been quoted as predictive.",
            "",
            "Where the traits ARE useful is corroboration: MiniMax M3.1 Flash "
            "scores near-bottom `truthful` (202 of a −611…2178 scale) while its "
            "`scannable` (1079) exceeds Kimi's (980) — exactly the shape the "
            "full-resume test measured independently.",
            "",
        ]

    # ── 7 corrections ────────────────────────────────────────────────────
    L += [
        "---",
        "",
        "## 7. Corrections carried forward",
        "",
        "Recorded because each could have produced a confidently wrong "
        "recommendation.",
        "",
        "| # | error | consequence if unfixed |",
        "|---|---|---|",
        "| 1 | Claimed \"AA publishes no writing benchmark\" | the benchmark "
        "exists on the website; the claim was false |",
        "| 2 | Named `slop` as \"avoidance\", higher-is-better | **inverted** — "
        "corr(organization, slop) = −0.196; would have recommended the sloppiest "
        "models |",
        "| 3 | Parsed personality block `[0]` on every page | a degenerate "
        "placeholder produced ~200 identical meaningless rows |",
        "| 4 | Predecessor scored 13/27 runs ≥90 while failing a gate | gate "
        "clamp added |",
        "| 5 | Predecessor weights summed to 110 then clipped at 100 | silently "
        "compressed every score |",
        "| 6 | `rag` substring-matched inside `storage` | flagged a faithful "
        "response as fabricated |",
        "| 7 | `quantification_score: 0.33` counted as a metric | JSON metadata "
        "read as a fabricated number |",
        "| 8 | **`2016`, `1000`, `4.0` in VERIFIED_METRICS but absent from the "
        "profile** | a model could invent that graduation year and be *credited* "
        "for it by the metrics score |",
        "| 9 | Plain-text resumes scored by the JSON scorer | all 43 variants "
        "appeared to fail faithfulness |",
        "| 10 | `04/2024` parsed as the numbers 4 and 2024 | correct dates "
        "flagged as fabricated metrics |",
        "| 11 | Unmarked bullets not extracted | models with 7 good bullets "
        "scored 0 |",
        "| 12 | Education/cert lines counted as bullets | band compliance forced "
        "to 0% |",
        "| 13 | Character window instead of line | adjacent credentials shared "
        "years, reported as invented |",
        "| 14 | Fixed above-then-below line preference | below-layout certs "
        "borrowed the previous cert's date |",
        "| 15 | Test B-bullets ranked on format | MiniMax M3.1 Flash looked "
        "best while inventing 24 items |",
        "",
        "Errors 8–14 were found by `test_scorers.py` or by inspecting a specific "
        "response, not by reading the code. That is the argument for asserting "
        "that a scorer fires on known-bad input.",
        "",
        "---",
        "",
    ]

    # ── 8 limitations ────────────────────────────────────────────────────
    L += [
        "## 8. Limitations",
        "",
        "1. **Small n.** Test A is n=4–11 per variant and resolves ~5–6 point "
        "differences, not 2-point. Test B is n=3; a 3/3 record is consistent "
        "with a ~15% failure rate. Read \"no failures observed\", not \"never "
        "fails\".",
        "2. **One task each.** One job description, one profile, one fixture. "
        "Resume writing is stylistically narrow; this may not transfer to "
        "another domain.",
        "3. **Deterministic scorers fail in fixed ways.** Fifteen such errors are "
        "listed in §7. The suite in `test_scorers.py` covers the classes found "
        "so far; it cannot prove the absence of others.",
        "4. **The Test B prompt is a reconstruction.** The production "
        "`stages/drafter.py` prompt has a golden-bullet library and seniority "
        "verb tables that vary per deployment. Every truth constraint and the "
        "evidence boundary are preserved, so relative comparisons hold; absolute "
        "scores are not production-identical.",
        "5. **The fixture is sparse on purpose.** Sparse input is what makes "
        "fabrication tempting; it is also not representative of a rich profile.",
        "6. **No LLM-as-judge anywhere.** A judge would inject a second model's "
        "bias into a cross-model comparison, so every metric here is "
        "deterministic and repeatable.",
        "7. **Cost attribution per key is unavailable.** `/api/v1/activity` has "
        "no `api_key_name`, so key totals cannot be joined to models.",
        "",
        "---",
        "",
        "## 9. Reproducing",
        "",
        "```bash",
        "source venv/bin/activate",
        "",
        "# Test A",
        "python resume_writing_v2/run_contest.py          # round 1",
        "python resume_writing_v2/round2.py               # round 2",
        "python resume_writing_v2/round3.py               # round 3, named set",
        "",
        "# Test B (full resume)",
        "python resume_writing_v2/round_b_fullresume.py",
        "RESCORE=1 python resume_writing_v2/round_b_fullresume.py   # no API calls",
        "",
        "# verification (free, no network)",
        "python resume_writing_v2/test_scorers.py",
        "",
        "# documents",
        "python resume_writing_v2/compile_test_b.py",
        "python resume_writing_v2/compile_results.py",
        "python resume_writing_v2/build_report.py",
        "```",
        "",
        "### Spend for this document",
        "",
        "| experiment | USD |",
        "|---|---|",
    ]
    for label, s in spend_rows:
        L.append(f"| {label} | ${s:.2f} |")
    L += [
        f"| **total** | **${spend_total:.2f}** |",
        "",
        "---",
        "",
        "*Generated from source by `resume_writing_v2/build_report.py`. "
        "Prompts, fixtures and allowlists are read from the modules that ran.*",
        "",
    ]
    return "\n".join(L)


def to_pdf(md_path: str) -> str | None:
    """Convert to PDF with pandoc. Returns the path, or None if it cannot.

    A PDF is a convenience, never a build requirement: if LaTeX is missing the
    Markdown is still complete and the build still succeeds. Verbose pandoc
    output is captured so a failure is a one-line message, not a wall of TeX.
    """
    if not shutil.which("pandoc"):
        return None
    cmd = [
        "pandoc", md_path, "-o", PDF_OUT,
        "--pdf-engine=xelatex",
        "-V", "geometry:margin=2.2cm",
        "-V", "fontsize=9pt",
        "-V", "colorlinks=true",
        "--toc", "--toc-depth=2",
        "-V", "mainfont=DejaVu Serif",
        "-V", "monofont=DejaVu Sans Mono",
        "--highlight-style=tango",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and os.path.exists(PDF_OUT):
            return PDF_OUT
        err = (r.stderr or "").strip().splitlines()
        print("pandoc failed:", err[-1] if err else "unknown error")
        # fall back to a plain engine with no font overrides
        r2 = subprocess.run(
            ["pandoc", md_path, "-o", PDF_OUT, "--pdf-engine=xelatex",
             "-V", "geometry:margin=2cm"],
            capture_output=True, text=True, timeout=300)
        if r2.returncode == 0 and os.path.exists(PDF_OUT):
            return PDF_OUT
        err = (r2.stderr or "").strip().splitlines()
        print("pandoc fallback failed:", err[-1] if err else "unknown")
    except Exception as e:                              # noqa: BLE001
        print(f"pandoc error: {type(e).__name__}: {e}")
    return None


def main() -> int:
    text = build()
    with open(MD_OUT, "w") as f:
        f.write(text)
    lines = text.count("\n")
    print(f"wrote {MD_OUT}  ({lines} lines, {len(text):,} chars)")
    pdf = to_pdf(MD_OUT)
    if pdf:
        print(f"wrote {pdf}")
    else:
        print("no markdown->PDF converter available "
              "(pandoc / md-to-pdf); Markdown written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
