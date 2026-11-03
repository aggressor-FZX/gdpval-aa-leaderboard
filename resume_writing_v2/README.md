# Resume Writing Competition Harness — v2

A rewrite of the v4 harness (`benchmarks/v4_resume_writing_benchmark.py`), built
because v4 could not discriminate between models and could not detect the failures
it was supposed to catch.

## Why v2 exists — measured, not asserted

Auditing all 27 recorded v4 runs (`results/v4_benchmark_results.json`):

| Symptom | v4 reality |
|---|---|
| Score saturation | 24 scores, **min 88 · max 100 · mean 96.1** |
| Perfect scores | **9 of 24 runs scored exactly 100** |
| Gates vs score disagreement | **13 runs scored ≥90 while failing a gate** |
| Gate concentration | G10 fired on **16 of 17** gate-failing runs |
| Serialisation | `RUNS_PER_MODEL = 3`, sequential loop, no cost ceiling |

A leaderboard where the worst model scores 88 and a third of entries score a
perfect 100 cannot rank models. And 13 runs scoring ≥90 with a failed gate means
the gate layer and the score layer are measuring different things.

## Design changes in v2

### 1. Evidence-checked scoring (fixes the "13 runs" problem)
Any run that fails a **critical** gate is hard-capped at 69. A run that fails a
**non-critical** gate loses its category points *and* cannot enter the
top band. The score is clamped by the gate verdict, so the two layers can no
longer disagree.

### 2. Weights renormalised to 100 (fixes the silent 10% inflation)
v4's docstring said `35+20+10+10+10+5+5+5 = 100` but the actual weights were
`35+20+10+10+10+5+5+5+10 = 110`, then `min(total, 100)` clipped it. Every model
was silently compressed toward 100. v2 declares weights that **sum to exactly
100** and asserts it at import.

### 3. G10 rebuilt (fixes the 16/17 false positives)
v4: `resume_text.count("|") > 5` — fired on any markdown table, including
tables a model *should* produce in a notes file, and on pipes inside prose.
v2 scores **table structure** (rows of 3+ pipe-delimited cells with a separator
line) and ignores isolated pipes. Same for decorative characters: a single rule
sized against the character count of the document.

### 4. Reasoning variants tested separately, not pooled
`GPT-5.6 Sol (Max)` and `(Non-reasoning)` are different models with different
measured intelligence. v2 requires an explicit effort per entry and records it,
so a result always names the variant that produced it.

### 5. Cost and time measured per run, not estimated
v4 hardcoded `price_in`/`price_out` per model. v2 reads pricing from the live
OpenRouter catalog at run time and records `usage.cost` from the response, then
reports $/run and $/quality-point.

### 6. Parallel + budgeted (fixes the sequential cost problem)
Bounded concurrency with a hard `MAX_SPEND_USD` ceiling; the runner stops
submitting when the budget is exhausted rather than discovering it afterwards.

### 7. Distribution-aware reporting
Reports per-model **mean, min, max, std dev and pass rate** across runs, plus the
score spread across the field. If the spread is small, the harness says so
instead of printing a leaderboard that pretends to separate models.

## Reports — read in this order

| document | answers |
|---|---|
| **`METHODOLOGY.md`** | what was tested, the exact scoring axes, thresholds, and limitations. **Start here.** |
| `CONTEST_RESULTS.md` | free-authoring contest: can a cheap model write a good resume from a profile? |
| `DRAFTER_RESULTS.md` | drafter faithfulness: can a model rewrite notes without inventing anything? + spend analysis |
| `FINDINGS.md` | AA-PersonalityBench extraction, and the corrected "AA has no writing benchmark" claim |

Short version: **three different tests, not interchangeable.** Free-authoring is
scored on a gate-clamped 100-point rubric (fidelity 30, alignment 20, bullets 12,
metrics 10, targeting 10, ats 8, skills 5, brevity 5); drafter faithfulness is
scored on fabrication / metric fidelity / format only, because the drafter's job
is fidelity rather than prose. AA-PersonalityBench is a candidate filter and has
never been used to grade a run.

## Layout

```
resume_writing_v2/
├── README.md                 this file
├── config.py                 models, effort, weights, thresholds (validated)
├── gates.py                  hard gates, table-structure aware
├── scoring.py                weighted scoring, gate-clamped, sums to 100
├── runner.py                 OpenRouter runner: parallel, budgeted, logged
├── report.py                 statistics + leaderboard + saturation warning
├── shortlist.py              AA writing-adjacent proxy shortlist
└── run_competition.py        entry point
```

## Running

```bash
source venv/bin/activate
python resume_writing_v2/run_competition.py --dry-run     # plan + cost estimate
python resume_writing_v2/run_competition.py --models shortlist --runs 3
```

`--dry-run` performs no API calls. Nothing spends money without an explicit
budget flag.

## What v2 deliberately does not do

- **No LLM-as-judge.** A judge introduces a second model's bias into a
  cross-model comparison. Every v2 metric is deterministic and reproducible.
- **No fabricated "AA writing score".** I first concluded AA had no writing
  benchmark, from the v2 API's 18 evaluation fields. **That was wrong.**
  AA-PersonalityBench exists (organization, expressiveness, slop, transparency,
  warmth, conviction, imagination, informativeness) and is the primary writing
  measure here. It is not in the API, so `personalitybench.py` extracts it from
  the site; the IFBench/LCR/HLE/GPQA proxy remains only as a labelled fallback.
- **No hidden normalisation.** If a metric is missing, it is reported missing,
  not silently imputed.
