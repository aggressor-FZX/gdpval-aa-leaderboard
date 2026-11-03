# Imaginator DRAFTER — faithfulness results & spend reality

Two questions were asked. The answers point in opposite directions from where
the cost conversation usually goes.

## Part 1 — What the drafter actually does (read from `stages/drafter.py`)

The drafter is **not** an author. It rewrites raw experience notes into STAR
bullets under hard constraints:

| Constraint | Source line |
|---|---|
| Company names must match input exactly | TRUTH CONSTRAINT 1 |
| Only technologies named in the input | TRUTH CONSTRAINT 3 |
| Metrics only from a VERIFIED METRICS list, value + unit together | TRUTH CONSTRAINT 5 |
| Bullets 15–25 words, strong verb first | STYLE RULES 1, 4 |
| "A bullet without a metric is NOT a failure" | METRIC RULE |
| Output JSON with `rewritten_experiences` | output schema |

Production config: `OR_SLUG_DRAFTER = "qwen/qwen3-coder"`, temp 0.3,
`max_tokens=6000`.

So the measurable thing is **faithfulness + format**, not prose quality. A model
that writes beautiful bullets and invents "reduced latency 65%" has failed, and
a generic prose score would reward it.

## Part 2 — Drafter contest result (n=4 per model, $0.20 total)

| model | clean runs | fabricated items | metric errors | 15–25w band | strong verb | $/run |
|---|---|---|---|---|---|---|
| **Kimi K3.1 Pro** | **4/4 (100%)** | **0** | **0** | **100%** | **94%** | $0.04344 |
| **Qwen3 Coder (INCUMBENT)** | 3/4 (75%) | 2 | 0 | **0%** | 78% | **$0.00046** |
| Claude Haiku 5.5 | 2/4 (50%) | 11 | 0 | 100% | 68% | $0.00205 |
| GLM 5.3 | 2/4 (50%) | 5 | 0 | 3% | 78% | $0.00064 |
| MiniMax M3.1 Flash | 0/4 (0%) | 24 | 0 | 100% | 93% | $0.00041 |

### The two findings that matter

**1. The incumbent has a real, specific defect — and it is not fabrication.**

`qwen3-coder` fabricates least among the cheap models (2 items in 4 runs) but its
bullets average **6–10 words against a spec of 15–25**. Band compliance is
**0%**. Its typical output:

```
[ 8w] Built resume parsing pipeline processing incoming candidate documents.
[ 9w] Reduced parsing step duration by 40% through refactored workflows.
[ 6w] Managed archived document datasets at scale.
```

Every bullet is a fragment. The prompt asks for 15–25 words and the model
ignores it consistently. This is a **prompt-compliance failure on a spec the
model was explicitly given**, and it is invisible to any score that only checks
facts.

**2. Only Kimi K3.1 Pro is both faithful and format-compliant.**

4/4 clean, zero fabrication, 100% band compliance, 94% strong verbs. No other
model achieves both. MiniMax M3.1 Flash has the best *shape* (100% band, 93%
strong verbs) and the worst *faithfulness* (24 fabricated items, 0/4 clean) —
it writes beautiful bullets full of things the candidate never did. That is
precisely the failure mode the drafter's constraints exist to prevent, and
precisely what a prose-quality benchmark would rank first.

### But Kimi costs 94×

Kimi is $0.04344/run vs the incumbent's $0.00046 — **94× more expensive** for
the same number of bullets.

The honest recommendation is therefore **not** "switch to Kimi":

- **Keep `qwen3-coder`.** It is the most faithful cheap model. Its only defect
  (short bullets) is fixable by making the constraint machine-checkable rather
  than trusting the model to obey a sentence in the prompt — pad to 15 words or
  retry, which the drafter already has the plumbing for (`max_tokens`,
  `temperature_override`).
- **Do not switch to MiniMax M3.1 Flash at any price.** 0/4 clean, 24 invented
  items. It is the trap this harness exists to catch.
- **Consider Kimi only if bullet length is being fought at the pipeline level.**
  It is the one model that satisfies the format contract unaided, but 94× cost
  to avoid a post-processing rule is a bad trade.

## Part 3 — Spend: the drafter is not the problem

30-day window (2026-10-04 → 2026-11-02), **$166.20** total.

| model | requests | spend | share | what it is |
|---|---|---|---|---|
| openai/gpt-6.1-sol | 666 | $39.02 | **23.5%** | development chat |
| openai/gpt-6.1-terra | 1,891 | $33.74 | **20.3%** | development chat |
| deepseek/deepseek-v4.1-flash | 8,905 | $26.23 | **15.8%** | `/coder` daemon (Wafer, max effort) |
| anthropic/claude-haiku-5.5 | 921 | $20.24 | **12.2%** | development |
| z-ai/glm-5.3 | 668 | $10.61 | 6.4% | development |
| openai/gpt-4o | 1,176 | $5.23 | 3.1% | legacy |
| … | | | | |

**All Imaginator/application stages combined: ~$2.82 = 1.7% of spend.**
The drafter alone is **$0.20 = 0.15%**.

Per-key spend:

| key | monthly | note |
|---|---|---|
| **fast_value_model_keys** | **$62.20** | largest active spender |
| Cogito-Metric Resume | $6.11 | |
| jan19_cogito_key2 | $1.52 | |
| Jan19_cogito_key1 | $0.92 | |

### So: which model is costing a lot?

**Not any Imaginator model.** The cost is in development/agenting traffic:

1. **`gpt-6.1-sol` + `gpt-6.1-terra` = $72.76 (43.8%)** — the two most expensive
   things on the account, both single-digit-thousands of requests at
   $0.039–0.075 per 1k output tokens. These are chat/development, not product.
2. **`deepseek-v4.1-flash` on Wafer at `max` effort = $26.23** over **8,905
   requests**. This is the `/coder` daemon. At $0.00408/1k output it is 5×
   the cost of the drafter per token.
3. **`fast_value_model_keys` at $62.20/month** is the key to investigate first —
   it is the only key with material recurring spend.

### Which to consider for replacement

| priority | what | why | candidate |
|---|---|---|---|
| 1 | `fast_value_model_keys` traffic | $62.20/mo, unattributed | pull `/api/v1/activity` per key window to name the workflow |
| 2 | `gpt-6.1-terra` ($33.74) | 1,891 requests, $0.039/1k out | the contest found cheaper models within noise of far stronger baselines |
| 3 | `gpt-6.1-sol` ($39.02) | highest $/1k out at 0.0746 | significant 4-model beat it in the free-authoring contest |
| **not worth it** | Imaginator stages ($2.82) | 1.7% of spend | optimising this cannot move the bill |

**The blunt version:** switching every Imaginator model to the cheapest
available option would save at most **$2.82/month**. Switching `gpt-6.1-terra`
alone could save an order of magnitude more. The drafter question is worth
answering for *quality* reasons — its 0% band compliance is a real defect — but
it is not a cost lever.

## Method corrections made while doing this

1. **`rag` matched inside `storage`.** Substring matching flagged a faithful
   response as fabricated. Fixed with word-boundary regexes for all JD-only
   technology terms.
2. **`quantification_score: 0.33` was counted as a fabricated metric.** The
   scorer read the whole JSON blob; it now scans bullet text plus `metrics_used`
   and rationale only.
3. **A precedence bug in the `clean` expression** made it depend only on the
   last clause. Fixed and covered by a self-test (faithful → clean, fabricated
   → caught).

## Caveats

- **n=4 per model.** Kimi's 4/4 is clean but a 4-run perfect record is still
  consistent with a ~10% failure rate. Treat 100% as "no failures observed".
- **One fixture.** A sparse two-job profile with two verified metrics. A denser
  profile gives fabrication less room to hide; a sparser one gives it more.
- **The golden-bullet library and seniority verb tables are omitted** from the
  reconstructed prompt. Every TRUTH CONSTRAINT and the evidence boundary are
  preserved, so the faithfulness test is faithful to the contract, but absolute
  scores are not production-identical.
- **Activity rows carry no `api_key_name`**, so per-key attribution of model
  spend is unavailable from that endpoint. Key totals come from `/api/v1/keys`.

Figures: `figures/drafter_faithfulness.png`, `figures/free_authoring_contest.png`.
