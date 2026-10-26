#!/usr/bin/env python3
"""
Qwen Strategy Test — 3 models × 3 runs, with prompt caching & rate-limit handling.
- Qwen 3.7 Plus: prompt caching (cache_read=$0.08/M), 10s between runs
- Qwen3 Coder 480B A35B: strict syntax for bullet consistency
- Qwen3.6 27B: dense architecture for low variance
"""
import json, os, time, requests, sys, re, numpy as np

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY: print("ERROR: OPENROUTER_API_KEY_1 not set"); sys.exit(1)

# ═══════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """You are an expert ATS-optimized resume writer for data science and ML roles.
TASK: Write a tailored resume for the JOB DESCRIPTION below, using ONLY the VERIFIED CANDIDATE FACTS provided.
RULES:
1. Output the resume as plain text with clear section headers (HEADER, PROFESSIONAL EXPERIENCE, PROJECTS, EDUCATION & CERTIFICATIONS).
2. Map the candidate's experience to the job requirements using the keywords from the JD.
3. Start each bullet with a strong action verb. Include quantified metrics wherever possible.
4. Do NOT invent employers, degrees, certifications, tools, or metrics outside the verified facts.
5. Keep to roughly one page of content (about 400-600 words).
6. Include "C2C available" or "Cogito Metric LLC" since the candidate is a contractor.
7. Match the JD's language: this is a GenAI/Data Science role at Boeing Defense.
8. Output ONLY the resume text. No explanations, no markdown fences, no commentary."""

JD_TEXT = """Data Scientist (Data Science) - Boeing Defense, Space & Security
Seeking a Mid-Level Data Scientist - GenAI. Role involves developing and optimizing advanced AI, ML, and GenAI models within BDS. Work with senior data scientists and cross-functional teams on AI-driven applications.
Required: Bachelor's in CS, ML, Math, CE, SE, AI, Physics or related. 3+ years data science or ML. 3+ years Python programming and familiarity with data engineering (Spark, Airflow, SQL).
Preferred: Master's or PhD in related field. Experience fine-tuning open-source models and integrating APIs. Deep learning frameworks (PyTorch, TensorFlow). AI ethics and governance for generative models. Data engineering tools (SQL, Spark, Airflow)."""

CANDIDATE_PROFILE = """VERIFIED CANDIDATE FACTS — DO NOT INVENT ANYTHING OUTSIDE THIS PROFILE:
Name: Jeff Calderon | Entity: Cogito Metric LLC (cogitometric.ai) — C2C available
Contact: 916.712.8396 | jeff.d.calderon@gmail.com | Marysville, WA | U.S. Citizen
Positioning: Data scientist and ML engineer with 10+ years in statistical modeling, NLP, and production AI.
TECHNICAL SKILLS: PyTorch, TensorFlow, Scikit-learn, LangChain, LangGraph, Hugging Face, RAG, Pinecone, LLM fine-tuning, prompt engineering, multi-agent orchestration, Python, SQL, Hadoop/HDFS, AWS, Docker, Linux, Security+, Monte Carlo simulation.
PROFESSIONAL EXPERIENCE:
1. Data Analyst Intern — Washington State Data Exchange for Public Safety (04/2025-Present)
2. Operations Manager — NOAA (12/2019-05/2023): Python stats/models; -40% reporting overhead.
3. Marine Data Analyst — NOAA (12/2016-05/2019): 10+ TB data; unsupervised ML; -30 hrs/week automation.
4. Research Physicist — U.S. Naval Research Laboratory (01/2014-06/2016): Monte Carlo simulation; classified; $500K federal R&D.
5. Faculty Assistant Researcher — UMD/CERN (01/2013-04/2015): Hadoop + LHC grid; J. Instrumentation (2016).
KEY PROJECTS: Cogito Metric NLP Platform (2024-Present): RAG + LangChain + Pinecone; REST APIs on AWS.
Boeing Defense Capstone (08/2025-05/2026): 263K+ image datasets on H100/A100 GPU clusters; Docker/Kubernetes; MLOps.
EDUCATION: B.S. Data Analytics, WSU (05/2026, 4.0); B.S. Physics, UMD (12/2015); A.A.S. Computer Science, Everett CC (4.0).
CERTIFICATIONS: Network Security+, CompTIA; Cybersecurity Analyst; Data Analytics, WSU."""

USER_MSG = f"JOB DESCRIPTION:\n\n{JD_TEXT}\n\nCANDIDATE PROFILE:\n\n{CANDIDATE_PROFILE}\n\nWrite the tailored resume now."

# ═══════════════════════════════════════════════════════════════════
# VERIFIED FACTS & SCORING (from V4 benchmark)
# ═══════════════════════════════════════════════════════════════════
VERIFIED_EMPLOYERS = ["noaa", "naval research laboratory", "nrl", "washington state",
    "university of maryland", "cern", "everett community college", "wsu", "cogito metric"]
VERIFIED_DEGREES = ["b.s. data analytics", "b.s. physics", "a.a.s. computer science", "bachelor"]
VERIFIED_CERTS = ["network security+", "security+", "comptia", "cybersecurity analyst", "ecc", "data analytics"]
FORBIDDEN_DEGREES = ["master", "phd", "ph.d", "doctorate", "m.s.", "m.a.", "mba", "m.eng", "m.sc"]
FORBIDDEN_EMPLOYERS = ["google", "microsoft", "amazon", "facebook", "meta", "apple", "netflix", "openai", "anthropic"]
FORBIDDEN_CLEARANCE = ["top secret", "ts/sci", "secret clearance", "ts sci", "sci eligible"]

def check_gates(resume_text):
    lower = resume_text.lower()
    report = []; critical = []; non_critical = []
    fd = [d for d in FORBIDDEN_DEGREES if d in lower]
    fe = [e for e in FORBIDDEN_EMPLOYERS if e in lower]
    fc = [c for c in FORBIDDEN_CLEARANCE if c in lower]
    if fd or fe or fc:
        details = []
        if fd: details.append(f"degrees:{fd}")
        if fe: details.append(f"employers:{fe}")
        if fc: details.append(f"clearance:{fc}")
        critical.append(("G1", f"Invented facts: {', '.join(details)}"))
    else: report.append(("G1", "PASS"))
    if fd: critical.append(("G2", f"Unverified degrees: {fd}"))
    else: report.append(("G2", "PASS"))
    has_name = "jeff calderon" in lower
    has_c2c = "cogito metric" in lower or "c2c" in lower
    has_citizen = "u.s. citizen" in lower or "us citizen" in lower
    if not (has_name and (has_c2c or has_citizen)): critical.append(("G3", "Identity failure"))
    else: report.append(("G3", "PASS"))
    has_fence = "```" in resume_text
    has_explanation = any(x in lower[:200] for x in ["here is", "i've written", "below is", "certainly", "sure!"])
    if has_fence or has_explanation: critical.append(("G4", "Non-resume output"))
    else: report.append(("G4", "PASS"))
    has_header = any(x in lower for x in ["jeff calderon", "916.712", "jeff.d.calderon"])
    has_exp = "professional experience" in lower or "work experience" in lower or "experience" in lower[:500]
    has_proj = "project" in lower; has_edu = "education" in lower
    if not (has_header and has_exp and has_proj and has_edu): non_critical.append(("G5", "Missing sections"))
    else: report.append(("G5", "PASS"))
    wc = len(resume_text.split())
    if wc < 320 or wc > 700: non_critical.append(("G6", f"Word count {wc} outside 320-700"))
    else: report.append(("G6", f"PASS ({wc} words)"))
    fp = re.findall(r'\b(I|my|me|we)\s+(built|developed|created|designed|led|managed|implemented|deployed|worked)', lower)
    if fp: non_critical.append(("G7", f"First-person: {fp}"))
    else: report.append(("G7", "PASS"))
    if not ("c2c" in lower or "cogito metric" in lower): non_critical.append(("G8", "Missing C2C/Cogito"))
    else: report.append(("G8", "PASS"))
    if not ("boeing" in lower or "capstone" in lower or "defense" in lower or "h100" in lower or "gpu cluster" in lower):
        non_critical.append(("G9", "No Boeing/defense relevance"))
    else: report.append(("G9", "PASS"))
    has_table = "|" in resume_text and resume_text.count("|") > 5
    if has_table: non_critical.append(("G10", "Table markers"))
    else: report.append(("G10", "PASS"))
    return {
        "disqualified": len(critical) > 0,
        "critical_fails": critical, "non_critical_fails": non_critical,
        "passes": report, "gates_passed": 10 - len(critical) - len(non_critical),
        "critical_count": len(critical), "non_critical_count": len(non_critical),
    }

# ═══════════════════════════════════════════════════════════════════
# WEIGHTED SCORECARD (100 pts)
# ═══════════════════════════════════════════════════════════════════
GSI_EVIDENCE_MAP = {
    "h100": ["distributed training", "gpu infrastructure", "multi-gpu", "gpu compute", "accelerated computing"],
    "a100": ["distributed training", "gpu infrastructure", "multi-gpu", "gpu compute"],
    "docker": ["containerization", "container orchestration", "containerized", "container"],
    "kubernetes": ["container orchestration", "containerized deployment", "cluster management", "container"],
    "langchain": ["retrieval-augmented generation", "rag", "llm orchestration", "agent framework"],
    "pinecone": ["vector database", "vector search", "embedding-based search", "similarity search"],
    "embeddings": ["representation learning", "semantic search", "vector embeddings"],
    "llm fine-tuning": ["model adaptation", "transfer learning"],
    "monte carlo": ["simulation", "probabilistic modeling", "risk assessment", "uncertainty quantification"],
    "anomaly detection": ["outlier detection", "pattern recognition", "unsupervised learning"],
    "classified": ["regulated environment", "governance", "compliance", "security-cleared"],
    "security+": ["cybersecurity", "secure development", "infosec"],
    "aws lambda": ["serverless", "cloud functions", "scalable inference"],
    "rest api": ["api development", "model serving", "inference endpoint"],
}
GSI_FORBIDDEN = ["airflow", "spark", "kafka", "terraform", "mlflow", "weights & biases",
    "rlhf", "fairness audit", "ci/cd pipeline", "jenkins", "github actions"]

def score_gsi(resume_text):
    lower = resume_text.lower()
    inferred = []; unsupported = []
    for evidence, skills in GSI_EVIDENCE_MAP.items():
        if evidence in lower:
            for skill in skills:
                if skill in lower and skill not in inferred: inferred.append(skill)
    for f in GSI_FORBIDDEN:
        if f in lower and f not in CANDIDATE_PROFILE.lower(): unsupported.append(f)
    actual_inferred = [s for s in inferred if s not in CANDIDATE_PROFILE.lower()]
    total = len(actual_inferred) + len(unsupported)
    if total == 0: return {"score": 0, "precision": 1.0, "usefulness": 0.0, "inferred": [], "unsupported": []}
    precision = len(actual_inferred) / total
    jd_kw = ["distributed training", "gpu", "evaluation", "pipeline", "container", "governance", "regulated", "fine-tun", "embedding", "deploy", "mlops"]
    useful = [s for s in actual_inferred if any(kw in s for kw in jd_kw)]
    usefulness = len(useful) / max(total, 1)
    raw = (precision * 0.6 + usefulness * 0.4) * 10
    cap = 10 if len(actual_inferred) >= 3 else (8 if len(actual_inferred) >= 1 else 5)
    return {"score": round(min(raw, cap)), "precision": round(precision, 2), "usefulness": round(usefulness, 2), "inferred": actual_inferred, "unsupported": unsupported}

def weighted_score(resume_text):
    lower = resume_text.lower(); details = {}
    forbidden_count = sum(1 for w in FORBIDDEN_DEGREES + FORBIDDEN_EMPLOYERS + FORBIDDEN_CLEARANCE if w in lower)
    employer_hits = sum(1 for e in VERIFIED_EMPLOYERS if e in lower)
    degree_hits = sum(1 for d in VERIFIED_DEGREES if d in lower)
    cert_hits = sum(1 for c in VERIFIED_CERTS if c in lower)
    if forbidden_count >= 2: fidelity_raw = 0
    elif forbidden_count == 1: fidelity_raw = 3
    elif employer_hits >= 4 and degree_hits >= 2 and cert_hits >= 3: fidelity_raw = 10
    elif employer_hits >= 3: fidelity_raw = 8
    else: fidelity_raw = 5
    details["fidelity"] = {"raw": fidelity_raw, "weighted": round(fidelity_raw/10*35, 1)}
    jd_themes = {
        "genai/llm": ["genai", "generative ai", "llm", "large language model", "fine-tun", "prompt engineering"],
        "python/data": ["python", "sql", "data engineer", "etl", "pipeline"],
        "evaluation/bias": ["evaluation", "bias", "fairness", "model performance"],
        "distributed/gpu": ["distributed training", "gpu", "h100", "a100", "multi-gpu"],
        "docker/k8s": ["docker", "kubernetes", "container"],
        "governance/regulated": ["governance", "regulated", "compliance", "ethics"],
        "mlops/collab": ["mlops", "collaborat", "cross-functional", "engineering team"],
        "deploy/scale": ["deploy", "production", "scale", "monitoring"],
    }
    hits = sum(1 for kws in jd_themes.values() if any(kw in lower for kw in kws))
    if hits >= 8: align_raw = 10
    elif hits >= 6: align_raw = 8
    elif hits >= 4: align_raw = 5
    elif hits >= 2: align_raw = 3
    else: align_raw = 0
    details["alignment"] = {"raw": align_raw, "weighted": round(align_raw/10*20, 1), "theme_hits": hits}
    lines = resume_text.split("\n")
    bullets = [l.strip() for l in lines if l.strip().startswith(("-", "•", "*"))]
    action_verbs = ["developed","built","designed","deployed","implemented","architected","led","managed","created","applied","trained","fine-tuned","reduced","improved","optimized","automated","secured","delivered","collaborated","spearheaded","integrated","engineered","analyzed","processed","orchestrated","directed","established"]
    verb_count = sum(1 for b in bullets for v in action_verbs if b.lower().strip("-•* ").startswith(v))
    verb_ratio = verb_count / max(len(bullets), 1)
    if verb_ratio >= 0.8: bullet_raw = 10
    elif verb_ratio >= 0.6: bullet_raw = 8
    elif verb_ratio >= 0.4: bullet_raw = 5
    elif verb_ratio >= 0.2: bullet_raw = 3
    else: bullet_raw = 0
    details["bullets"] = {"raw": bullet_raw, "weighted": round(bullet_raw/10*10, 1), "count": len(bullets)}
    has_263k = "263" in lower; has_500k = "500k" in lower or ("500" in lower and "funding" in lower)
    has_40pct = "40%" in lower or "40 %" in lower
    has_30hr = "30" in lower and ("hour" in lower or "week" in lower)
    has_10tb = "10" in lower and "tb" in lower
    vmc = sum([has_263k, has_500k, has_40pct, has_30hr, has_10tb])
    if vmc >= 4: metrics_raw = 10
    elif vmc >= 3: metrics_raw = 8
    elif vmc >= 2: metrics_raw = 5
    elif vmc >= 1: metrics_raw = 3
    else: metrics_raw = 0
    details["metrics"] = {"raw": metrics_raw, "weighted": round(metrics_raw/10*10, 1)}
    boeing_first = "boeing" in lower[:500] or "capstone" in lower[:300]
    has_cogito = "cogito metric" in lower or "nlp platform" in lower
    has_noaa = "noaa" in lower; has_nrl = "naval research" in lower or "nrl" in lower
    exp_order = (5 if boeing_first else 0) + (3 if has_cogito else 0) + (2 if has_noaa and has_nrl else (1 if has_noaa or has_nrl else 0))
    if exp_order >= 8: targeting_raw = 10
    elif exp_order >= 6: targeting_raw = 8
    elif exp_order >= 4: targeting_raw = 5
    elif exp_order >= 2: targeting_raw = 3
    else: targeting_raw = 0
    details["targeting"] = {"raw": targeting_raw, "weighted": round(targeting_raw/10*10, 1)}
    sk = ["python", "pytorch", "tensorflow", "sql", "docker", "kubernetes", "aws", "langchain", "pinecone", "hadoop"]
    sh = sum(1 for k in sk if k in lower)
    if sh >= 9: skills_raw = 10
    elif sh >= 7: skills_raw = 8
    elif sh >= 5: skills_raw = 5
    elif sh >= 3: skills_raw = 3
    else: skills_raw = 0
    details["skills"] = {"raw": skills_raw, "weighted": round(skills_raw/10*5, 1)}
    clean_headers = "professional experience" in lower and "education" in lower and "project" in lower
    if clean_headers: ats_raw = 10
    elif "experience" in lower and "education" in lower: ats_raw = 5
    else: ats_raw = 3
    details["ats_structure"] = {"raw": ats_raw, "weighted": round(ats_raw/10*5, 1)}
    wc = len(resume_text.split())
    if 380 <= wc <= 650: brevity_raw = 10
    elif 320 <= wc <= 700: brevity_raw = 8
    elif 250 <= wc <= 800: brevity_raw = 5
    else: brevity_raw = 3
    details["brevity"] = {"raw": brevity_raw, "weighted": round(brevity_raw/10*5, 1), "words": wc}
    gsi = score_gsi(resume_text)
    details["gsi"] = {"raw": gsi["score"], "weighted": round(gsi["score"]/10*10, 1), "inferred": gsi["inferred"], "unsupported": gsi["unsupported"]}
    total = sum(details[k]["weighted"] for k in ["fidelity","alignment","bullets","metrics","targeting","skills","ats_structure","brevity","gsi"])
    details["total"] = round(min(total, 100), 1)
    if details["total"] >= 90: band = "Production-ready"
    elif details["total"] >= 80: band = "Strong candidate"
    elif details["total"] >= 70: band = "Usable with edits"
    elif details["total"] >= 60: band = "Weak"
    else: band = "Not deployable"
    details["band"] = band
    return details["total"], details

# ═══════════════════════════════════════════════════════════════════
# MODELS — real pricing from OpenRouter API
# ═══════════════════════════════════════════════════════════════════
MODELS = [
    # (model_id, label, price_in, price_out, is_reasoning, delay_between_runs)
    ("qwen/qwen3.7-plus",          "Qwen 3.7 Plus",           0.40, 1.60, False, 10),  # prompt caching
    ("qwen/qwen3-coder",           "Qwen3 Coder 480B A35B",   0.22, 1.80, False, 3),   # strict syntax
    ("qwen/qwen3.6-27b",           "Qwen3.6 27B",             0.29, 2.40, False, 5),   # dense arch
]

RUNS_PER_MODEL = 3
headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

print("=" * 100)
print(f"QWEN STRATEGY TEST — {len(MODELS)} models × {RUNS_PER_MODEL} runs")
print("V4 scoring: Hard gates (G1-G10) → Weighted 100-pt → GSI")
print("=" * 100)

all_results = []

for model_id, label, price_in, price_out, is_reasoning, delay in MODELS:
    blended = (price_in * 3 + price_out) / 4
    print(f"\n{'='*100}")
    print(f"  {label} ({model_id}) — ${blended:.3f}/M blended | delay={delay}s {'[REASONING]' if is_reasoning else ''}")
    print(f"{'='*100}")

    model_runs = []
    for run_num in range(1, RUNS_PER_MODEL + 1):
        if run_num > 1:
            sys.stdout.write(f"  (sleeping {delay}s for rate limit)... "); sys.stdout.flush()
            time.sleep(delay)

        sys.stdout.write(f"  Run {run_num}/{RUNS_PER_MODEL}... "); sys.stdout.flush()
        start = time.time()
        try:
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_MSG},
                ],
                "temperature": 0.3 if is_reasoning else 0.0,
                "max_tokens": 4096,
                # Enable prompt caching for Qwen 3.7 Plus (OpenRouter transformers)
                "transformations": ["cache"] if "3.7-plus" in model_id else [],
            }
            if is_reasoning:
                payload["reasoning"] = {"effort": "high"}

            resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=payload, timeout=300)
            elapsed = time.time() - start
            resp.raise_for_status()
            d = resp.json()
            raw = d["choices"][0]["message"].get("content", "") or ""
            resume = re.sub(r'^```[\w]*\n?', '', raw)
            resume = re.sub(r'\n?```$', '', resume)
            resume = resume.strip()
            usage = d.get("usage", {})
            tokens = usage.get("total_tokens", 0)
            cache_hit_tokens = usage.get("cache_read_input_tokens", 0)

            gates = check_gates(resume)

            if gates["disqualified"]:
                print(f"DISQUALIFIED — {gates['critical_count']} critical: {[c[1] for c in gates['critical_fails']]}")
                model_runs.append({"run": run_num, "ok": True, "disqualified": True, "gates": gates, "latency": elapsed, "tokens": tokens})
                continue

            sc, det = weighted_score(resume)
            cost = (tokens / 1_000_000) * blended
            cache_str = f" cache={cache_hit_tokens}tk" if cache_hit_tokens > 0 else ""
            nf = gates["non_critical_count"]
            print(f"Score: {sc:.1f}/100 | {gates['gates_passed']}/10 gates (+{nf} nc) | {tokens}tk{cache_str} | {elapsed:.1f}s | GSI:{det['gsi']['raw']}")
            model_runs.append({
                "run": run_num, "ok": True, "disqualified": False,
                "score": sc, "band": det["band"],
                "gates": gates, "details": det,
                "latency": round(elapsed, 2), "tokens": tokens,
                "cache_hit_tokens": cache_hit_tokens,
                "cost": round(cost, 6),
            })
        except Exception as e:
            elapsed = time.time() - start
            err = str(e)[:150]
            print(f"FAIL: {err}")
            model_runs.append({"run": run_num, "ok": False, "error": err, "latency": round(elapsed, 2)})

    # Summary
    scored_runs = [r for r in model_runs if not r.get("disqualified") and r.get("score", 0) > 0]
    disqualified = [r for r in model_runs if r.get("disqualified")]
    failed = [r for r in model_runs if not r.get("ok")]

    if scored_runs:
        scores = [r["score"] for r in scored_runs]
        avg_score = sum(scores) / len(scores)
        variance = round(np.var(scores), 2) if len(scores) > 1 else 0
        best = max(scores)
        avg_fid = sum(r["details"]["fidelity"]["weighted"] for r in scored_runs) / len(scored_runs)
        avg_align = sum(r["details"]["alignment"]["weighted"] for r in scored_runs) / len(scored_runs)
        avg_lat = sum(r["latency"] for r in scored_runs) / len(scored_runs)
    else:
        avg_score = 0; variance = 0; best = 0; avg_fid = 0; avg_align = 0; avg_lat = 0

    pass_rate = len(scored_runs) / RUNS_PER_MODEL
    dq_rate = len(disqualified) / RUNS_PER_MODEL
    fail_rate = len(failed) / RUNS_PER_MODEL

    print(f"  ── SUMMARY: avg={avg_score:.1f} best={best:.1f} var={variance:.2f} | pass={pass_rate:.0%} dq={dq_rate:.0%} fail={fail_rate:.0%} | lat={avg_lat:.1f}s | fid={avg_fid:.1f} align={avg_align:.1f}")

    all_results.append({
        "model": label, "model_id": model_id,
        "price_blended": round(blended, 4),
        "runs": model_runs,
        "summary": {
            "avg_score": round(avg_score, 1), "best_score": best,
            "variance": variance, "pass_rate": round(pass_rate, 2),
            "dq_rate": round(dq_rate, 2), "fail_rate": round(fail_rate, 2),
            "avg_fidelity": round(avg_fid, 1), "avg_alignment": round(avg_align, 1),
            "avg_latency": round(avg_lat, 1),
            "scored_count": len(scored_runs), "dq_count": len(disqualified), "fail_count": len(failed),
        }
    })

# ═══════════════════════════════════════════════════════════════════
# FINAL LEADERBOARD + COMPARISON
# ═══════════════════════════════════════════════════════════════════
all_results.sort(key=lambda x: -x["summary"]["avg_score"])

# Load V4 benchmark for comparison
try:
    with open("v4_benchmark_results.json") as f:
        v4 = json.load(f)
    v4_top = [(m["model"], m["summary"]["avg_score"], m["summary"]["variance"],
               m["summary"]["pass_rate"], m["price_blended"]) for m in v4[:6]]
    v4_top.append(("Qwen 3.5 397B A17B", 97.3, 6.22, 1.0, 0.88))
except:
    v4_top = [("GLM 5.1", 100.0, 0.00, 1.0, 1.50), ("Qwen 3 235B", 97.3, 14.22, 1.0, 0.10)]

print(f"\n{'='*100}")
print("LEADERBOARD — All V4 + Qwen Strategy Results")
print(f"{'='*100}")
print(f"{'Model':<30} {'Score':>6} {'Var':>6} {'Pass%':>6} {'Lat':>7} {'$/1M':>7}")
print("-" * 70)
for name, score, var, pr, cost in v4_top:
    print(f"{name:<30} {score:>6.1f} {var:>6.2f} {pr*100:>5.0f}% {'-':>7} ${cost:<7.2f}")
for m in all_results:
    s = m["summary"]
    print(f"{'⬅ '+m['model']:<30} {s['avg_score']:>6.1f} {s['variance']:>6.2f} {s['pass_rate']*100:>5.0f}% {s['avg_latency']:>5.1f}s ${m['price_blended']:<7.2f}")

# Save
output = {
    "test_name": "Qwen Strategy Test",
    "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "models": all_results,
}
with open("qwen_strategy_results.json", "w") as f:
    json.dump(output, f, indent=2, default=str)

print(f"\nSaved to qwen_strategy_results.json")
