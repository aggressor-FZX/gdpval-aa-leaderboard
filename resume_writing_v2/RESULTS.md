# RESULTS — resume-writing model evaluation

Consolidated, generated document. Regenerate with `python resume_writing_v2/compile_results.py`.

All experiments in this document cost **$3.03** in API calls: $2.33 for test A across three rounds, $0.50 for test B, and $0.19 for the superseded bullets-only drafting test.

Figure: `figures/price_vs_quality.png`  
Machine-readable: `results/consolidated.json`

---

## 1. What was measured

Two tests. They answer different questions and are not interchangeable.

| test | task | scored on |
|---|---|---|
| **A — free-authoring** | write a full resume from a verified profile + a Boeing Defense GenAI DS job description | gate-clamped 100-point rubric |
| **B — drafter faithfulness** | rewrite raw experience notes into STAR bullets under an evidence boundary | fabrication / metric fidelity / format |

AA-PersonalityBench is reported as a **prior**, never as a grade. It was checked against the measured scores and does not predict them (§5).

### Rounds

| round | set | runs/model | effort | file |
|---|---|---|---|---|
| 1 | every OpenRouter model with output ≤ $2/M | 3 | provider default | `results/contest_cheap_r1.json` |
| 2 | round-1 contenders within 4 pts of control | 8 | provider default | `results/contest_cheap_r2.json` |
| 3 | the named high/low-cost set | 4 | explicit (`xhigh`/`high`/default) | `results/contest_cheap_r3.json` |

A **variant** is `(model_id, reasoning_effort)`. The same family at `xhigh` and at provider default is a different model and is never pooled.

---

## 2. Test A — cost vs quality, all measured variants

48 variants scored at least one run: **4 significantly better** than the control and **14 significantly worse**. Everything else is inside noise.

Control = **DeepSeek V4.1 Flash at provider default** (n=11, mean 84.1). Significance = Welch test, |t| ≥ 2.5 **and** |Cohen's d| ≥ 0.8. `low_n` means fewer than 3 scored runs — not a result.

| model · effort | n | mean | sd | Δ vs ctrl | t | $/run | in $/M | out $/M | verdict |
|---|---|---|---|---|---|---|---|---|---|
| Qwen3.7 Plus | n=11 | 91.9 | 3.3 | +7.8 | 3.50 | $0.00713 | $0.320 | $1.280 | significant |
| MiniMax-M3 | n=14 | 91.7 | 3.3 | +7.7 | 3.50 | $0.00446 | $0.300 | $1.200 | significant |
| MiMo-V2.6-Pro | n=4 | 90.5 | 3.6 | +6.4 | 2.37 | $0.00056 | $0.435 | $0.870 | inside noise |
| Qwen3 Next 80B A3B Instruct | n=11 | 90.0 | 1.5 | +6.0 | 2.89 | $0.00066 | $0.090 | $1.100 | significant |
| Qwen3.6 35B A3B (Reasoning) | n=11 | 89.8 | 3.0 | +5.8 | 2.62 | $0.00053 | $0.100 | $0.900 | significant |
| Inkling Small | n=11 | 89.7 | 4.1 | +5.6 | 2.38 | $0.00647 | $0.450 | $1.200 | inside noise |
| Inkling (xhigh) · xhigh | n=4 | 88.6 | 3.6 | +4.5 | 1.67 | $0.01818 | $1.000 | $4.050 | inside noise |
| Qwen3 Coder Next | n=11 | 88.4 | 4.6 | +4.4 | 1.79 | $0.00045 | $0.120 | $0.800 | inside noise |
| Gemini 3.8 Flash (high) · high | n=4 | 88.0 | 3.3 | +3.9 | 1.51 | $0.01302 | $0.825 | $4.125 | inside noise |
| Nemotron 3 Ultra 550B | n=4 | 87.5 | 12.9 | +3.5 | 0.52 | $0.00406 | $0.600 | $2.400 | inside noise |
| Mistral Large 4 Preview | n=4 | 87.3 | 5.1 | +3.3 | 1.01 | $0.01793 | $0.700 | $2.100 | inside noise |
| DeepSeek V4.1 Flash (max) · xhigh | n=4 | 86.8 | 3.4 | +2.7 | 1.05 | $0.00028 | $0.045 | $0.500 | inside noise |
| Qwen3.5 9B (Reasoning) | n=11 | 86.4 | 5.8 | +2.3 | 0.88 | $0.00003 | $0.170 | $0.250 | inside noise |
| GLM-5.3-Flash | n=15 | 86.2 | 6.0 | +2.2 | 0.85 | $0.00061 | $0.029 | $0.092 | inside noise |
| DeepSeek V4.1 Flash 1017 (max) · xhigh | n=4 | 85.6 | 6.3 | +1.5 | 0.41 | $0.00027 | $0.150 | $0.600 | inside noise |
| gpt-oss-20b (High) | n=11 | 85.3 | 3.4 | +1.2 | 0.54 | $0.00002 | $0.030 | $0.130 | inside noise |
| DeepSeek V4.1 Flash (incumbent) · default | n=11 | 84.1 | 6.7 | +0.0 | — | $0.00246 | $0.045 | $0.500 | control |
| GPT-3.5 Turbo | n=4 | 84.1 | 1.4 | +0.1 | 0.03 | $0.00198 | $1.000 | $2.000 | inside noise |
| MiniMax-M3.1-Flash | n=4 | 83.3 | 0.9 | -0.8 | -0.37 | $0.00036 | $0.150 | $0.600 | inside noise |
| gpt-oss-120b (High) | n=3 | 82.9 | 3.2 | -1.1 | -0.41 | $0.00021 | $0.150 | $0.600 | inside noise |
| Qwen3 Omni 30B A3B (Reasoning) | n=3 | 82.8 | 3.9 | -1.3 | -0.43 | $0.00064 | $0.120 | $0.500 | inside noise |
| Nemotron 3.5 Super VL | n=4 | 82.7 | 1.4 | -1.4 | -0.66 | $0.00030 | $0.150 | $0.500 | inside noise |
| LongCat 2.0 | n=3 | 81.6 | 6.6 | -2.5 | -0.57 | $0.01076 | $0.300 | $1.200 | inside noise |
| Hy3 | n=3 | 79.9 | 6.5 | -4.1 | -0.97 | $0.00349 | $0.083 | $0.330 | inside noise |
| Solar Pro 4 | n=3 | 79.1 | 8.8 | -5.0 | -0.91 | $0.00039 | $0.150 | $0.600 | inside noise |
| DeepSeek V4 Flash Vision (Max) | n=2 | 78.8 | 5.4 | — | — | $0.00511 | $0.216 | $0.647 | low_n |
| Qwen3.8 27B (xhigh) · xhigh | n=3 | 78.8 | 4.8 | -5.3 | -1.54 | $0.01546 | $0.150 | $1.875 | inside noise |
| Qwen3.8 27B (Xhigh) · default | n=2 | 77.7 | 2.1 | — | — | $0.00297 | $0.150 | $1.875 | low_n |
| Gemma 4 31B (Non-reasoning) | n=3 | 76.7 | 4.6 | -7.3 | -2.20 | $0.00020 | $0.200 | $0.400 | inside noise |
| GPT-5.4 mini (non-reasoning) | n=4 | 76.3 | 2.2 | -7.8 | -3.41 | $0.00244 | $0.750 | $4.500 | significant |
| Beam 1.0 | n=4 | 75.6 | 1.9 | -8.4 | -3.79 | $0.00568 | $0.250 | $1.000 | significant |
| NVIDIA Nemotron 3 Nano 30B A3B (Reasoning) | n=6 | 74.4 | 8.4 | -9.7 | -2.43 | $0.00060 | $0.060 | $0.240 | inside noise |
| Llama 4 Maverick | n=7 | 74.4 | 3.0 | -9.7 | -4.21 | $0.00026 | $0.188 | $0.652 | significant |
| GPT-6.1 Sol (max) · xhigh | n=4 | 74.2 | 12.0 | -9.9 | -1.56 | $0.06311 | $2.000 | $10.000 | inside noise |
| Claude Haiku 5.5 (max) · high | n=4 | 73.8 | 3.4 | -10.3 | -3.89 | $0.00159 | $0.100 | $0.500 | significant |
| Qwen3.8 Max (0902) | n=4 | 73.8 | 1.6 | -10.3 | -4.79 | $0.06538 | $2.000 | $6.000 | significant |
| Kimi K3.1 Pro | n=4 | 73.5 | 0.9 | -10.6 | -5.17 | $0.03803 | $2.000 | $10.000 | significant |
| Llama 4 Scout | n=3 | 73.2 | 5.8 | -10.8 | -2.78 | $0.00028 | $0.100 | $0.300 | significant |
| Grok 4.7 (xhigh) · xhigh | n=4 | 72.0 | 3.3 | -12.1 | -4.66 | $0.16239 | $2.000 | $6.000 | significant |
| Grok 4.6 (xhigh) · xhigh | n=4 | 71.2 | 2.8 | -12.8 | -5.23 | $0.03602 | $2.000 | $6.000 | significant |
| GPT-6 Luna (max) · xhigh | n=4 | 71.2 | 2.4 | -12.9 | -5.52 | $0.00394 | $0.100 | $0.500 | significant |
| Llama 3.3 Instruct 70B | n=3 | 69.9 | 0.0 | -14.2 | -7.05 | $0.00019 | $0.100 | $0.320 | significant |
| Nemotron 3.5 Lightning | n=1 | 69.0 | — | — | — | $0.00060 | $0.070 | $0.200 | low_n |
| Step 5 Preview | n=4 | 68.8 | 27.6 | -15.2 | -1.09 | $0.03508 | $1.000 | $2.700 | inside noise |
| Granite 4.2 8B | n=3 | 68.6 | 4.2 | -15.4 | -4.91 | $0.00204 | $0.060 | $0.150 | significant |
| Gemma 4 26B A4B (Reasoning) | n=3 | 68.4 | 2.0 | -15.6 | -6.74 | $0.00008 | $0.076 | $0.255 | significant |
| Muse Glimmer (high) · high | n=4 | 67.9 | 4.0 | -16.1 | -5.66 | $0.00330 | $0.300 | $1.200 | significant |
| Reka Flash 3 | n=1 | 25.1 | — | — | — | $0.00331 | $0.100 | $0.200 | low_n |

### The cheap end, and Claude Haiku 5.5

| model · effort | n | mean | sd | Δ vs ctrl | t | $/run | AA eloquent | AA scannable | AA truthful | AA writing |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3.7 Plus | n=11 | 91.9 | 3.3 | +7.8 | 3.50 | $0.00713 | — | — | — | — |
| MiniMax-M3 | n=14 | 91.7 | 3.3 | +7.7 | 3.50 | $0.00446 | 1178 | 1393 | 303 | 32.7 |
| MiMo-V2.6-Pro | n=4 | 90.5 | 3.6 | +6.4 | 2.37 | $0.00056 | 1077 | 1545 | 456 | 35.1 |
| Qwen3 Next 80B A3B Instruct | n=11 | 90.0 | 1.5 | +6.0 | 2.89 | $0.00066 | — | — | — | — |
| Qwen3.6 35B A3B (Reasoning) | n=11 | 89.8 | 3.0 | +5.8 | 2.62 | $0.00053 | — | — | — | — |
| Inkling Small | n=11 | 89.7 | 4.1 | +5.6 | 2.38 | $0.00647 | — | — | — | — |
| Inkling (xhigh) · xhigh | n=4 | 88.6 | 3.6 | +4.5 | 1.67 | $0.01818 | 1336 | 1357 | 449 | 71.0 |
| Qwen3 Coder Next | n=11 | 88.4 | 4.6 | +4.4 | 1.79 | $0.00045 | — | — | — | — |
| Gemini 3.8 Flash (high) · high | n=4 | 88.0 | 3.3 | +3.9 | 1.51 | $0.01302 | 1336 | 1424 | 463 | 45.0 |
| Nemotron 3 Ultra 550B | n=4 | 87.5 | 12.9 | +3.5 | 0.52 | $0.00406 | 211 | 1337 | -62 | 7.9 |
| Mistral Large 4 Preview | n=4 | 87.3 | 5.1 | +3.3 | 1.01 | $0.01793 | 1567 | 1283 | 389 | 59.9 |
| DeepSeek V4.1 Flash (max) · xhigh | n=4 | 86.8 | 3.4 | +2.7 | 1.05 | $0.00028 | 1146 | 1140 | 663 | 79.7 |
| Qwen3.5 9B (Reasoning) | n=11 | 86.4 | 5.8 | +2.3 | 0.88 | $0.00003 | — | — | — | — |
| GLM-5.3-Flash | n=15 | 86.2 | 6.0 | +2.2 | 0.85 | $0.00061 | 1575 | 1011 | 712 | 51.2 |
| DeepSeek V4.1 Flash 1017 (max) · xhigh | n=4 | 85.6 | 6.3 | +1.5 | 0.41 | $0.00027 | 1068 | 1053 | 762 | 71.0 |
| gpt-oss-20b (High) | n=11 | 85.3 | 3.4 | +1.2 | 0.54 | $0.00002 | — | — | — | — |
| DeepSeek V4.1 Flash (incumbent) · default | n=11 | 84.1 | 6.7 | +0.0 | — | $0.00246 | 1146 | 1140 | 663 | 79.7 |
| GPT-3.5 Turbo | n=4 | 84.1 | 1.4 | +0.1 | 0.03 | $0.00198 | -207 | 64 | 72 | 5.5 |
| MiniMax-M3.1-Flash | n=4 | 83.3 | 0.9 | -0.8 | -0.37 | $0.00036 | 865 | 1079 | 202 | 73.5 |
| gpt-oss-120b (High) | n=3 | 82.9 | 3.2 | -1.1 | -0.41 | $0.00021 | — | — | — | — |
| Qwen3 Omni 30B A3B (Reasoning) | n=3 | 82.8 | 3.9 | -1.3 | -0.43 | $0.00064 | — | — | — | — |
| Nemotron 3.5 Super VL | n=4 | 82.7 | 1.4 | -1.4 | -0.66 | $0.00030 | 1268 | 1411 | 497 | 66.1 |
| LongCat 2.0 | n=3 | 81.6 | 6.6 | -2.5 | -0.57 | $0.01076 | — | — | — | — |
| Hy3 | n=3 | 79.9 | 6.5 | -4.1 | -0.97 | $0.00349 | — | — | — | — |
| Solar Pro 4 | n=3 | 79.1 | 8.8 | -5.0 | -0.91 | $0.00039 | — | — | — | — |
| DeepSeek V4 Flash Vision (Max) | n=2 | 78.8 | 5.4 | — | — | $0.00511 | — | — | — | — |
| Qwen3.8 27B (xhigh) · xhigh | n=3 | 78.8 | 4.8 | -5.3 | -1.54 | $0.01546 | 984 | 1213 | 188 | 35.1 |
| Qwen3.8 27B (Xhigh) · default | n=2 | 77.7 | 2.1 | — | — | $0.00297 | 984 | 1213 | 188 | 35.1 |
| Gemma 4 31B (Non-reasoning) | n=3 | 76.7 | 4.6 | -7.3 | -2.20 | $0.00020 | — | — | — | — |
| GPT-5.4 mini (non-reasoning) | n=4 | 76.3 | 2.2 | -7.8 | -3.41 | $0.00244 | 653 | 1354 | 411 | 56.2 |
| Beam 1.0 | n=4 | 75.6 | 1.9 | -8.4 | -3.79 | $0.00568 | 1174 | 1406 | 498 | 58.7 |
| NVIDIA Nemotron 3 Nano 30B A3B (Reasoning) | n=6 | 74.4 | 8.4 | -9.7 | -2.43 | $0.00060 | — | — | — | — |
| Llama 4 Maverick | n=7 | 74.4 | 3.0 | -9.7 | -4.21 | $0.00026 | -139 | 842 | 68 | 1.7 |
| GPT-6.1 Sol (max) · xhigh | n=4 | 74.2 | 12.0 | -9.9 | -1.56 | $0.06311 | — | — | — | — |
| Claude Haiku 5.5 (max) · high | n=4 | 73.8 | 3.4 | -10.3 | -3.89 | $0.00159 | 1091 | 967 | 873 | 64.8 |
| Qwen3.8 Max (0902) | n=4 | 73.8 | 1.6 | -10.3 | -4.79 | $0.06538 | 902 | 1243 | 636 | 43.8 |
| Kimi K3.1 Pro | n=4 | 73.5 | 0.9 | -10.6 | -5.17 | $0.03803 | 1189 | 980 | 989 | 83.4 |
| Llama 4 Scout | n=3 | 73.2 | 5.8 | -10.8 | -2.78 | $0.00028 | — | — | — | — |
| Grok 4.7 (xhigh) · xhigh | n=4 | 72.0 | 3.3 | -12.1 | -4.66 | $0.16239 | 1310 | 820 | 753 | 59.9 |
| Grok 4.6 (xhigh) · xhigh | n=4 | 71.2 | 2.8 | -12.8 | -5.23 | $0.03602 | 1052 | 744 | 691 | 37.6 |
| GPT-6 Luna (max) · xhigh | n=4 | 71.2 | 2.4 | -12.9 | -5.52 | $0.00394 | 915 | 577 | 886 | 57.4 |
| Llama 3.3 Instruct 70B | n=3 | 69.9 | 0.0 | -14.2 | -7.05 | $0.00019 | — | — | — | — |
| Nemotron 3.5 Lightning | n=1 | 69.0 | — | — | — | $0.00060 | — | — | — | — |
| Step 5 Preview | n=4 | 68.8 | 27.6 | -15.2 | -1.09 | $0.03508 | 1081 | 1250 | 546 | 74.8 |
| Granite 4.2 8B | n=3 | 68.6 | 4.2 | -15.4 | -4.91 | $0.00204 | — | — | — | — |
| Gemma 4 26B A4B (Reasoning) | n=3 | 68.4 | 2.0 | -15.6 | -6.74 | $0.00008 | — | — | — | — |
| Muse Glimmer (high) · high | n=4 | 67.9 | 4.0 | -16.1 | -5.66 | $0.00330 | 1019 | 954 | 177 | 21.5 |
| Reka Flash 3 | n=1 | 25.1 | — | — | — | $0.00331 | — | — | — | — |

`—` in an AA column means no exact PersonalityBench name match, not a score of zero.

### AA records rejected as degenerate

- **GPT-6.1 Sol (max)** — all 30 traits equal 1000.0 — degenerate AA payload, not a measurement

### Efforts the provider did not honour

These requests sent `reasoning_effort` and got **zero reasoning tokens** back, so the named effort was ignored. Their scores are default-effort scores and must not be read as the high-effort variant:

- DeepSeek V4.1 Flash (max) — reasoning_effort=xhigh produced 0 reasoning tokens — provider ignored or does not support this level
- DeepSeek V4.1 Flash 1017 (max) — reasoning_effort=xhigh produced 0 reasoning tokens — provider ignored or does not support this level

### Reading the table

Significantly better than the control:

- **Qwen3.7 Plus** — mean 91.9, Δ +7.8, t=3.50, $0.00713/run (2.90× the control's cost)
- **MiniMax-M3** — mean 91.7, Δ +7.7, t=3.50, $0.00446/run (1.81× the control's cost)
- **Qwen3 Next 80B A3B Instruct** — mean 90.0, Δ +6.0, t=2.89, $0.00066/run (0.27× the control's cost)
- **Qwen3.6 35B A3B (Reasoning)** — mean 89.8, Δ +5.8, t=2.62, $0.00053/run (0.21× the control's cost)

Significantly **worse** than the control — no price justifies these on this task:

- **GPT-5.4 mini (non-reasoning)** — mean 76.3, Δ -7.8, t=-3.41, $0.00244/run
- **Beam 1.0** — mean 75.6, Δ -8.4, t=-3.79, $0.00568/run
- **Llama 4 Maverick** — mean 74.4, Δ -9.7, t=-4.21, $0.00026/run
- **Claude Haiku 5.5 (max)** — mean 73.8, Δ -10.3, t=-3.89, $0.00159/run
- **Qwen3.8 Max (0902)** — mean 73.8, Δ -10.3, t=-4.79, $0.06538/run
- **Kimi K3.1 Pro** — mean 73.5, Δ -10.6, t=-5.17, $0.03803/run
- **Llama 4 Scout** — mean 73.2, Δ -10.8, t=-2.78, $0.00028/run
- **Grok 4.7 (xhigh)** — mean 72.0, Δ -12.1, t=-4.66, $0.16239/run
- **Grok 4.6 (xhigh)** — mean 71.2, Δ -12.8, t=-5.23, $0.03602/run
- **GPT-6 Luna (max)** — mean 71.2, Δ -12.9, t=-5.52, $0.00394/run
- **Llama 3.3 Instruct 70B** — mean 69.9, Δ -14.2, t=-7.05, $0.00019/run
- **Granite 4.2 8B** — mean 68.6, Δ -15.4, t=-4.91, $0.00204/run
- **Gemma 4 26B A4B (Reasoning)** — mean 68.4, Δ -15.6, t=-6.74, $0.00008/run
- **Muse Glimmer (high)** — mean 67.9, Δ -16.1, t=-5.66, $0.00330/run

Best score-per-dollar in the measured set: **gpt-oss-20b (High)** — 85.3 at $0.00002/run.

---

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

---

## 4. Spend — product stages only

30 days (2026-10-04 → 2026-11-02). Development traffic is **excluded**
(`gpt-6.1-sol`, `gpt-6.1-terra`, `claude-haiku-5.5` and similar are engineering-use models, not product).

| | spend | requests | share |
|---|---|---|---|
| **A. Imaginator pipeline** | **$2.86** | 2,060 | 1.7% |
| └ drafter (`qwen3-coder`) | $0.21 | — | 0.13% |
| **B. Job Scout research** | **$27.52** | 10,281 | 16.6% |
| **PRODUCT TOTAL** | **$30.38** | 12,341 | **18.3%** |
| Development (out of scope) | $135.82 | — | 81.7% |

**Job Scout research is 91% of product spend.** The whole Imaginator pipeline is $2.86. Replacing the drafter cannot move the bill — it is a quality question, not a cost one.

---

## 5. AA-PersonalityBench — a prior, not a score

Available for 40 models (30 trait Elos + 8 index percentiles) and extracted from the website payload, because the documented API returns **404 DEPLOYMENT_NOT_FOUND** and the v2 host carries no personality fields.

Three measured reasons it is not a grading axis:

1. **Not exposed by the API** — the documented v1 endpoint returns **404 DEPLOYMENT_NOT_FOUND** and the v2 host carries no personality fields, so the website payload is the only route.
2. **Does not predict the task.** See the correlation table below.
3. **It would mis-rank the winner.** DeepSeek V4.1 Flash has the highest `organization` index of all 40 (100) and finished last among contenders. `eloquent` puts Claude Fable 5.1 first (1716) and Kimi K3.1 Pro 14th (1189), while the harness found Kimi the best-faithfulness drafter.

### Trait vs measured score — n=24 models

One point per model (its best variant), so a family measured at three efforts cannot outvote a family measured once. At n=24, |r| must exceed **0.43** to reach p<0.05.

| trait | Pearson r vs our score | significant |
|---|---|---|
| `scannable` | +0.38 | no |
| `truthful` | -0.29 | no |
| `eloquent` | +0.12 | no |
| `lexicallyVaried` | +0.11 | no |
| `structured` | +0.10 | no |
| `literate` | -0.06 | no |

**No trait clears the threshold.** The earlier n=6 analysis reported `scannable` at +0.81, which looked like it sat on the significance boundary; at n=24 the same relationship is far weaker. That is the expected regression of a small-sample correlation toward zero, and it is why the n=6 value should never have been quoted as "borderline predictive".

Where it is useful is **corroboration**: MiniMax M3.1 Flash scores near-bottom `truthful` (202 of a −611…2178 scale) while its `scannable` (1079) sits above Kimi's (980) — exactly the shape the drafter test measured independently (looks structured, fabricates in practice).

```bash
python -m resume_writing_v2.personalitybench traits eloquent scannable truthful
```

Each record carries a `_<trait>_scale` field (`trait Elo` or `index percentile`) so the two scales cannot be silently mixed.

---

## 6. Limitations

1. n=4–11 per variant resolves ~5–6 point differences, not 2-point. Claims under ~5 points are undetermined and are labelled `inside noise`.
2. A 4/4 drafter record is consistent with a ~10% failure rate. Read "no failures observed", not "never fails".
3. One task each — one JD, one profile, one fixture. Results may not transfer to another domain.
4. Deterministic keyword scorers can be wrong in fixed ways. Two such bugs were found and fixed (see git history).
5. The drafter prompt is reconstructed; golden-bullet library and seniority verb tables omitted. Relative comparisons hold, absolute scores are not production-identical.
6. No LLM-as-judge anywhere — every metric is deterministic and repeatable.
7. `K2 Horizon 375B A23B` has no OpenRouter id and is therefore unmeasured, not excluded for a bad score.
