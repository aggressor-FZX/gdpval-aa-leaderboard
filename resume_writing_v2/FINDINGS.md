# v2 harness — findings from the first live runs

Two live runs against the AA writing-adjacent shortlist, 1 run per model,
$0.012 total spend. These are validation runs to prove the harness behaves
correctly, **not** a publishable leaderboard (n=1).

## The AA writing question, answered

**Artificial Analysis publishes no writing benchmark.** Verified against the
live v2 API (`/api/v2/data/llms/models`, 722 records): 18 evaluation fields,
none of them writing, essay, prose, style, summarisation or authoring.

| field | what it measures |
|---|---|
| ifbench, lcr | instruction following, long-context reasoning |
| hle, gpqa, mmlu_pro | factual rigor, reasoning under distribution shift |
| livecodebench, scicode, terminalbench_*, aime*, math_500 | code and math |
| tau2, tau_banking | agentic tool use |

Any "AA writing score" would be fabricated. `shortlist.py` therefore builds an
explicitly-labelled **proxy**: `IFBench .35 + LCR .25 + HLE .25 + GPQA .15`,
with code/math fields deliberately excluded because they do not transfer to
prose authoring. Every output states that it is a proxy.

## Shortlist (66 models with >=3 of 4 components, on OpenRouter, priced)

Top by combined writing-rank and value-rank:

| model | OpenRouter id | proxy | $/M | value |
|---|---|---|---|---|
| MiniMax-M3 | `minimax/minimax-m3` | 0.734 | 0.53 | 1.40 |
| GLM-5.3-Flash | `z-ai/glm-5.3-flash` | 0.672 | 0.24 | 2.83 |
| Hy3 | `tencent/hy3` | 0.640 | 0.24 | 2.65 |
| Gemma 4 26B A4B (Reasoning) | `google/gemma-4-26b-a4b-it` | 0.585 | 0.16 | 3.65 |
| Qwen3.5 9B (Reasoning) | `qwen/qwen3.5-9b` | 0.567 | 0.15 | 3.75 |

Highest proxy overall is `anthropic/claude-fable-5.1` at 0.772 — but at
**$20.00/M** its value score is 0.04, i.e. 39× worse per dollar than MiniMax-M3.
High proxy does not mean good value.

## Bugs the live runs found (all fixed)

1. **Reasoning ate the whole completion budget.** With `max_tokens=4096`,
   GLM-5.3-Flash spent 4,772 reasoning tokens and emitted 0 answer tokens; Hy3
   spent 4,096/4,096. Both returned "empty completion" and could not be scored.
   Fixed: `REASONING_HEADROOM = 16384`, and the runner now reports
   `reasoning_exhausted_budget` distinctly from a transport error.
2. **G2 disqualified omission.** GLM-5.3-Flash failed G2 with `claimed=[]` — it
   simply left education out. Absence is a quality issue (G5), not fabrication.
   Fixed: G2 is critical only for an *unverified* degree claim.
3. **Wrong credential for the AA endpoint.** The first CLI run passed the
   OpenRouter key to AA and got 401. Fixed: `aa_key()` and `api_key()` are
   separate, and a 401 raises an explicit message rather than looking like
   "no models qualify".

## Validation results (n=1, correct behaviour, not a ranking)

| model | score | gates | $/run |
|---|---|---|---|
| Qwen3.5 9B (Reasoning) | 95.1 | clean | 0.00003 |
| MiniMax-M3 | 90.1 | clean | 0.00161 |
| GLM-5.3-Flash | 82.9 | clean | 0.00053 |
| Hy3 | 82.3 | G5 (sections) | 0.00291 |
| Gemma 4 26B A4B (Reasoning) | 67.7 | G5, G6 (232 words) | 0.00008 |

- **spread 27.4 points, 0 perfect scores** — versus v4's 88-100 with 9 perfect.
- The gate clamp was observed firing: a GLM run with raw 86.7 was capped to 69.0
  on a critical gate, instead of being published in the high 80s.
- Gemma's 232-word output is a real finding: reasoning models under `medium`
  effort tend to emit thin resumes, which G6 correctly catches.

## Still open

- **n=1 is not enough.** `RUNS_PER_MODEL=3` is the default for real use; these
  runs were budget validation.
- **Proxy is not a measurement.** The shortlist ranks *candidates to test*. The
  harness exists precisely because the proxy cannot settle the question.
- **`temperature=0.2`** is fixed, so run-to-run variance reported in `std` is
  provider-side only.
