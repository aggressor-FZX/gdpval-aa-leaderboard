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
| **B — full-resume faithfulness + structure** | raw experience notes → a complete resume under an evidence boundary | invention checks **and** sections / chronology / exact dates / ATS formatting — both required |

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
- **B:** 40 variants, 3 runs each, scored on faithfulness **and** structure
  together. **35 passed every run.** Structure was not the hard part — exact
  dates and years were copied correctly by almost everyone. The **15–25 word
  band** was the real discriminator (several models: 0–7%). One variant leaked
  its internal reasoning into the output and failed outright.
- **B — excluded by request:** five variants Test A found significantly worse
  than the incumbent at a higher price (Haiku 5.5 `high`, Kimi K3.1 Pro, Grok
  4.7/4.6 `xhigh`, GPT-6 Luna `xhigh`) were not re-run.
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
├── run_drafter_contest.py  test B runner (superseded bullets-only version)
├── round_b_fullresume.py   test B runner (full resume, faithfulness + structure)
├── compile_test_b.py       test B ranking + figure + RESULTS_TEST_B.md
├── test_scorers.py         scorer self-tests: fire on bad, quiet on good
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
python resume_writing_v2/round_b_fullresume.py      # test B (full resume)
python resume_writing_v2/compile_test_b.py          # B: ranking + figure
python resume_writing_v2/test_scorers.py            # scorer self-tests (free)
python resume_writing_v2/personalitybench.py        # AA shortlist data
python resume_writing_v2/compile_results.py         # RESULTS.md + figure
python resume_writing_v2/visualise.py               # per-test figures
```

Run `compile_test_b.py` **before** `compile_results.py`: the latter folds the
Test B section into `RESULTS.md` at a placeholder.

Cost: A rounds 1+2 = $0.37, round 3 = $1.96, B = $0.50. Total **$3.03**. Nothing
spends money without an explicit budget, and `runner.py` checkpoints partial
results every 5 completions so a killed shell cannot discard a paid-for round.

`RESCORE=1 python resume_writing_v2/round_b_fullresume.py` re-scores saved
responses with the current scorer, at zero cost. Use it after any scorer change:
a run that finished under an older scorer would otherwise keep stale verdicts.

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
- **Scorers are tested.** `test_scorers.py` asserts each check fires on a
  known-bad fixture and stays quiet on a known-good one. Six silent scorer bugs
  were caught this way; each would have produced a confident wrong ranking.
- **Truncation is its own failure.** A run that exhausts its token budget is
  reported as truncated, not as a wrong date.
