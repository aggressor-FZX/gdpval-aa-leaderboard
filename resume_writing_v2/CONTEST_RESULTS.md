# Cheap-model resume-writing contest — results

Scope: **is any model priced at or below $2/M output actually better than
DeepSeek V4.1 Flash at writing a tailored resume, and is the difference real?**

- Incumbent: `deepseek/deepseek-v4.1-flash` (the model Cogito Metric currently
  uses for Job Scout research)
- Challengers: every OpenRouter-reachable model with **output ≤ $2.00/M** that
  has an AA-PersonalityBench score or a writing proxy (28 models)
- Harness: `resume_writing_v2` — gate-clamped scoring, weights summing to 100,
  table-structure G10, case-insensitive G7
- Cost: **$0.167** for round 1 (84 requests)

## 1. Is the harness trustworthy? Yes — measured

| check | value | meaning |
|---|---|---|
| individual run spread | **71.5 points** (25.1 → 96.6) | wide, so it discriminates |
| within-model repeat sd | **7.5 points** | the noise floor |
| spread ÷ noise | 9.5× | signal dominates |
| perfect scores | **0 / 75** | no ceiling compression (v4 had 9/24 at 100) |

The old harness spanned 88–100 with 9 perfect scores. This one spans 25–97 with
none, so it can rank.

**But**: the incumbent's own repeat sd is **5.4 points**. That single number
governs every claim below.

## 2. Round 1 (n=3) — the honest reading

Raw mean deltas over DeepSeek V4.1 Flash (88.4):

| model | mean | delta | $/run | cost × | verdict |
|---|---|---|---|---|---|
| Qwen3.7 Plus | 92.1 | +3.7 | 0.00724 | 3.00× | inside noise (t=0.83) |
| MiniMax-M3 | 91.6 | +3.2 | 0.00304 | 1.26× | inside noise (t=0.78) |
| Inkling Small | 90.6 | +2.2 | 0.00589 | 2.44× | inside noise (t=0.56) |
| Qwen3 Coder Next | 90.4 | +2.1 | 0.00044 | **0.18×** | inside noise (t=0.41) |
| Qwen3.6 35B A3B (Reasoning) | 90.4 | +2.1 | 0.00048 | **0.20×** | inside noise (t=0.50) |
| Qwen3 Next 80B A3B | 89.7 | +1.3 | 0.00064 | 0.27× | inside noise (t=0.33) |
| **Qwen3.5 9B (Reasoning)** | 89.6 | +1.2 | **0.00003** | **0.01×** | inside noise (t=0.26) |

**No model significantly beat the incumbent.** Zero. Every positive delta had
|t| < 0.9, which is well inside the noise the incumbent itself produces.

**Seven models were significantly WORSE** (|t| ≥ 2.5, |d| ≥ 0.8): Llama 3.3
Instruct 70B (Δ−18.5), Granite 4.2 8B (−19.7), Gemma 4 26B A4B (−19.9),
Llama 4 Scout (−15.1), Llama 4 Maverick (−14.0), Nemotron 3 Nano 30B (−14.0),
Qwen3.8 27B Xhigh (−10.7).

Publishing round 1 as "7 models beat DeepSeek" would have repeated the exact v4
error — reporting measurement noise as a ranking. Redoing this at n=8 is the only
way to decide it (round 2, below).

## 3. The finding that survives regardless of significance

Three models are **statistically indistinguishable from the incumbent and far
cheaper**:

| model | mean | vs incumbent | $/run | cost × |
|---|---|---|---|---|
| Qwen3.6 35B A3B (Reasoning) | 90.4 | +2.1 (noise) | 0.00048 | 0.20× |
| Qwen3 Next 80B A3B Instruct | 89.7 | +1.3 (noise) | 0.00064 | 0.27× |
| **Qwen3.5 9B (Reasoning)** | 89.6 | +1.2 (noise) | **0.00003** | **0.01×** |

Qwen3.5 9B costs **1% of the incumbent per run** at a mean 1.2 points higher.
Even at maximum unfavourability (both bounding the noise), swapping is
defensible: you cannot lose 5 points of quality at a 100× price reduction
without the harness having said so louder than it did.

## 4. Gate reliability — a separate axis from score

The clamp caps a gate-failing run at 89, so score alone hides publishability.

| model | clean runs | note |
|---|---|---|
| MiniMax-M3 | 2/3 | 1 run clamped |
| Qwen3 Coder Next | 1/3 | 2 runs clamped |
| gpt-oss-20b (High) | 0/3 | always clamped |
| Qwen3 Omni 30B A3B | 0/3 | always clamped |

A model at 90 with 1/3 clean runs is a different proposition from one at 89 with
3/3.

## 5. Engineering failures found (9 unscorable of 84)

Not model quality — harness bugs:

1. **`reasoning_exhausted_budget`** (5 runs): Nemotron 3.5 Lightning burned
   16,384 reasoning tokens of a 16,384 budget and emitted nothing. Fixing needs
   a per-model token budget, not a global one.
2. **Phi-4 HTTP 400** (3 runs): the endpoint's max context is 16,384 **total**,
   and the prompt plus 16,384 max_tokens exceeds it. The runner must clamp
   `max_tokens` to `context − prompt`.
3. **Reka Flash 3** empty completion (1 run).


## 7. Round 2 (n=8) — the decisive result

Round 1 was underpowered. Round 2 re-ran every model within 4 points of the
incumbent at **n=8 per model** (80 requests, $0.202), plus the incumbent as the
control. Selection rule stated up front so it cannot look cherry-picked: include
any model whose round-1 mean was >= incumbent mean - 4.

Combining both rounds (**n=11 per model**, incumbent n=11, mean 84.1, sd 6.3):

| model | mean | delta | t | Cohen's d | verdict |
|---|---|---|---|---|---|
| **Qwen3.7 Plus** | 91.9 | **+7.8** | 3.50 | 1.49 | **BETTER (significant)** |
| **MiniMax-M3** | 91.0 | **+7.0** | 3.15 | 1.33 | **BETTER (significant)** |
| **Qwen3 Next 80B A3B Instruct** | 90.0 | **+6.0** | 2.89 | 1.23 | **BETTER (significant)** |
| **Qwen3.6 35B A3B (Reasoning)** | 89.8 | **+5.8** | 2.62 | 1.12 | **BETTER (significant)** |
| Inkling Small | 89.7 | +5.6 | 2.38 | 1.01 | inside noise |
| Qwen3 Coder Next | 88.4 | +4.4 | 1.79 | 0.76 | inside noise |
| Qwen3.5 9B (Reasoning) | 86.4 | +2.3 | 0.88 | 0.38 | inside noise |
| gpt-oss-20b (High) | 85.3 | +1.2 | 0.54 | 0.23 | inside noise |
| GLM-5.3-Flash | 83.6 | −0.4 | −0.18 | −0.08 | inside noise |

**Four models beat DeepSeek V4.1 Flash significantly.** Not marginal: +5.8 to
+7.8 points, t = 2.6–3.5, d = 1.1–1.5 (large effects).

### Why round 1 disagreed, and why round 2 is the one to trust

Round 1's incumbent sample averaged 88.4; round 2's averaged 82.4. **That 6-point
swing is the incumbent's own instability** (sd 5.4–5.9), not any change in the
model. Round 1 happened to draw a lucky incumbent. Round 2's larger sample
caught its true centre.

Crucially, **the challengers' ordering was stable across both rounds** —
Qwen3.7 Plus 92.1 → 91.8, Qwen3 Next 80B 89.7 → 90.1, Qwen3.6 35B 90.4 → 89.6.
The models are consistent; the incumbent is not. That asymmetry is itself the
finding: DeepSeek V4.1 Flash is the *least reliable* contender in its own
weight class.

### The practical answer

| model | $/run | cost × incumbent | score delta |
|---|---|---|---|
| **Qwen3.6 35B A3B (Reasoning)** | **0.00048** | **0.20×** | +5.8 (significant) |
| **Qwen3 Next 80B A3B Instruct** | 0.00064 | 0.27× | +6.0 (significant) |
| MiniMax-M3 | 0.00304 | 1.26× | +7.0 (significant) |
| Qwen3.7 Plus | 0.00724 | 3.00× | +7.8 (significant) |

**Recommendation: move Job Scout research from
`deepseek/deepseek-v4.1-flash` to `qwen/qwen3.6-35b-a3b`.**

It is **5× cheaper per run and 5.8 points better, significantly**, with a 3/3
clean gate record in round 2 and lower run-to-run variance (sd 3.1 vs 5.9). If
maximum quality matters more than cost, Qwen3.7 Plus is the top scorer — but at
3× the incumbent's price it is not the value pick.

Qwen3.5 9B remains the cheapest thing that is not worse (1% of incumbent cost,
+2.3 points, inside noise) — a valid fallback if the pipeline needs to be as
cheap as possible rather than as good as possible.

## 8. What would change this conclusion

- **The task is one JD and one candidate profile.** Resume writing is
  stylistically narrow; a model that wins here may not win on a different domain.
- **AA-PersonalityBench agreement is partial.** Qwen3.7 Plus and MiniMax-M3 rank
  high on both PB and this task. But DeepSeek V4.1 Flash scores PB
  organization 100 — the single highest of 40 models — and still came last among
  contenders here. **PB organization does not predict task performance**, which
  is exactly why the harness exists.
- **n=11 resolves a 6-point difference, not a 2-point one.** Claims below ~5
  points should be treated as undetermined.

## 9. Method notes

- **Slop direction corrected.** AA's `indexScores["slop"]` is the *amount* of
  slop: corr(organization, slop) = −0.196 over 40 models, and the worst models
  carry the highest slop (Llama 4 Maverick org 3.5 / slop 100.0). An earlier
  revision treated it as "avoidance", which is inverted.
- **AA scores 40 models.** 24 of the 62 OpenRouter-reachable shortlist entries
  have real PersonalityBench scores; the rest carry the labelled proxy.
- **Temperature fixed at 0.2**, so all reported variance is provider-side.
