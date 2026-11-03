# METHODOLOGY — what was tested, how, and what the numbers mean

This states the design; `RESULTS.md` states the outcomes.

- **`RESULTS.md`** — consolidated final results, recommendations, limitations.
  (Earlier per-round reports were removed; their corrections are summarised in
  RESULTS.md §5 and preserved in git history.)

---

## 0. There are THREE different things being measured

They answer different questions and are **not interchangeable**. Conflating them
is the fastest way to draw a wrong conclusion.

| # | Test | Question | Scored on | Results |
|---|---|---|---|---|
| A | **Free-authoring contest** | Can a cheap model write a good resume from a profile? | gate-clamped 100-pt rubric | RESULTS.md §2 |
| B | **Drafter faithfulness** | Can a model rewrite raw notes into STAR bullets without inventing anything? | fabrication / metrics / format | RESULTS.md §3 |
| C | **AA-PersonalityBench** | What does AA's published writing benchmark say? | 8 index percentiles + 30 trait Elos | RESULTS.md §5 |

Notes that matter:

- **C is not a scoring axis for A or B.** PersonalityBench is a prior/candidate
  filter. It has *never* been used to grade a run. It was also shown to be a poor
  predictor: DeepSeek V4.1 Flash has the highest PersonalityBench organization of
  40 models (100) and came **last among contenders** in test A.
- **A and B use different tasks.** A is authoring from a structured profile. B is
  constrained rewriting with an explicit evidence boundary. A model can win one
  and lose the other — several did.
- **Neither A nor B measures prose beauty.** Deliberately. A fluent fabricator is
  worse than a plain faithful writer for this pipeline.

---

## A. Free-authoring contest

### Task
One prompt: a Boeing Defense GenAI Data Scientist job description plus a verified
candidate profile. The model writes a complete resume.

### Scoring — 100 points, weights asserted at import

| category | pts | what earns it |
|---|---|---|
| fidelity | 30 | no invented credentials; real employers/certs present |
| alignment | 20 | JD themes actually covered (7 themes: genai, data, eval, compute, containers, governance, mlops) |
| bullets | 12 | action-verb ratio, 7–28 word length band |
| metrics | 10 | verified numbers only, from a fixed list |
| targeting | 10 | role named early, incumbent entity, prior employers |
| ats_structure | 8 | 4 parseable sections |
| skills | 5 | required-stack coverage, 12 keywords |
| brevity | 5 | 400–600 word target band |
| **total** | **100** | asserted `sum(WEIGHTS) == 100` at import |

### Gates — and the clamp that makes them binding

| gate | severity | checks |
|---|---|---|
| G1 | **critical** | no invented degrees / employers / clearance |
| G2 | **critical** | no unverified degree claimed (omission is *not* fatal) |
| G3 | **critical** | identity intact (name, contractor entity, citizenship) |
| G4 | **critical** | output is the resume only — no fences, no preamble |
| G5 | non-critical | experience / projects / education sections present |
| G6 | non-critical | word count inside 320–700 |
| G7 | non-critical | no first-person bullets |
| G8 | non-critical | contractor signal present |
| G9 | non-critical | target-role relevance |
| G10 | non-critical | no markdown **table structure** |

**The clamp:** any critical failure caps the score at **69**; any non-critical
failure caps at **89**. This is the fix for the predecessor harness, where 13 of
27 runs scored ≥90 *while failing a gate*.

### Why the gate design changed
- G10 previously tested `resume_text.count("|") > 5`, which fired on 16 of 17
  gate-failing runs and flagged prose pipes as tables. It now detects real table
  structure (3+ cells plus a separator row).
- G7 previously compiled an uppercase `I` against lowercased text with no
  `IGNORECASE`, so it could never match.
- Weights previously declared 100 but summed to 110, then `min(total, 100)`
  silently compressed every score.

### Trust check
Reported before any ranking: individual-run spread vs within-model repeat
standard deviation. Free-authoring: **71.5-point spread vs 7.5-point noise =
9.5×**, and 0/75 perfect scores. Where the ratio is poor, the report says the
harness is *not* discriminating rather than printing a leaderboard.

### Significance
Means alone were not published as a ranking. Round 1 (n=3) produced 7 "winners"
at +1.2 to +3.7 points, all with |t| < 0.9 — inside noise. Round 2 (n=8) plus
combined n=11 produced 4 **statistically significant** winners (t = 2.6–3.5,
Cohen's d = 1.1–1.5).

Threshold used throughout: **|t| ≥ 2.5 AND |Cohen's d| ≥ 0.8**. Both must hold.
A large effect with an unstable n, or a stable mean with a trivial effect, is
reported as `inside noise`.

### Rounds, and why a variant is not a model

| round | set | runs/model | effort |
|---|---|---|---|
| 1 | every OpenRouter model with output ≤ $2/M | 3 | provider default |
| 2 | round-1 contenders within 4 pts of control | 8 | provider default |
| 3 | the named high/low-cost set (Haiku through GPT-3.5) | 4 | explicit |

Rounds 1 and 2 ran every model at the **provider default** effort. Round 3 exists
because that cannot answer "Grok 4.7 at `xhigh` vs Kimi K3.1 Pro", and because
most of that set had never been run at all.

The unit of analysis is therefore the **variant**: `(model_id, reasoning_effort)`.
The same family at `xhigh` and at provider default behaves differently — Grok 4.7
at `xhigh` produced 68–78 where its default-effort predecessor sat near 68–71 —
so pooling them would average two different models and hide the effect under test.

**Cost is measured, not modelled.** `$/run` is the mean observed `usage.cost`
returned by OpenRouter for the scored runs, not price × an assumed token count.
That matters because reasoning models bill for hidden reasoning tokens, which vary
run to run (Grok 4.7 at `xhigh`: $0.119–$0.177 per run for the same prompt).

---

## B. Drafter faithfulness contest

### Task — read from `stages/drafter.py`, not assumed
The production drafter (`OR_SLUG_DRAFTER = "qwen/qwen3-coder"`, temp 0.3,
`max_tokens=6000`) receives **raw experience notes** and must emit STAR bullets
as JSON.

### Scoring axes — the drafter's own contract

| axis | how it is checked | verdict role |
|---|---|---|
| **fabrication** | any of 23 JD-only technologies (aws, docker, kubernetes, pytorch, langchain, llm, gpu, rag…) appearing in a bullet → violation. Word-boundary matched. | **auto-fail** |
| **fabricated company** | any org-name token outside the allowed company set | **auto-fail** |
| **metric fidelity** | a number not in the verified list (currently `40`, `30`), or in the list but with its unit stripped (`"30"` instead of `"30 hours"`) | **auto-fail** |
| **schema** | output parses as `{"rewritten_experiences": [...]}` | required |
| **bullet band** | share of bullets in **15–25 words** | format |
| **strong verbs** | share of bullets starting with an approved verb | format |
| **coverage** | every source company survives | required |

`clean` = no fabrication, no metric error, schema OK, full coverage.

**Prose quality is not scored.** A model that writes beautifully and invents
"reduced latency 65%" fails, which is the correct outcome for this pipeline.

### The fixture, and why it is sparse
Two jobs (Cogito Metric, NOAA), five and three raw bullets, and exactly **two**
verified metrics. Sparse input is what makes fabrication tempting: the model has
to resist "the JD asks for Docker" without inventing that the candidate used
Docker.

### What "fabrication" actually flagged
Every single flagged item across all runs was a **JD-only technology** — no
fabricated companies anywhere. Example: incumbent run 1 was flagged for
`['docker', 'kubernetes']`. The source says "Worked with Postgres and Python for
the storage layer", which does not license Docker. That is an invention under
TRUTH CONSTRAINT 3.

### Reference points
- Incumbent `qwen/qwen3-coder`: 3/4 clean, **0%** of bullets in the 15–25 word
  band.
- Best: `moonshotai/kimi-k3.1-pro` — 4/4 clean, 0 fabricated, 100% band.
- Worst: `minimax/minimax-m3.1-flash` — 0/4 clean, 24 invented items, but 100%
  band and 93% strong verbs. **Best shape, worst faithfulness**: a prose
  benchmark would rank it first.

### Known limitation — the fixture's evidence boundary
The drafter prompt *does* include a job description, so a model may argue Docker
is "context". The pipeline's own contract settles it: the JD "may NEVER supply
accomplishments". Under that rule the flag is correct. But this is a judgement
call baked into the fixture, not an objective truth, and it is why the report
never claims an absolute "fabrication rate" — only relative comparisons on the
same fixture.

---

## C. AA-PersonalityBench (prior, not a score)

AA-PersonalityBench publishes **two different things on two different scales**.
They are not interchangeable and must never be averaged together.

**8 index scores — percentile ranks 1–100** (AA's own page text):
organization, slop, expressiveness, informativeness, transparency, warmth,
conviction, imagination.

**30 trait scores — Elo ratings**, one per named trait. Measured range across
the 40 scored models is **−611 to 2178** and 19 models carry negative values, so
treat the scale as unbounded rather than as a 0–100 or 780–1570 band:
lexicallyVaried, eloquent, literate, naturalSounding, metaphorical, structured,
scannable, summarizesBottomLine, answerFirst, informationDense, evidenceBased,
resourceSpecific, providesActionableGuidance, pragmatic, truthful,
admitsUncertainty, disclaimsWithAssumptions, flagsNuances, sycophantic, friendly,
humorous, sincere, emotionallyIntelligent, direct, confident, opinionated,
constructivelyPushesBack, creative, openEnded, slop.

The indexes are used for ranking. The traits are used to inspect *why* — several
map directly onto the drafter's contract (`scannable`, `answerFirst`,
`summarizesBottomLine`, `structured` → organization; `truthful`,
`evidenceBased`, `resourceSpecific` → the no-fabrication rule).

Both exist only on the website, not in the v2 API, so they are scraped.

- **`slop` is the AMOUNT of filler — lower is better.** Verified:
  corr(organization, slop) = −0.196, and the worst models carry the highest slop
  (Llama 4 Maverick: organization 3.5, slop 100.0). An earlier revision had this
  inverted.
- Combined as `writing_score = (organization + (100 − slop)) / 2`.
- Used **only** to shortlist candidates. Demonstrated not to predict task
  performance.

### Trait predictive value — the n=6 number was not usable

With the round-3 data there are **24 models** that have both a trait record and a
measured score. Pearson r against our score, one point per model (best variant):

| trait | r | threshold at n=24 is 0.43 |
|---|---|---|
| `scannable` | +0.38 | not significant |
| `truthful` | −0.29 | not significant |
| `eloquent` | +0.12 | not significant |
| `lexicallyVaried` | +0.11 | not significant |
| `structured` | +0.10 | not significant |
| `literate` | −0.06 | not significant |

`scannable` was previously reported as **+0.81 at n=6** and described as sitting
"on the threshold". It is now +0.38 at n=24. Both are consistent with a true
correlation somewhere near 0.3–0.4; the n=6 value was small-sample noise, and
quoting it as borderline-predictive was wrong. The correct statement is that no
AA trait has been shown to predict this task.

There is also a **degenerate-payload check** in `compile_results.py`: any AA
record whose 30 traits are all identical is rejected and its values nulled
(currently `GPT-6.1 Sol`, all 1000.0). Such a record is a scrape artefact, not a
model that scores 1000 on every trait.

---

## D. Reproducing

```bash
source venv/bin/activate
python resume_writing_v2/contestants.py           # who is in the contest
python resume_writing_v2/run_contest.py           # A round 1  (RUNS/BUDGET env)
python resume_writing_v2/round2.py                # A round 2  (n=8 contenders)
python resume_writing_v2/round3.py                # A round 3  (named set, efforts)
python resume_writing_v2/analyse_contest.py       # A: trust check + leaderboard
python resume_writing_v2/significance.py <results.json>   # A: significance
python resume_writing_v2/run_drafter_contest.py   # test B
python resume_writing_v2/personalitybench.py      # C: AA indexes
traits
python resume_writing_v2/compile_results.py       # consolidated + figure + RESULTS.md
python resume_writing_v2/visualise.py             # the two per-test figures
```

`compile_results.py` is the single source of `RESULTS.md`. It pools all rounds,
attaches AA trait Elo by **exact** name match only, writes
`results/consolidated.json`, and regenerates `figures/price_vs_quality.png`.
A fuzzy name match is deliberately not attempted: attaching the wrong model's Elo
would be invisible in the output.

Cost: A rounds 1+2 ≈ $0.37 (164 requests), round 3 ≈ $0.75 (100 requests at
named efforts), B ≈ $0.20 (20 requests), C free.

`round3.py` records models with no OpenRouter id (currently
`K2 Horizon 375B A23B`) as **unavailable** rather than dropping them silently.

### Runner safety

The runner checkpoints partial results atomically (`os.replace`) every 5
completions. This was added after a 15-minute console timeout killed a paid-for
run with nothing written: high-effort models can hold a worker for minutes, and
losing the whole round to an impatient shell is a real cost.

---

## E. Honest limitations

1. **Small n.** A is n=11 per model (resolves ~6-point differences, not
   2-point). B is n=4 — a 4/4 record is consistent with a ~10% failure rate.
   Read "no failures observed", not "never fails".
2. **One task each.** One JD, one candidate profile, one fixture. Resume writing
   is stylistically narrow; conclusions may not transfer to another domain.
3. **Deterministic scorers, so they can be wrong in fixed ways.** They are
   keyword and structure based. Two bugs of exactly this kind were found and
   fixed: `rag` matching inside `storage`, and a JSON metadata field
   (`quantification_score: 0.33`) being counted as a fabricated metric.
4. **Drafter prompt is reconstructed.** The golden-bullet library and seniority
   verb tables are omitted; every TRUTH CONSTRAINT and the evidence boundary are
   preserved. Relative faithfulness is meaningful; absolute scores are not
   production-identical.
5. **No LLM-as-judge anywhere.** A judge would inject a second model's bias into
   a cross-model comparison. Every metric here is deterministic and repeatable.
6. **Per-key cost attribution is unavailable** from `/api/v1/activity` (no
   `api_key_name` field). Key totals come from `/api/v1/keys` and cannot be
   joined to models.
