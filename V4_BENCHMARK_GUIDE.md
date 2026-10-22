# V4 Resume Writing Benchmark — Developer Guide

## Overview

We benchmark LLMs on a **resume writing task** for a Boeing Defense GenAI Data Scientist role. Each model receives a job description + verified candidate profile and must produce an ATS-optimized resume using **only** the provided facts. No hallucination allowed.

**9 models × 3 runs each = 27 total runs.** Scoring is a two-stage process: hard gates (pass/fail) then weighted rubric (100 pts).

---

## How We Judge Performance

### Stage 1: Hard Gates (G1-G10)

Any **critical fail** = immediate disqualification. No score.

| Gate | What It Checks | Why It Matters |
|------|---------------|----------------|
| **G1** | No invented employers, degrees, certs, clearance, or metrics | Hallucination kills trust |
| **G2** | No Master's/PhD claims (candidate has Bachelor's only) | Degree integrity |
| **G3** | Name, contractor entity (Cogito Metric/C2C), U.S. citizenship present | Identity integrity |
| **G4** | Output is plain resume text — no markdown fences, no "Here is…" preamble | Clean output |
| **G5** | All required sections: HEADER, EXPERIENCE, PROJECTS, EDUCATION | Completeness |
| **G6** | Word count 320-700 (target 400-600) | Brevity |
| **G7** | Third-person only — no "I built…" | Professional tone |
| **G8** | "C2C" or "Cogito Metric" present | Contractor signal |
| **G9** | Boeing/defense relevance (capstone, GPU clusters, etc.) | JD alignment |
| **G10** | No table/multi-column markers | ATS parsable |

**Non-critical fails** (G5-G10) reduce the gates-passed count but don't disqualify.

### Stage 2: Weighted Scorecard (100 pts)

Only scorable runs (passed all critical gates) get scored.

| Category | Pts | What It Measures |
|----------|-----|------------------|
| **Fidelity** | 35 | Factual accuracy: employer hits, degree hits, cert hits, forbidden word avoidance |
| **Alignment** | 20 | JD keyword coverage across 8 themes (GenAI/LLM, Python/data, GPU/distributed, Docker/K8s, evaluation/bias, governance/regulated, MLOps/collab, deploy/scale) |
| **Bullets** | 10 | Action verb ratio on bulleted lines (≥0.8 = 10pts) |
| **Metrics** | 10 | Verified quantified impact preserved (263K, $500K, -40%, -30hrs, 10+TB) |
| **Targeting** | 10 | Experience ordering: Boeing/capstone first (+5), Cogito Metric (+3), NOAA+NRL (+2) |
| **Skills** | 5 | JD-relevant tech keywords (Python, PyTorch, TF, SQL, Docker, K8s, AWS, LangChain, Pinecone, Hadoop) |
| **ATS Structure** | 5 | Clean section headers ("Professional Experience", "Education", "Projects") |
| **Brevity** | 5 | Word count in 380-650 band |
| **GSI** | 10 | Grounded Skill Inference — smart bridging from evidence to adjacent skills without hallucination |

**Bands:** ≥90 Production-ready | ≥80 Strong | ≥70 Usable | ≥60 Weak | <60 Not deployable

---

## Top Scoring Models

### Tier 1: Perfect Score (100.0)

| Model | Avg | Var | Pass Rate | Cost/M |
|-------|-----|-----|-----------|--------|
| **GLM 5.1** | **100.0** | 0.00 | 100% | **$1.51** |
| OpenRouter Fusion (default) | 100.0 | 0.00 | 100% | ~$75.00* |

> *Fusion pricing is estimated — it's a multi-model orchestration system, not a single model.

### Tier 2: Near-Perfect (95-99)

| Model | Avg | Var | Pass Rate | Cost/M |
|-------|-----|-----|-----------|--------|
| **Qwen 3 235B Thinking** | **97.3** | 14.22 | 100% | **$0.10** |
| Grok 4.3 | 97.3 | 3.56 | 100% | $1.56 |
| Kat Coder Pro V2 | 95.0 | 10.67 | 100% | $0.53 |

### Tier 3: Strong (90-94)

| Model | Avg | Var | Pass Rate | Cost/M |
|-------|-----|-----|-----------|--------|
| Magnum V4 72B | 94.7 | 16.22 | 100% | $3.50 |
| MiMo V2.5 Pro | 93.2 | 2.72 | 100% | $0.54 |
| GPT-5 | 91.0 | 4.67 | 100% | $3.44 |

### Disqualified

| Model | Reason |
|-------|--------|
| Kimi K2.6 | 100% DQ — invented Master's/PhD degrees across all 3 runs |

---

## GLM 5.1 In Detail

**Model:** `z-ai/glm-5.1`  
**Provider:** GMI Cloud  
**Pricing:** $0.98/M input, $3.08/M output (blended: ~$1.51/M)  
**Score:** 100.0 avg across 3 runs, 0.00 variance  
**Pass Rate:** 100% (all gates passed, no disqualifications)

### Why GLM 5.1 Scores Perfectly

| Category | Avg Score | Why It Excels |
|----------|-----------|---------------|
| Fidelity (35) | 35.0 | Never invents facts. Always uses verified employers, degrees, certs. Zero forbidden words. |
| Alignment (20) | 20.0 | Hits all 8 JD themes every run. GenAI/LLM, GPU/distributed, Docker/K8s, governance — all present. |
| Bullets (10) | 8.0 | Strong action verb ratio (~0.7). Bullets start with "Developed", "Deployed", "Implemented". |
| Metrics (10) | 10.0 | Always preserves 263K, $500K, -40%, -30hrs, 10+TB from the profile. |
| Targeting (10) | 8.3 | Consistently leads with Boeing capstone or Cogito Metric. |
| Skills (5) | 5.0 | Hits 9-10 of 10 JD-relevant tech keywords. |
| ATS (5) | 5.0 | Clean "Professional Experience" / "Education" / "Projects" headers. |
| Brevity (5) | 5.0 | Word count consistently in 400-600 target band. |
| GSI (10) | 8.0 | Smart inferences: "containerized", "retrieval-augmented generation", "governance" — all grounded in evidence. |

### What Makes GLM 5.1 Stand Out

1. **Zero hallucination** — never invents degrees, employers, or metrics. This is the #1 failure mode for other models (Kimi K2.6: 100% DQ rate).

2. **Perfect consistency** — 0.00 variance across 3 runs. Every run scores 100.0. No randomness.

3. **Best cost/performance ratio in the premium tier** — $1.51/M for perfect scores. Compare to Fusion at ~$75/M for the same score.

4. **Strong GSI** — bridges from "Docker" → "containerized", "LangChain" → "retrieval-augmented generation" without overclaiming skills not in the profile.

### Where It Could Improve

- **Bullets (8/10):** Verb ratio is ~0.7, not quite the 0.8+ threshold for 10/10. Some bullets start with nouns or prepositions.
- **Targeting (8.3/10):** Occasionally doesn't lead with Boeing/capstone first, costing 2 pts.

### Comparison to Other Top Models

| Aspect | GLM 5.1 | Qwen 3 235B | Grok 4.3 |
|--------|---------|-------------|----------|
| Score | **100.0** | 97.3 | 97.3 |
| Variance | **0.00** | 14.22 | 3.56 |
| Cost/M | $1.51 | **$0.10** | $1.56 |
| Consistency | **Perfect** | High variance | Good |
| Hallucination | **None** | None | None |

**Bottom line:** GLM 5.1 is the most reliable model for this task — perfect scores every time at a reasonable price. Qwen 3 235B is the value king ($0.10/M) but has higher variance. If you need guaranteed quality, use GLM 5.1. If you're cost-sensitive, use Qwen 3 235B and accept some variance.

---

## How to Run the Benchmark

```bash
cd /home/skystarved/dev_workspaces
source venv/bin/activate
export OPENROUTER_API_KEY_1="your-key-here"
python v4_resume_writing_benchmark.py
```

Results are saved to `v4_benchmark_results.json`.

### Adding a New Model

Edit the `MODELS` list in `v4_resume_writing_benchmark.py`:

```python
MODELS = [
    ("provider/model-id", "Display Name", input_price, output_price, is_reasoning),
    # ...
]
```

- `is_reasoning=True` enables `reasoning: {effort: "high"}` for thinking models
- Prices are in $/M tokens (blended rate = (input×3 + output)/4)

---

## File Reference

| File | Purpose |
|------|---------|
| `v4_resume_writing_benchmark.py` | Main benchmark runner — 9 models × 3 runs |
| `v4_benchmark_results.json` | Full results with gates, scores, GSI per run |
| `test_fusion_config.py` | Fusion-specific tests with same scoring rubric |
| `fusion_config_test_results.json` | Fusion test results |
| `v3_resume_writing_results.json` | Previous V3 benchmark results |
| `GDPval_AA_Leaderboard.ipynb` | Notebook with leaderboard visualization |