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

48 measured variants across three rounds. Full tables in
[`RESULTS.md`](RESULTS.md) §2; figure at `figures/price_vs_quality.png`.

- **A — best value:** `qwen/qwen3.6-35b-a3b` beats the DeepSeek V4.1 Flash
  incumbent by **+5.8 points (t=2.62)** at **$0.00053/run — 0.21× the cost**.
  Four variants are significantly better; 15 are significantly worse.
- **A — cheap does not mean good.** `Claude Haiku 5.5` at `high` scores **73.8**,
  significantly *worse* than the incumbent (t=−3.89), as do Kimi K3.1 Pro
  (73.5), Grok 4.6/4.7 at `xhigh` (71–72) and GPT-6 Luna at `xhigh` (71.2), at
  13–66× the control's cost per run.
- **A — expensive does not mean good either.** Grok 4.7 at `xhigh` costs
  **$0.162/run** — 66× the control — and scores 72.0.
- **B:** the incumbent `qwen3-coder` is the most faithful *cheap* model but has
  **0% compliance** with its own 15–25 word bullet spec. `Kimi K3.1 Pro` is the
  only model faithful *and* compliant, at 94× cost. `MiniMax M3.1 Flash` writes
  the prettiest bullets and invents 24 things — do not use it as a drafter.
- **Spend (product only):** Job Scout research is **91% of product spend**
  ($27.52/mo). The whole Imaginator pipeline is **$2.86**, of which the drafter
  is $0.21. Development traffic is excluded from this analysis.

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
├── round3.py               test A, named model set at explicit efforts
├── run_drafter_contest.py  test B runner
├── analyse_contest.py      test A trust check + leaderboard
├── compile_results.py      pools all rounds -> RESULTS.md + price/quality figure
├── visualise.py            generates the two per-test figures
└── results/  figures/      raw JSON, consolidated.json, PNGs (gitignored)
```

## Running

```bash
source venv/bin/activate
python resume_writing_v2/contestants.py             # who competes
python resume_writing_v2/run_contest.py             # test A round 1 (RUNS/BUDGET)
python resume_writing_v2/round2.py                  # A round 2, n=8 contenders
python resume_writing_v2/round3.py                  # A round 3, named set
python resume_writing_v2/analyse_contest.py         # A: trust check + table
python resume_writing_v2/significance.py results/contest_cheap_r2.json
python resume_writing_v2/run_drafter_contest.py     # test B
python resume_writing_v2/personalitybench.py        # AA shortlist data
python resume_writing_v2/compile_results.py         # RESULTS.md + figure
python resume_writing_v2/visualise.py               # per-test figures
```

Cost: A rounds 1+2 ≈ $0.37, round 3 ≈ $1.96, B ≈ $0.20. Nothing spends money
without an explicit budget, and `runner.py` checkpoints partial results every 5
completions so a killed shell cannot discard a paid-for round.

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
- **A variant is not a model.** `(model_id, reasoning_effort)` is the unit; the
  same family at `xhigh` and at provider default is never pooled.
- **Efforts are verified, not assumed.** If an explicit `reasoning_effort`
  returns zero reasoning tokens, the run is flagged as default-effort rather
  than reported under the effort name that was requested.
- **Cost is measured, not modelled.** `$/run` is the mean observed `usage.cost`.
