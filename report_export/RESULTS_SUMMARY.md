# LLM Provider-Value Analysis — Results (2026-10-24)

## What was removed
- Redundant scoring layer (linear / exponential / sigmoid / quadratic) in cell 4.1 prep. All four are monotonic transforms of the same Base_Performance_Score; over the displayed range they preserve identical top-model ordering (quadratic also preserves rank). Removing avoids false diversity.

## What was kept / added
- 3.11 — provider-value discovery (top-20, best-value endpoint vs router default, quality gates, value gain).
- 3.13 — dynamic chosen-provider visual (reads cache, zero cost, shows provider / tok/s / price / gates / gain, two plots).
- 3.14 — top-20 rerank on provider true cost / real speed (clear plot labels: AA PUBLISHED vs PROVIDER TRUE COST / REAL SPEED).

## Key results (from executed 3.11 / 3.12 / 3.14)
- DeepSeek V4.1 Flash (Max): best-value provider delivers ~2.47x efficiency vs default; default (OpenInference $0.02/M input) failed quality gates in stealth test.
- 5 default providers failed gates (lossy quant / low uptime) — the "dumb provider" mechanism.
- Above-44 rerank: 14 moved up, 14 down, 4 unchanged when using real endpoint speed/price.
- Provider cache: 57/61 models resolved; 3 unresolved (Agnes 2.5 Pro Beta, Qwen3.8-Flash-Next, Gemma 4 12B, Qwen3.5 4B).

## Cost
- All analysis uses existing `_cache` / `provider_value_by_model.json` — $0.00.
- Refresh (`REFRESH_PROVIDER_DATA=True`) = ~20-40 endpoint calls = <10¢.

## Shared files
- `report_export/chosen_providers_top20.csv` — chosen provider, tok/s, price, gates, gain per model.
- Notebook cells 3.11 / 3.13 / 3.14 contain the plots and tables.
