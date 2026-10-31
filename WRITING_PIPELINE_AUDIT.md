# Writing Pipeline Audit — High-Yield Fixes First

**Date:** 2026-10-30
**Scope:** `Imagination_Resume_Module/` (live writer), `Login_Landing_page/backend/services/` (loop writer + scorer),
`dev_workspaces/benchmarks/v4_resume_writing_benchmark.py` + `results/v4_benchmark_results.json` (evaluator),
`dev_workspaces/resume_experiment/` (dataset), `Model_Efficiency_Comparison.ipynb` (appendix V2/V3/V4 cells).
**Spend during this audit:** $0 (code reading + local reproduction only; no model calls, no deploys).

---

## 0. Executive summary

The benchmark says "GLM 5.1 is perfect (100.0)." That conclusion is not supported, and switching models is
**not** the highest-yield next step.

Two cheaper things dominate:

1. **The production writer is instructed to invent facts.** The active Drafter prompt authorizes converting a
   JD requirement into a candidate claim, and separately authorizes inventing team sizes, vessel counts, and
   reporting frequency. Same prompt file later forbids exactly that. Whichever instruction the model follows,
   the output can be unfaithful.
2. **The pipeline destroys correct data on the way through.** I reproduced three independent silent-corruption
   bugs: the PII sanitizer flattens the resume before parsing, the metric validator deletes real source-backed
   numbers, and the revision memo reports every metric as missing on every pass.

Fixing those is roughly **2 hours of work, $0 in model spend, and no deploy risk**. Re-ranking models should
happen *after*, with a scorer that can actually fail an output.

---

## 1. What is actually running in production (verified topology)

```
Frontend  ──POST /api/ml/imagination/analyze──►  orchestrator-backend (Node)
                                                        │
                                                        ▼
                                       imaginator-resume-cowriter (FastAPI app.py)
                                                        │
                                            sanitize_resume_pii()        ◄── BUG S1
                                                        ▼
                                            parse_experiences()          ◄── depends on line structure
                                                        ▼
                                    orchestrator.run_pipeline()
                                       ├─ stages/researcher.py   inception/mercury-2
                                       ├─ stages/drafter.py      qwen/qwen3-coder      ◄── BUG P1..P5, M1, I1
                                       └─ stages/star_editor.py  inception/mercury-2  ◄── BUG M2
                                                        ▼
                                              final_markdown / final_plain_text
```

| Route | Status | Writer |
|---|---|---|
| `POST /api/ml/imagination/analyze` | **default, used by frontend** (`src/services/orchestratorService.ts:58`, `imaginationService.ts:106`) | Imaginator 3-stage |
| `POST /api/analyze/direct` | available | single-shot GLM (`directResumeWriter.js`) |
| `POST /api/analyze/loop` | **returns 503 unless `LOOP_WRITER_ENABLED=true`** (`server.cjs:2392`) | `loopWriter.js` |

**Consequences for planning:**

- The benchmarked task (one model writes a full resume) is **not** the production task (Drafter writes JSON
  bullets → StarEditor writes the document). A model can win one and lose the other.
- `pipeline_config.py:29` sets the Drafter's **first fallback to `z-ai/glm-5.1`** — the benchmark "winner".
  Production can silently run a model that was never benchmarked *in the Drafter role*, and the response does
  not surface which model actually served the request.
- Memory is the binding constraint, not quality: `orchestrator.py:253` caps the Drafter at 6 experiences and
  `drafter.py:332` / `star_editor.py:163` cap output at 6000 / 5000 tokens, against a 1 GB Render instance.
  Any change that enlarges output must be memory-tested first.
- Stale duplicate files exist at module root (`drafter.py` 528 lines, `star_editor.py` 817 lines) that differ
  from the live `stages/` versions (641 / 1347). Editing the root copies changes nothing.

---

## 2. Verified defects, ordered by yield-per-hour

Each item below was reproduced locally. Line numbers are current as of this audit.

### A. Truth constraints (highest risk, trivial fix)

**P1 — JD-implied metrics are explicitly authorized** (`stages/drafter.py:145`)

> "TIER 2 — JD-IMPLIED … If the JD provides a specific target (e.g., "5+ years of Python") … you MAY reflect
> these numbers … Example: JD says "5+ years experience with SQL" and candidate lists SQL → "5+ years of SQL
> experience"."

A requirement is not evidence of history. This directly contradicts `stages/drafter.py:173` in the same prompt
("✗ Hallucinated (BAD): Copying "Must have 5 years of Python" from Job Ad").

**P2 — Invented counts and scale authorized** (`stages/drafter.py:146`)

> "TIER 3 — REASONABLE SCALE … "Led project" → "Led cross-functional team of 6 engineers"."

**P3 — "Metric injection" is mandatory** (`stages/drafter.py:308-316`)

> "⚠️ METRIC INJECTION REQUIREMENT (CRITICAL — FAILURE = INCOMPLETE OUTPUT): You MUST weave AT LEAST 2 of the
> metrics listed above … DO NOT skip this step. Every experience must carry at least one concrete metric where
> available."

Combined with the extraction bug (M1) that supplies only ~⅓ of the real metrics, this is a direct pressure
gradient toward inventing numbers. The block also **hardcodes one real candidate's metrics** (`13-vessel`,
`$500K`, `10+ TB`, `30 hours`, `40%`) into a shared system prompt — that content can leak into other users'
resumes as a style example.

**P4 — Sparse input triggers experience invention** (`stages/drafter.py:254`)

> "You must EXPAND them into full bullets by **inferring standard industry tasks** associated with these
> roles/skills. Focus on **HOW the work was likely done**."

**P5 — New activity claims authorized** (`stages/drafter.py:135-138`)

> "If the JD mentions "deep learning internals analysis" and the candidate has PyTorch experience, you may write
> "Analyzed deep learning model internals using PyTorch"."

Listing PyTorch does not establish model-internals research. Contrast with the safe case in the same block
("database work" → "SQL"), which is terminology normalization, not a new activity.

**Fix (P1–P5):** replace the three tiers and the injection block with one evidence rule:

> Use a number only when it is attached to candidate-provided evidence. The JD and research may guide
> relevance and vocabulary — they may never supply accomplishments, durations, budgets, team sizes, or
> outcomes. If a useful metric is missing, leave the bullet unquantified; never estimate.

Delete the hardcoded metric examples and the "EXPAND / infer standard industry tasks" instruction (replace with
"you may use neutral, generic phrasing but may not assert tasks the source does not support").

---

### B. Silent data destruction (highest yield, cheap, invisible today)

**S1 — PII sanitizer flattens the whole resume** (`imaginator_new_integration.py:142`)

```python
result = re.sub(r'\s{2,}', ' ', result)   # runs on the FULL document
```

`\s` includes `\n`, so every blank line becomes a space. This executes at line 923, **before**
`parse_experiences()` at line 946 — and that parser is explicitly line-based
(`imaginator_flow.py:710`, "Works line-by-line"). Reproduced on a real-shape resume:

```
BEFORE: 15 lines, 0 blank-line loss
AFTER :  7 lines, 0 blank lines remaining
        "... Tacoma, WA 98405 | (253) 774-9031 PROFESSIONAL EXPERIENCE Cascade Power
         Solutions, LLC - Tacoma, WA | March 2020 - Present"
```

The `PROFESSIONAL EXPERIENCE` header is now glued to the previous line, so `in_experience_section` detection
and job-title boundary detection both degrade. Every downstream stage inherits the damage.

**Fix:** collapse horizontal whitespace only — `re.sub(r'[^\S\n]{2,}', ' ', result)` — and strip trailing
spaces per line. Add a regression test asserting line count is preserved.

**M1 — Metric extraction loses most real metrics** (`stages/drafter.py:274-287`)

`re.findall()` returns capture-group tuples; the code takes `m[0]`, which is frequently an empty optional group.
Reproduced against the Drafter's own documented examples:

| Source text | Extracted |
|---|---|
| `$500K in federal R&D funding` | `''` → dropped |
| `Reduced load time by 40%` | `40%` ✓ |
| `13 vessels` | **not matched** (`vessels` absent from `count_with_unit`) |
| `10+ TB of data` | **not matched** |
| `30 hours per week` | `30` (unit lost) |
| `200 users` | `200` (unit lost) |

Result: `['40%', '200', '30']` — the `$500K`, `13-vessel`, and `10+ TB` examples that the prompt literally
demonstrates are never supplied. The model is told to weave metrics it was never given, which is precisely the
condition that produces invention. Also: metrics are a flat global list with **no role ownership**.

**Fix:** use `re.finditer` with named groups and no optional leading group; attach each metric to its
`experience_id`; delete the "MUST weave 2" mandate.

**M2 — Metric validator deletes real metrics** (`stages/star_editor.py:1208`)

It removes any output metric whose literal `value+unit` string is absent from `original_resume_text`, and it
only inspects lines starting with `-`. Reproduced:

```
INPUT : "Reduced reporting overhead by 40% for NOAA's 13-vessel research fleet"
OUTPUT: "Reduced reporting overhead for NOAA's 13-vessel research fleet"   ← "by 40%" deleted
```

Triggered whenever the upstream text is empty or the writer rephrased. Two opposite failures in one function:
real metrics deleted from bullets, invented metrics in Summary/Skills/Projects **never checked at all** (those
lines don't start with `-`).

**Fix:** make it fail-open and non-destructive — never mutate the text; emit
`unsupported_metrics: [{text, experience_id, reason}]` for review and downstream policy. If a metric must be
removed, remove at generation time via the evidence ledger, not by string surgery on finished prose.

**M3 — Revision memo reports every metric as missing** (`atsScorer.js:397-404`)

```js
memo.missingMetrics = sourceMetrics.filter(
  (sm) => !JSON.stringify(scoreResult).toLowerCase().includes(sm.toLowerCase())
);
```

`scoreResult` (shape at `atsScorer.js:351-362`) **contains no draft text**, so the predicate is always true.
The regex also misses `13-vessel` and `10+ TB`. Reproduced: draft contains `40%`, memo still reports `40%` as
missing. Every revision pass then instructs "Add these metrics from profile"
(`canonicalPayload.js:378-379`), inviting duplicate or displaced numbers.

**Fix:** pass the draft text into `buildRevisionMemo`; compare against it; widen the metric regex; use the
evidence ledger IDs rather than string matching.

**I1 — Identity restored by list position** (`stages/drafter.py:401`)

```python
original_exp = original_experiences[i] if i < len(original_experiences) else {}
```

Dates, `start_date`, `end_date`, and `location` are re-attached by index. If the model reorders or drops a role,
one job's dates land on another job — the single most damaging resume error and completely invisible to any
keyword scorer.

**Fix:** require the model to echo a stable `experience_id`; join on it; treat company/title/dates/location as
immutable server-side fields and let the model rewrite bullets only.

**I2 — Input order decides what the writer sees** (`orchestrator.py:127-264`)

Up to 3 projects are appended as pseudo-experiences, then the first 6 non-education entries are kept. A relevant
project or an older highly-relevant role can be silently dropped before the writer ever sees it, and nothing is
logged about what was excluded.

**Fix:** explicit selection policy (recent employment always in; rank remaining achievements by *supported* JD
relevance; separate project budget; log `excluded: [{id, reason}]`).

---

### C. The evaluator cannot support the model choice

**E1 — Weights total 110, then clip to 100** (`benchmarks/v4_resume_writing_benchmark.py:446-447`)

`35+20+10+10+10+5+5+5+10 = 110`, then `min(total, 100)`. Reproduced: a run scoring **0/10 on Grounded Skill
Inference still reaches 100/100**. Category weaknesses are structurally invisible.

**E2 — 16 of 27 recorded runs failed a gate and still scored high**

Nine runs scored ≥95 with a failed gate — including all three GLM-5.1 runs (100.0 with `G10` fail):

```
OpenRouter Fusion     run1/2/3  score=100    fails=[G10]
GLM 5.1               run1/2     score=100    fails=[G10]
Qwen 3 235B Thinking  run1/3     score=100    fails=[G10]
Grok 4.3              run3       score=100    fails=[G10]
MiMo V2.5 Pro         run2       score=95.0   fails=[G10]
```

**E3 — G10 is a false-positive generator** (`v4:201-205`)

`resume_text.count('|') > 5` fires on ordinary `Role | Company | Dates` headers (reproduced: 7 pipes → fail).
16/27 runs "failed" ATS layout for correct formatting.

**E4 — G7 first-person gate cannot see "I"** (`v4:181`)

`lower` is lowercased but the pattern contains uppercase `I` and relies on `\b(I|my|me|we)`. Reproduced:
`"i built a data pipeline"` **not** matched; only `"we managed"` matched. Fix: `re.IGNORECASE` + drop the
verb-position requirement.

**E5 — "Factual fidelity" is keyword presence** (`v4:323-336`)

`employer_hits >= 4 and degree_hits >= 2 and cert_hits >= 3 → 10/10`. No per-bullet support check, no
date↔role binding, no numeric ownership. Any invention outside the blacklist passes.

**E6 — GSI judges inference against the output itself** (`v4:257-296`)

It looks for an evidence term *and* an adjacent skill **in the generated resume**. Self-referential: the model
is rewarded for writing both halves. The source profile must be the arbiter.

**E7 — Empty content is replaced by reasoning** (`v4:~496`)

```python
if not content or content.strip() == "": content = d["choices"][0]["message"].get("reasoning") or ""
```
A truncated or refused answer becomes a scored "resume". This should be a hard output failure.

**E8 — Version conflation.** Three different experiments must not be merged in narrative:
V2 = 18 models × 5 resumes, 110-pt parsing; V3 = 17 models, 100-pt writing
(ATS 30 / Fidelity 25 / Structure 15 / Bullets 15 / Alignment 15 — notebook cell 67);
V4 = 9 models × 3 runs, gates + 110-clipped rubric. V3's own headline was "all 17 models scored 25/25 on fact
fidelity", which is a statement about a keyword check, not about truthfulness.

---

## 3. Ranked plan

### Phase 0 — Truth + integrity fixes (≈2 h, $0, no deploy risk)

| # | Change | File | Effort | Why first |
|---|---|---|---|---|
| 1 | Replace TIER 2 / TIER 3 / METRIC INJECTION with one evidence rule | `stages/drafter.py:143-148, 308-316` | 30 m | Removes the license to invent |
| 2 | Delete hardcoded candidate metrics & "infer standard tasks" | `stages/drafter.py:254, 310-313` | 10 m | Cross-user leakage + invention |
| 3 | Fix sanitizer whitespace collapse | `imaginator_new_integration.py:142` | 10 m | Restores parser input |
| 4 | Fix metric extraction (`finditer`, named groups, `vessels`/`TB`) | `stages/drafter.py:274-287` | 30 m | Supplies real metrics |
| 5 | Make `_validate_metrics_against_input` non-destructive + all lines | `stages/star_editor.py:1208` | 20 m | Stops deleting truth |
| 6 | Fix `missingMetrics` to compare against the draft | `atsScorer.js:397` | 15 m | Stops bad revision orders |

**Do-not-deploy note:** #1–#2 change output shape (fewer numbers). Verify against 10 real resumes before
enabling broadly; expect word count to dip and `quantification_score` to fall — that is the intended direction.

**Definition of done (all must be automatic tests):**
- Prompt source contains no `TIER 2`, `TIER 3`, `METRIC INJECTION`, or `good company names`:
  `grep -c` returns 0.
- `sanitize_resume_pii("a\n\nb")` keeps `\n\n`.
- Metric extractor on the documented examples returns `{40%, 500K, 13 vessels, 10+ TB, 30 hours}`.
- Validator on the reproduction case returns text **byte-identical** to input plus a non-empty
  `unsupported_metrics` list.
- `buildRevisionMemo` returns `missingMetrics: []` for a draft containing all source metrics.

**Expected effect:** measurable drop in unsupported-claim rate on the same inputs; no model change needed to
see it.

### Phase 1 — Fix the evaluator, then re-score for free (≈1 h, $0)

| # | Change | File |
|---|---|---|
| 7 | Renormalize weights to sum 100 | `v4:321,446` |
| 8 | G10: detect real tables (`^\|?.*\|.*\|`, separator rows), not pipe count | `v4:201` |
| 9 | G7: `re.IGNORECASE`, match any first-person pronoun | `v4:181` |
| 10 | Remove reasoning-as-content fallback → hard failure | `v4:~496` |
| 11 | Per-bullet support check against a frozen fact list; date↔role binding | `v4:323` |
| 12 | GSI: score inference against the **profile**, not the resume | `v4:257` |

Then **re-score `results/v4_benchmark_results.json` offline with the fixed scorer**. The stored runs include the
gate results, so much of this is recomputable without new API calls; where per-bullet support needs the raw
text, it is already in the saved outputs.

**Definition of done:** no run can score ≥90 with a failed gate (assert in a test); re-scored leaderboard is
published with the old one alongside it, and the GLM "100.0, variance 0.00" claim is either reproduced or
retracted.

### Phase 2 — Evidence ledger + stable IDs (≈1 day, $0)

Give every experience, bullet, and metric a stable `exp_04_metric_01` identity and thread it through:

```json
{ "fact_id": "exp_04_metric_01", "experience_id": "exp_04",
  "source_text": "Secured $500K in federal R&D funding",
  "value": "500K", "unit": "USD", "meaning": "funding secured" }
```

- Drafter may only emit numbers whose `fact_id` it was given; unknown numbers are rejected at parse time
  (cheap, deterministic, no extra tokens).
- `I1` positional restore deleted; join on `experience_id`.
- `star_editor` gets the ledger and reports `unsupported_claims` instead of mutating prose.
- One canonical structured resume; derive markdown / plain text / PDF / DOCX from it. Today
  `star_editor` emits `final_markdown` **and** `final_plain_text` independently, and the frontend also has its
  own `docxGenerator.ts` markdown parser — three representations of the same facts.

### Phase 3 — Controlled comparison (≈$1, the only paid step)

Do this **after** Phases 0–2, or the numbers mean nothing.

- **Track A (writer only):** 5 verified candidate/JD pairs × 3 models × 3 reps = 45 runs. Identical frozen
  payload, identical ledger, identical schema.
- **Track B (architecture):** feed saved Track-A drafts to the current StarEditor; also render
  drafter→deterministic-renderer. Measures editorial gain *and* loss.
- **Track C (end-to-end):** PDF/DOCX → text re-extraction → compare employers, dates, metrics, section order,
  bullets against the canonical resume; page images for clipping/overlap.

Dataset already present in `dev_workspaces/resume_experiment/`:
`Holloway_ElecWA25.txt` (electrician), `Whitfield_AdminNC25.txt` (admin), plus the two answer keys. Add a
technical pair and a deliberately sparse resume; hold out one pair permanently.

**Cost estimate (measured from the recorded V4 runs):**

| Track | Runs | Est. spend |
|---|---|---|
| A — 45 writer runs (qwen3-coder / GLM-5.1 / Grok-4.3) | 45 | ~$0.19 |
| B — 45 editor passes on saved drafts (mercury-2) | 45 | ~$0.05 |
| C — export + re-extraction | — | $0 |
| **Total** | | **< $0.25** |

(The recorded V4 batch cost ~$1.2 for 27 runs, dominated by `openrouter/fusion` at $0.38/run. Dropping Fusion
makes a full re-run essentially free.)

### Do not do yet

- **Do not switch the Drafter to GLM-5.1** on the strength of the current 100.0. It scored 100.0 *with a failed
  gate*, at 131 s median latency vs Qwen's 15 s, and ~20× the cost. It is already fallback #1
  (`pipeline_config.py:29`), so production may be running it today **unmeasured** — first step is to *surface
  the actual model used* in the response, not to promote it.
- **Do not raise `MAX_DRAFTER_EXPERIENCES` past 6** or the token caps without a 1 GB memory test; that limit
  exists because 7+ experiences OOM'd the instance.

---

## 4. The one-sentence reframe

The question is not "which LLM writes the nicest resume" — it is "which model-and-pipeline combination produces
the strongest **truthful** resume from the evidence the customer actually supplied," and today the pipeline
deletes the evidence, invents the numbers, and then grades itself on keyword presence.

---

## Appendix — exact reproduction commands

```bash
python3 /tmp/audit_gates.py        # weight 110→100 clip; G7 misses "i built"; G10 pipe false positive;
                                   #   metric extraction returns only 3 of 6 real metrics
python3 /tmp/audit_validator.py    # "by 40%" deleted from a real bullet
python3 /tmp/audit_sanitizer.py    # 15 lines → 7 lines, all blank lines destroyed
node    /tmp/audit_memo.js         # every source metric reported missing though present in draft
```
