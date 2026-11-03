## 3. Test B — full resume: faithfulness AND structure

The task is the drafter's real job extended to a whole document: rewrite the source history into a complete resume with three required sections, reverse-chronological jobs, dates copied exactly, education years exact, certification dates exact, and ATS-parseable plain text.

Two contracts are scored **separately** and both must hold to pass. They fail independently, and the fix differs:

| contract | checks |
|---|---|
| **faithfulness** | no invented technology, no invented company, no unverified number, no unit stripped |
| **structure** | required sections present, reverse-chronological order, employment dates exact, education years exact, cert dates exact, plain text (no markdown tables/fences) |

40 variants, 116 scored runs, **$0.50**. Figure: `figures/drafter_fullresume.png`.

**35 variants passed every run.** 4 passed some, 1 passed none.

### Ranking — pass rate over 3 runs

| # | variant | n | pass | faith | struct | truncated | 15–25w band | $/run | Test A |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Qwen3.7 Plus | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00592 | 91.9 |
| 2 | MiniMax-M3 | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00252 | 91.7 |
| 3 | MiMo-V2.6-Pro | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00070 | 90.5 |
| 4 | Qwen3 Next 80B A3B Instruct | 3 | **100%** | 3/3 | 3/3 | 0/3 | 33% | $0.00041 | 90.0 |
| 5 | Qwen3.6 35B A3B (Reasoning) | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00053 | 89.8 |
| 6 | Inkling Small | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00533 | 89.7 |
| 7 | Inkling (xhigh) · xhigh | 3 | **100%** | 3/3 | 3/3 | 0/3 | 95% | $0.02413 | 88.6 |
| 8 | Qwen3 Coder Next | 3 | **100%** | 3/3 | 3/3 | 0/3 | 4% | $0.00032 | 88.4 |
| 9 | Nemotron 3 Ultra 550B | 3 | **100%** | 3/3 | 3/3 | 0/3 | 90% | $0.00665 | 87.5 |
| 10 | DeepSeek V4.1 Flash (max) · xhigh | 3 | **100%** | 3/3 | 3/3 | 0/3 | 89% | $0.00033 | 86.8 |
| 11 | Qwen3.5 9B (Reasoning) | 3 | **100%** | 3/3 | 3/3 | 0/3 | 7% | $0.00008 | 86.4 |
| 12 | GLM-5.3-Flash | 3 | **100%** | 3/3 | 3/3 | 0/3 | 29% | $0.00011 | 86.2 |
| 13 | DeepSeek V4.1 Flash 1017 (max) · xhigh | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00035 | 85.6 |
| 14 | gpt-oss-20b (High) | 3 | **100%** | 3/3 | 3/3 | 0/3 | 0% | $0.00002 | 85.3 |
| 15 | DeepSeek V4.1 Flash (incumbent) · default | 3 | **100%** | 3/3 | 3/3 | 0/3 | 90% | $0.00035 | 84.1 |
| 16 | GPT-3.5 Turbo | 3 | **100%** | 3/3 | 3/3 | 0/3 | 14% | $0.00154 | 84.1 |
| 17 | MiniMax-M3.1-Flash | 3 | **100%** | 3/3 | 3/3 | 0/3 | 90% | $0.00024 | 83.3 |
| 18 | gpt-oss-120b (High) | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00021 | 82.9 |
| 19 | Qwen3 Omni 30B A3B (Reasoning) | 3 | **100%** | 3/3 | 3/3 | 0/3 | 0% | $0.00121 | 82.8 |
| 20 | Nemotron 3.5 Super VL | 3 | **100%** | 3/3 | 3/3 | 0/3 | 0% | $0.00017 | 82.7 |
| 21 | LongCat 2.0 | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00396 | 81.6 |
| 22 | Hy3 | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00186 | 79.9 |
| 23 | DeepSeek V4 Flash Vision (Max) | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00190 | 78.8 |
| 24 | Qwen3.8 27B (xhigh) · xhigh | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00462 | 78.8 |
| 25 | Qwen3.8 27B (Xhigh) · default | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00241 | 77.7 |
| 26 | Gemma 4 31B (Non-reasoning) | 3 | **100%** | 3/3 | 3/3 | 0/3 | 94% | $0.00021 | 76.7 |
| 27 | GPT-5.4 mini (non-reasoning) | 3 | **100%** | 3/3 | 3/3 | 0/3 | 75% | $0.00197 | 76.3 |
| 28 | Beam 1.0 | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00270 | 75.6 |
| 29 | Llama 4 Maverick | 3 | **100%** | 3/3 | 3/3 | 0/3 | 14% | $0.00034 | 74.4 |
| 30 | GPT-6.1 Sol (max) · xhigh | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.01769 | 74.2 |
| 31 | Qwen3.8 Max (0902) | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.02089 | 73.8 |
| 32 | Llama 3.3 Instruct 70B | 3 | **100%** | 3/3 | 3/3 | 0/3 | 0% | $0.00020 | 69.9 |
| 33 | Granite 4.2 8B | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00117 | 68.6 |
| 34 | Gemma 4 26B A4B (Reasoning) | 3 | **100%** | 3/3 | 3/3 | 0/3 | 39% | $0.00007 | 68.4 |
| 35 | Muse Glimmer (high) · high | 3 | **100%** | 3/3 | 3/3 | 0/3 | 100% | $0.00391 | 67.9 |
| 36 | Solar Pro 4 | 2 | **50%** | 2/2 | 1/2 | 0/2 | 0% | $0.00019 | 79.1 |
| 37 | NVIDIA Nemotron 3 Nano 30B A3B (Reasoning) | 2 | **50%** | 1/2 | 1/2 | 0/2 | 100% | $0.00130 | 74.4 |
| 38 | Gemini 3.8 Flash (high) · high | 3 | **33%** | 2/3 | 1/3 | 3/3 | 67% | $0.03125 | 88.0 |
| 39 | Llama 4 Scout | 3 | **33%** | 3/3 | 1/3 | 0/3 | 0% | $0.00026 | 73.2 |
| 40 | Reka Flash 3 | 1 | **0%** | 0/1 | 0/1 | 1/1 | 37% | $0.00174 | 25.1 |

`pass` = faithfulness-clean AND structurally-clean on the same run.
`faith`/`struct` are counts of clean runs out of n.

### Variants that did not hold the contract

- **Reka Flash 3** — 0% pass. invented technology (1/1), unverified number (1/1), missing section (1/1), wrong employment dates (1/1), wrong education years (1/1), wrong cert dates (1/1)
- **Solar Pro 4** — 50% pass. wrong cert dates (1/2)
- **NVIDIA Nemotron 3 Nano 30B A3B (Reasoning)** — 50% pass. wrong employment dates (1/2)
- **Gemini 3.8 Flash (high)** — 33% pass. wrong cert dates (2/3), unverified number (1/3), missing section (1/3), wrong employment dates (1/3), wrong education years (1/3)
- **Llama 4 Scout** — 33% pass. wrong cert dates (2/3)

### What this says

1. **The full-resume structure is not hard when it is specified.** Most variants copied every date and year exactly. That is a genuine finding, and it means the *earlier* bullets-only task was the harder one — it asked for JSON and a word band with no document structure to lean on.

2. **The word band is the real differentiator.** Several models passed structure perfectly and failed the 15–25 word band almost totally (see the band column: 0%, 4%, 7%). Structure and prose discipline are unrelated skills.

3. **A reasoning leak is a hard failure.** One variant emitted its internal word-count deliberation instead of a resume — no sections, no dates, no bullets. It is scored as a total failure, correctly: reasoning text in a user-facing field is a production incident.

4. **Test A score does not predict Test B.** The seed of the ranking is similar because both reward competence, but failures here cut across price: cheap models pass, and one expensive model failed outright.

### Excluded by request

Five variants were skipped because Test A found them significantly **worse** than the incumbent at a higher price per run — spending on them would not change any decision:

| variant | Test A | $/run | Δ vs control |
|---|---|---|---|
| Claude Haiku 5.5 (high) | 73.8 | $0.00159 | −10.3 |
| Kimi K3.1 Pro | 73.5 | $0.03803 | −10.6 |
| Grok 4.7 (xhigh) | 72.0 | $0.16239 | −12.1 |
| Grok 4.6 (xhigh) | 71.2 | $0.03602 | −12.8 |
| GPT-6 Luna (xhigh) | 71.2 | $0.00394 | −12.9 |

### Why this replaced the earlier bullets-only test

The first Test B asked for JSON bullets only. It could not see a wrong graduation year, a reordered job history, or a missing section, because it never asked for them. It is superseded here, and its five-model result is kept in `results/drafter_faithfulness.json` as history, not as a current ranking.

### Scorer integrity

`python resume_writing_v2/test_scorers.py` asserts the scorers fire on known-bad input and stay quiet on known-good input. Six silent bugs were caught this way during this round, each of which would have produced a confidently wrong ranking:

| bug | wrong conclusion it produced |
|---|---|
| plain-text resumes scored with the JSON scorer | all 43 variants failed faithfulness |
| `04/2024` parsed as the numbers 4 and 2024 | correct dates flagged as fabricated metrics |
| unmarked bullets not extracted | models that wrote 7 good bullets scored 0 |
| education/cert lines counted as bullets | in-band compliance artificially 0% |
| character window instead of line | adjacent credentials shared years, reported as invented |
| dates searched only below the company | correct layouts marked failed |
| fixed above-then-below line preference | below-layout certs borrowed the previous cert's date |
| `2016`, `1000`, `4.0` in `VERIFIED_METRICS` but absent from the profile | a model could invent that graduation year and be **credited** for it |

### The year rule

The education years and certificate dates in this test are **synthetic** and belong to no real person. They are also never reachable from the production prompt: `task.build_prompt()` uses `CANDIDATE_PROFILE`, which contains no graduation or certificate years. See METHODOLOGY.md "Fixture provenance — the year rule" for why this is treated as an invariant rather than a convention.
