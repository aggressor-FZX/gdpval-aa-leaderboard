# GDPval-AA LLM Leaderboard

Comprehensive LLM scoring analysis combining **Artificial Analysis** (AA) benchmark data with **OpenRouter** real-world pricing and throughput telemetry.

## What This Does

Scores 700+ LLMs across intelligence, speed, reliability, and cost using multiple scoring schemes:

1. **Base metric**: `((intelligence + speed) × (1 - hallucination_rate)) / cost`
2. **Additive efficiency**: `(Throughput + Intel²) × (1-Hall) / Cost`
3. **Multiplicative efficiency**: `(√Throughput × Intel) × (1-Hall) / Cost`
4. **Eval-cost multiplicative**: same formula using the estimated cost of running the full AA Intelligence Index evaluation suite (captures verbosity)
5. **Raw-throughput multiplier**: throughput used linearly (no √) with real-world measured throughput — for latency-sensitive workloads

## Category Comparisons

- **Free models (3.7)**: raw performance only; no cost denominator
- **Above-44 (3.8)**: AA Intelligence Index ≥ 44, cost-normalized (44.0+ rounds up to the displayed 45+ elite tier)
- **Above-44 weighted prices (3.10)**: same formulas, but the cost denominator is OpenRouter's *Weighted Average Input/Output* price — the traffic-weighted average price actually paid per 1M tokens over the past day (caching + provider discounts), not the listed price

## Data Sources

### Artificial Analysis
- API: `https://artificialanalysis.ai/api/v2/data/llms/models`
- Intelligence Index v4.0 — composite of GDPval-AA, Terminal-Bench Hard, SciCode, GPQA, HLE, IFBench, AA-Omniscience, AA-LCR

### OpenRouter
- Catalog: `GET /api/v1/models`
- Weighted-average (effective) pricing: `GET /api/frontend/v1/stats/effective-pricing?permaslug=<canonical-slug>&shape=v7&variant=standard` → `weightedInputPrice` / `weightedOutputPrice`
- Real-world throughput: `GET /api/frontend/v1/stats/throughput-comparison?perfWorkload=text_generation&permaslug=<slug>&timeRange=1w`
- The `permaslug` comes from `GET /api/frontend/v1/catalog/models` (field `permaslug`)

## Data Quality Rules (2026-10 audit)

- **Missing ≠ zero**: AA speed values `<=0` are treated as missing
- **Family imputation**: missing throughput/reliability uses family medians computed before filtering
- **True NaNs stay NaN**: models without sufficient data are excluded visibly rather than scored as zero
- **OpenRouter fallback**: rescued throughput is tagged `Throughput_Source` for provenance

## Resume Benchmarks (Appendix)

- **V2 parsing**: 18 models × 5 resumes (3 domains), 110-point scoring with name & date accuracy
- **V3 writing**: 17 models writing ATS-optimized resumes for a Boeing Defense GenAI Data Scientist role from a verified profile — all models scored 25/25 fact fidelity (zero hallucinated credentials)
- **V4 writing**: 9 models × 3 runs, two-stage scoring (10 hard gates + 100-pt weighted scorecard)

## Setup

```bash
pip install pandas numpy matplotlib seaborn scipy requests python-dotenv
```

Create a `.env` file (gitignored):

```
ARTIFICIAL_ANALYSIS_KEY=your_key
OPENROUTER_API_KEY_1=your_key
```

## Usage

Open `GDPval_AA_Leaderboard.ipynb` and run cells top-to-bottom. Sections 2.1b–2.3 rescue missing throughput data and cross-check both catalogs; sections 3.1–3.10 compute the efficiency analyses; section 4 compares scoring methods; the appendix holds the resume benchmarks.

## Key Findings (2026-10)

- **DeepSeek V4.1 Flash** dominates cost-normalized rankings: effective price ~$0.21/M (60% real-world discount from caching) with 104 tok/s measured real-world throughput
- **MiMo-V2.6-Pro** is the value pick in the elite tier (55% effective discount)
- **GLM-5.3 (Max)** at Intel 44.8 just clears the Above-44 tier and ranks #4 in raw-throughput efficiency with a 53.9% effective discount
- Hallucination is a solved problem for resume writing: every scored model passed fact fidelity