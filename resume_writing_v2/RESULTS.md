# RESULTS — resume-writing model evaluation

Consolidated final results. Supersedes the earlier per-round reports, which were
removed: they documented a first round that was underpowered, a wrong "AA has no
writing benchmark" claim, and an inverted slop direction. Those corrections are
summarised in §5 and preserved in git history.

Cost of everything below: **$0.57** in API calls.

---

## 1. What was tested

Two distinct tests. They answer different questions and are not interchangeable.

| test | task | scored on |
|---|---|---|
| **A — free-authoring** | write a full resume from a verified profile + a Boeing Defense GenAI DS job description | gate-clamped 100-point rubric |
| **B — drafter faithfulness** | rewrite raw experience notes into STAR bullets under an evidence boundary | fabrication / metric fidelity / format |

AA-PersonalityBench was used **only to shortlist candidates**. It was not a
grading axis, and it was shown not to predict task performance — see §5.

---

## 2. Test A — free-authoring, n=11 per model

Incumbent: **DeepSeek V4.1 Flash — mean 84.1, sd 6.3, $0.00246/run**

| model | n | mean | sd | Δ | t | $/run | cost × | verdict |
|---|---|---|---|---|---|---|---|---|
| **Qwen3.7 Plus** | 11 | **91.9** | 3.1 | **+7.8** | 3.50 | 0.00713 | 2.90× | **significant** |
| **MiniMax-M3** | 10 | **91.0** | 2.8 | **+7.0** | 3.15 | 0.00455 | 1.85× | **significant** |
| **Qwen3 Next 80B A3B Instruct** | 11 | **90.0** | 1.5 | **+6.0** | 2.89 | 0.00066 | 0.27× | **significant** |
| **Qwen3.6 35B A3B (Reasoning)** | 11 | **89.8** | 2.9 | **+5.8** | 2.62 | 0.00053 | **0.22×** | **significant** |
| Inkling Small | 11 | 89.7 | 3.9 | +5.6 | 2.38 | 0.00647 | 2.63× | inside noise |
| Qwen3 Coder Next | 11 | 88.4 | 4.4 | +4.4 | 1.79 | 0.00045 | 0.18× | inside noise |
| Qwen3.5 9B (Reasoning) | 11 | 86.4 | 5.5 | +2.3 | 0.88 | **0.00003** | **0.01×** | inside noise |
| gpt-oss-20b (High) | 11 | 85.3 | 3.2 | +1.2 | 0.54 | 0.00002 | 0.01× | inside noise |
| GLM-5.3-Flash | 11 | 83.6 | 4.4 | −0.4 | −0.18 | 0.00077 | 0.31× | inside noise |

**Four models beat the incumbent significantly. None were significantly worse.**

### Recommendation

**`qwen/qwen3.6-35b-a3b`** — +5.8 points (t=2.62, d=1.12), **4.6× cheaper**,
lowest variance of the winners (sd 2.9 vs incumbent 6.3).

- If maximum score matters more than cost: `Qwen3.7 Plus` (91.9) at 2.9× price.
- If minimum cost matters: `Qwen3.5 9B` at **1% of incumbent cost** and
  statistically indistinguishable (+2.3, t=0.88).
- `MiniMax-M3` scored well but must be read with §3 — the same family failed
  drafter faithfulness completely.

### Why n=11 and not n=3
The first round (n=3) showed 7 apparent winners at +1.2 to +3.7 points, all with
|t| < 0.9 — pure noise, because the incumbent's own repeat sd is 5.9. Reporting
those would have been the exact failure the harness exists to prevent.

---

## 3. Test B — drafter faithfulness, n=4 per model

The production drafter is `qwen/qwen3-coder` (temp 0.3, `max_tokens=6000`). Its
contract, read from `stages/drafter.py`: company names exact, only input
technologies, metrics only from a verified list with units attached, 15–25 word
bullets, JSON output. "A bullet without a metric is NOT a failure."

| model | clean runs | fabricated | metric err | 15–25w band | strong verb | $/run |
|---|---|---|---|---|---|---|
| **Kimi K3.1 Pro** | **4/4** | **0** | 0 | **100%** | 94% | $0.04344 |
| **Qwen3 Coder (incumbent)** | 3/4 | 2 | 0 | **0%** | 78% | **$0.00046** |
| Claude Haiku 5.5 | 2/4 | 11 | 0 | 100% | 68% | $0.00205 |
| GLM 5.3 | 2/4 | 5 | 0 | 3% | 78% | $0.00064 |
| **MiniMax M3.1 Flash** | **0/4** | **24** | 0 | 100% | 93% | $0.00041 |

### Two findings

**1. The incumbent's defect is format, not fabrication.** `qwen3-coder` invents
little (2 items / 4 runs) but its bullets average **6–10 words against a 15–25
spec — 0% compliance**:

```
[ 8w] Built resume parsing pipeline processing incoming candidate documents.
[ 9w] Reduced parsing step duration by 40% through refactored workflows.
[ 6w] Managed archived document datasets at scale.
```

This is a prompt-compliance failure on an explicit instruction, and it is
invisible to any fact-only check.

**2. MiniMax M3.1 Flash is the trap.** Best format shape (100% band, 93% strong
verbs), worst faithfulness — **24 invented items, 0/4 clean**. Every flagged item
was a JD-only technology (aws, docker, kubernetes, pytorch, langchain, llm, gpu,
rag). A prose benchmark ranks this model first; the drafter's contract ranks it
last.

### Recommendation

**Keep `qwen3-coder`.** It is the most faithful cheap model; its one defect is
fixable by making the word band machine-checkable (pad-or-retry) instead of
trusting a prompt sentence.

- **Do not switch to MiniMax M3.1 Flash at any price.**
- Kimi is the only model that satisfies both faithfulness and format unaided, but
  at **94× the cost** — a bad trade to avoid a post-processing rule.

---

## 4. Spend — product stages only

30 days (2026-10-04 → 2026-11-02). Development traffic is **excluded**: `gpt-6.1-sol`,
`gpt-6.1-terra`, `claude-haiku-5.5` and similar are engineering-use models, not
product, and quoting them as "cost to replace" would be wrong.

| | spend | requests | share |
|---|---|---|---|
| **A. Imaginator pipeline** | **$2.86** | 2,060 | 1.7% |
| └ drafter (`qwen3-coder`) | $0.21 | — | 0.13% |
| **B. Job Scout research** | **$27.52** | 10,281 | 16.6% |
| **PRODUCT TOTAL** | **$30.38** | 12,341 | **18.3%** |
| Development (out of scope) | $135.82 | — | 81.7% |

### Where the product money actually is

**Job Scout research is 91% of product spend** — `deepseek-v4.1-flash` at
$27.52 across 10,281 requests. The entire Imaginator pipeline, all stages
together, is **$2.86**.

So within the product:

| priority | target | spend | note |
|---|---|---|---|
| 1 | **Job Scout / `deepseek-v4.1-flash`** | $27.52 | 10,281 requests, $0.00408/1k out |
| 2 | `xiaomi/mimo-v2.6-flash` (parser backup) | $1.07 | highest $/1k out of the Imaginator models at 0.00374 |
| 3 | `inception/mercury-3` | $1.08 | |
| 4 | drafter `qwen3-coder` | $0.21 | 0.13% of total — not a cost lever |

**The drafter question is a quality question, not a cost question.** Replacing it
cannot move the bill: it is $0.21 of $166.20.

### Why AA's traits were not used for scoring

They were available and are now extracted for all 40 models (30 trait Elos plus
the 8 index percentiles). They are **not** used as a grading axis, for three
measurable reasons.

**1. They are not exposed by the documented API.** The endpoint
`data.artificialanalysis.ai/api/v1/models` returns **404 DEPLOYMENT_NOT_FOUND**.
The working host (`artificialanalysis.ai/api/v2/...`) has **no** personality data:
`?include=personality` returns a byte-identical payload, `personality_bench` is
absent from `evaluations`, and six plausible subresource paths all 404. Extraction
from the website payload is the only route.

**2. They do not predict the measured task.** Of the 40 models with trait data,
only **6** also produced a measured score in test A. With n=6, |r| must exceed
~0.81 for significance at p=0.05:

| trait | r vs measured score |
|---|---|
| scannable | +0.81 |
| structured | +0.78 |
| lexicallyVaried | +0.75 |
| eloquent | +0.72 |
| informationDense | +0.71 |
| evidenceBased | +0.62 |
| truthful | +0.48 |
| resourceSpecific | +0.37 |
| answerFirst | +0.31 |

Every value sits on or under the significance threshold, so **no trait is a
usable predictor on this sample**. Suggestive, not established.

**3. They would have mis-ranked the best model.** DeepSeek V4.1 Flash has the
highest `organization` index of all 40 models (100) and came **last among
contenders** in test A. `eloquent` ranks Claude Fable 5.1 first (1716) and Kimi
K3.1 Pro 14th (1189) — while the harness found Kimi the single best-faithfulness
drafter. Trait rank and task rank disagree.

### Where the traits are genuinely useful

As a **post-hoc corroboration** of the drafter result, which is not the same as
using them as a score. The traits that map onto the drafter's contract agree with
what the harness measured independently:

| model | `truthful` | `scannable` | measured drafter outcome |
|---|---|---|---|
| Kimi K3.1 Pro | **989** | 980 | **4/4 clean, 0 fabricated** |
| GLM-5.3 | 743 | 994 | 2/4 clean, 5 fabricated |
| Claude Haiku 5.5 | 873 | 967 | 2/4 clean, 11 fabricated |
| **MiniMax-M3.1-Flash** | **202** | 1079 | **0/4 clean, 24 fabricated** |

MiniMax M3.1 Flash scores **near-bottom `truthful` (202 of a −611…2178 scale,
6th lowest of 40)** while its `scannable` (1079) sits above Kimi K3.1 Pro's (980).
That single pair of numbers explains the whole result: it looks well-structured on
a format measure and fabricates in practice. AA's own traits and this harness
reached the same conclusion from different evidence.

The strongest `scannable` in the set is MiMo-V2.6-Pro at 1545, not MiniMax — so
`scannable` alone is not a discriminator, which is consistent with §2 finding it
only borderline correlated (r=+0.81, n=6).

`qwen3-coder` (the production drafter) is **not in AA's 40-model set**, so it has
no traits at all — another reason the empirical harness is the primary instrument.

### Querying specific traits

```bash
python -m resume_writing_v2.personalitybench traits eloquent scannable truthful
```

```python
from resume_writing_v2 import personalitybench as pb
rows = pb.trait_table(traits=("eloquent", "slop"), sort_by="eloquent")
```

Each record carries a `_<trait>_scale` field (`trait Elo` or `index percentile`)
so the two scales cannot be silently mixed. Unknown trait names raise `KeyError`
rather than returning `None`, so a typo cannot look like missing data.

## 5. Corrections carried forward

These were found and fixed; recording them because each could have produced a
confidently wrong recommendation.

| error | consequence if unfixed |
|---|---|
| Claimed "AA publishes no writing benchmark" from the v2 API's 18 fields | AA-PersonalityBench exists on the website; the claim was wrong |
| Named `slop` "avoidance", higher-is-better | **inverted** — corr(organization, slop) = −0.196; worst models carry the highest slop (Llama 4 Maverick org 3.5 / slop 100.0). Would have recommended the sloppiest models |
| Took `personalityBench` block `[0]` on every page | a degenerate placeholder (`organization 1, slop 90.1`) produced ~200 identical meaningless rows |
| Predecessor harness scored 13/27 runs ≥90 while failing a gate | gate clamp added: critical fail ≤69, non-critical ≤89 |
| Predecessor weights summed to 110 then clipped at 100 | silently compressed every score |
| `rag` substring-matched inside `storage` | flagged a faithful response as fabricated |
| `quantification_score: 0.33` counted as a metric | JSON metadata read as a fabricated number |

---

## 6. Limitations

1. **n=11 resolves ~6-point differences, not 2-point.** Claims under ~5 points
   are undetermined.
2. **n=4 for the drafter** — a 4/4 record is consistent with a ~10% failure rate.
   Read "no failures observed", not "never fails".
3. **One task each** — one JD, one profile, one fixture. Resume writing is
   stylistically narrow; results may not transfer to another domain.
4. **Deterministic keyword scorers** can be wrong in fixed ways. Two such bugs
   were found and fixed (§5).
5. **The drafter prompt is reconstructed** — golden-bullet library and seniority
   verb tables omitted. Every truth constraint and the evidence boundary are
   preserved, so relative comparisons hold; absolute scores are not
   production-identical.
6. **The fabrication rule is a judgement call.** The job description *is* in the
   prompt, so a model may argue Docker is "context". The pipeline's own rule that
   the JD "may NEVER supply accomplishments" settles it — but this is a
   design decision, not objective truth.
7. **No LLM-as-judge anywhere** — every metric is deterministic and repeatable.
8. **Per-key cost attribution is unavailable** from `/api/v1/activity` (no
   `api_key_name`), so key totals cannot be joined to models.

Figures: `figures/free_authoring_contest.png`, `figures/drafter_faithfulness.png`
