# Resume-writing model evaluation

Measures which model should write resumes and STAR bullets for the Imaginator
pipeline, with enough statistical rigour that a result is trustworthy rather
than merely plausible.

**Start with [`RESULTS.md`](RESULTS.md)** — the final answers, recommendations
and limitations. [`METHODOLOGY.md`](METHODOLOGY.md) states the exact scoring
axes and thresholds if you need to audit or reproduce a number.

## What it measured

| test | task | scored on |
|---|---|---|
| **A — free-authoring** | full resume from a verified profile + a job description | gate-clamped 100-point rubric |
| **B — drafter faithfulness** | raw experience notes → STAR bullets under an evidence boundary | fabrication / metric fidelity / format |

These are different tasks and are not interchangeable. AA-PersonalityBench was a
candidate shortlist filter only, never a grading axis.

## Headline findings

- **A:** `qwen/qwen3.6-35b-a3b` beats the DeepSeek V4.1 Flash incumbent by
  **+5.8 points (significant, t=2.62)** at **0.22× the cost**. Four models beat
  it significantly; none were significantly worse.
- **B:** the incumbent `qwen3-coder` is the most faithful *cheap* model but has
  **0% compliance** with its own 15–25 word bullet spec. `Kimi K3.1 Pro` is the
  only model faithful *and* compliant, at 94× cost. `MiniMax M3.1 Flash` writes
  the prettiest bullets and invents 24 things — do not use it as a drafter.
- **Spend:** all Imaginator stages are **1.7%** of the bill. The cost is in
  development traffic (`gpt-6.1-sol` + `gpt-6.1-terra` = 43.8%).

## Layout

```
resume_writing_v2/
├── RESULTS.md              final results, recommendations, limitations
├── METHODOLOGY.md          scoring axes, thresholds, how to reproduce
├── config.py               weights (asserted to sum to 100), gates, word bands
├── gates.py                G1-G10, table-structure aware
├── scoring.py              weighted scoring, gate-clamped
├── drafter_faithfulness.py drafter contract scorer + prompt reconstruction
├── task.py                 JD, candidate profile, system prompt
├── shortlist.py            AA shortlist + PersonalityBench merge
├── personalitybench.py     extract AA-PersonalityBench from the AA website
├── contestants.py          competitor set (output <= $2/M + incumbent)
├── runner.py               OpenRouter runner: parallel, budgeted, logged
├── report.py               statistics + saturation verdict
├── significance.py         Welch t-test + effect size vs the incumbent
├── run_contest.py          test A runner
├── round2.py               test A, higher-n focused rerun
├── run_drafter_contest.py  test B runner
├── analyse_contest.py      test A trust check + leaderboard
├── visualise.py            generates figures/
└── results/  figures/      raw JSON, PNGs (gitignored)
```

## Running

```bash
source venv/bin/activate
python resume_writing_v2/contestants.py             # who competes
python resume_writing_v2/run_contest.py             # test A (RUNS/BUDGET env)
python resume_writing_v2/analyse_contest.py         # A: trust check + table
python resume_writing_v2/significance.py results/contest_cheap_r2.json
python resume_writing_v2/run_drafter_contest.py     # test B
python resume_writing_v2/personalitybench.py        # AA shortlist data
python resume_writing_v2/visualise.py               # figures
```

Cost: A ≈ $0.37, B ≈ $0.20. Nothing spends money without an explicit budget.

## Design principles

- **Deterministic scoring.** No LLM-as-judge — a judge injects a second model's
  bias into a cross-model comparison.
- **Gates clamp the score.** A critical failure caps at 69, non-critical at 89, so
  a high score and a failed gate cannot coexist.
- **Trust check before ranking.** Every analysis reports score spread against
  within-model repeat noise and says whether the harness discriminates at all.
- **Significance gates the claims.** A positive delta inside the noise is reported
  as noise, not as a winner.
- **Missing data stays missing.** No silent imputation, no zero-filling.
