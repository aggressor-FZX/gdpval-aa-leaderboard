#!/usr/bin/env python3
"""
Deterministic Fusion test — 2 explicit Fusion configs + 1 default Fusion +
standalone panel models for log comparison. All scored with V4 rubric.

╔══════════════════════════════════════════════════════════════════════════╗
║                    V4 RESUME WRITING BENCHMARK CRITERIA                ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  HARD GATES (G1-G10) — Pass/Fail, any critical fail = DISQUALIFIED    ║
║  ────────────────────────────────────────────────────────────────────  ║
║  G1  No invented facts: employers, degrees, certs, clearance, metrics  ║
║      Checks: FORBIDDEN_DEGREES, FORBIDDEN_EMPLOYERS,                   ║
║              FORBIDDEN_CLEARANCE                                       ║
║  G2  Degree integrity: no Master's/PhD claims                          ║
║      Checks: same FORBIDDEN_DEGREES list                               ║
║  G3  Identity integrity: name, entity (Cogito Metric/C2C), citizenship ║
║      Checks: "jeff calderon", "cogito metric"/"c2c", "u.s. citizen"   ║
║  G4  Output type: resume only, no explanations/markdown fences         ║
║      Checks: "```" fences, preamble phrases ("here is", "certainly")   ║
║  G5  Required sections: HEADER, EXPERIENCE, PROJECTS, EDUCATION        ║
║      Checks: name/contact, "professional experience", "project",       ║
║              "education"                                               ║
║  G6  Word count band: 320-700 words (target 400-600)                   ║
║      Checks: len(resume_text.split())                                  ║
║  G7  Third-person style: no "I built", "my role", etc.                 ║
║      Checks: regex for first-person + action verb combos               ║
║  G8  Contractor signal: C2C or Cogito Metric LLC present               ║
║      Checks: "c2c" or "cogito metric" in text                          ║
║  G9  Boeing relevance: JD is Boeing Defense role                       ║
║      Checks: "boeing", "capstone", "defense", "h100", "gpu cluster"    ║
║  G10 ATS readability: no tables or decorative markers                  ║
║      Checks: pipe chars > 5, decorative line chars                     ║
║                                                                        ║
║  WEIGHTED SCORECARD (100 pts total)                                    ║
║  ────────────────────────────────────────────────────────────────────  ║
║  Fidelity (35 pts) — Factual accuracy against verified profile         ║
║      Raw 0-10 scaled: 0=2+forbidden, 3=1forbidden, 5=weak,            ║
║      8=3+employers, 10=4+employers+2degrees+3certs                     ║
║  Alignment (20 pts) — JD keyword coverage across 8 theme categories    ║
║      Themes: genai/llm, python/data, evaluation/bias, distributed/gpu, ║
║      docker/k8s, governance/regulated, mlops/collab, deploy/scale      ║
║  Bullets (10 pts) — Action verb ratio on bulleted lines                ║
║      Raw 0-10: 0=<0.2, 3=0.2+, 5=0.4+, 8=0.6+, 10=0.8+               ║
║  Metrics (10 pts) — Verified quantified impact metrics preserved       ║
║      Checks: 263K, $500K, -40%, -30hrs, 10+TB from profile            ║
║  Targeting (10 pts) — Experience ordering for Boeing role              ║
║      Points: Boeing/capstone first=5, Cogito Metric=3, NOAA+NRL=2     ║
║  Skills (5 pts) — JD-relevant technical skills mentioned               ║
║      Checks: python, pytorch, tensorflow, sql, docker, k8s, aws,       ║
║      langchain, pinecone, hadoop                                       ║
║  ATS Structure (5 pts) — Clean section headers for parsing             ║
║      Checks: "professional experience" + "education" + "project"       ║
║  Brevity (5 pts) — Word count in target band                           ║
║      10=380-650, 8=320-700, 5=250-800, 3=outside                      ║
║  GSI (10 pts) — Grounded Skill Inference: smart bridging from          ║
║      evidence to adjacent skills without hallucination                 ║
║      Precision (0.6 weight) + Usefulness vs JD (0.4 weight)            ║
║      Penalizes overreach (claiming Spark/Airflow/Kafka not in profile) ║
║                                                                        ║
║  BANDS: >=90 Production-ready | >=80 Strong | >=70 Usable |           ║
║         >=60 Weak | <60 Not deployable                                 ║
║                                                                        ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
import json, os, time, requests, sys, re, numpy as np

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY:
    print("ERROR: OPENROUTER_API_KEY_1 not set"); sys.exit(1)

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
# VERIFIED FACTS (from v4 benchmark)
# ═══════════════════════════════════════════════════════════════════
VERIFIED_EMPLOYERS = ["noaa", "naval research laboratory", "nrl", "washington state",
    "university of maryland", "cern", "everett community college", "wsu", "cogito metric"]
VERIFIED_DEGREES = ["b.s. data analytics", "b.s. physics", "a.a.s. computer science", "bachelor"]
VERIFIED_CERTS = ["network security+", "security+", "comptia", "cybersecurity analyst", "ecc", "data analytics"]
VERIFIED_METRICS = ["263", "500k", "40%", "30", "10+ tb", "13", "1000", "4.0", "2016"]
FORBIDDEN_DEGREES = ["master", "phd", "ph.d", "doctorate", "m.s.", "m.a.", "mba", "m.eng", "m.sc"]
FORBIDDEN_EMPLOYERS = ["google", "microsoft", "amazon", "facebook", "meta", "apple", "netflix", "openai", "anthropic"]
FORBIDDEN_CLEARANCE = ["top secret", "ts/sci", "secret clearance", "ts sci", "sci eligible"]

# ═══════════════════════════════════════════════════════════════════
# HARD GATES (G1-G10) — same as v4 benchmark
# ═══════════════════════════════════════════════════════════════════
# CRITERIA REF: See header block above — G1 through G10
# G1: No invented facts (FORBIDDEN_DEGREES, FORBIDDEN_EMPLOYERS, FORBIDDEN_CLEARANCE)
# G2: Degree integrity (same FORBIDDEN_DEGREES list)
# G3: Identity integrity (name, entity, citizenship)
# G4: Output type (no fences, no preamble)
# G5: Required sections (HEADER, EXPERIENCE, PROJECTS, EDUCATION)
# G6: Word count band (320-700)
# G7: Third-person style (no "I built")
# G8: Contractor signal (C2C/Cogito Metric)
# G9: Boeing relevance
# G10: ATS readability (no tables)
def check_gates(resume_text):
    lower = resume_text.lower()
    report = []; critical = []; non_critical = []

    # G1
    forbidden_deg = [d for d in FORBIDDEN_DEGREES if d in lower]
    forbidden_emp = [e for e in FORBIDDEN_EMPLOYERS if e in lower]
    forbidden_clr = [c for c in FORBIDDEN_CLEARANCE if c in lower]
    if forbidden_deg or forbidden_emp or forbidden_clr:
        details = []
        if forbidden_deg: details.append(f"degrees:{forbidden_deg}")
        if forbidden_emp: details.append(f"employers:{forbidden_emp}")
        if forbidden_clr: details.append(f"clearance:{forbidden_clr}")
        critical.append(("G1", f"Invented facts: {', '.join(details)}"))
    else: report.append(("G1", "PASS"))

    # G2
    if forbidden_deg: critical.append(("G2", f"Unverified degrees: {forbidden_deg}"))
    else: report.append(("G2", "PASS"))

    # G3
    has_name = "jeff calderon" in lower
    has_c2c = "cogito metric" in lower or "c2c" in lower
    has_citizen = "u.s. citizen" in lower or "us citizen" in lower
    if not (has_name and (has_c2c or has_citizen)): critical.append(("G3", "Identity failure"))
    else: report.append(("G3", "PASS"))

    # G4
    has_fence = "```" in resume_text
    has_explanation = any(x in lower[:200] for x in ["here is", "i've written", "below is", "certainly", "sure!"])
    if has_fence or has_explanation: critical.append(("G4", f"Non-resume output"))
    else: report.append(("G4", "PASS"))

    # G5
    has_header = any(x in lower for x in ["jeff calderon", "916.712", "jeff.d.calderon"])
    has_exp = "professional experience" in lower or "work experience" in lower or "experience" in lower[:500]
    has_proj = "project" in lower
    has_edu = "education" in lower
    if not (has_header and has_exp and has_proj and has_edu): non_critical.append(("G5", "Missing sections"))
    else: report.append(("G5", "PASS"))

    # G6
    wc = len(resume_text.split())
    if wc < 320 or wc > 700: non_critical.append(("G6", f"Word count {wc} outside 320-700"))
    else: report.append(("G6", f"PASS ({wc} words)"))

    # G7
    first_person = re.findall(r'\b(I|my|me|we)\s+(built|developed|created|designed|led|managed|implemented|deployed|worked)', lower)
    if first_person: non_critical.append(("G7", f"First-person: {first_person}"))
    else: report.append(("G7", "PASS"))

    # G8
    if not ("c2c" in lower or "cogito metric" in lower): non_critical.append(("G8", "Missing C2C/Cogito"))
    else: report.append(("G8", "PASS"))

    # G9
    if not ("boeing" in lower or "capstone" in lower or "defense" in lower or "h100" in lower or "gpu cluster" in lower):
        non_critical.append(("G9", "No Boeing/defense relevance"))
    else: report.append(("G9", "PASS"))

    # G10
    has_table = "|" in resume_text and resume_text.count("|") > 5
    if has_table: non_critical.append(("G10", "Table markers"))
    else: report.append(("G10", "PASS"))

    return {
        "disqualified": len(critical) > 0,
        "critical_fails": critical,
        "non_critical_fails": non_critical,
        "passes": report,
        "gates_passed": 10 - len(critical) - len(non_critical),
        "critical_count": len(critical),
        "non_critical_count": len(non_critical),
    }

# ═══════════════════════════════════════════════════════════════════
# WEIGHTED SCORECARD (100 pts) — same as v4 benchmark
# ═══════════════════════════════════════════════════════════════════
# CRITERIA REF: See header block above
# Fidelity (35 pts) — factual accuracy
# Alignment (20 pts) — JD theme coverage
# Bullets (10 pts) — action verb ratio
# Metrics (10 pts) — verified quantified impact
# Targeting (10 pts) — Boeing-first ordering
# Skills (5 pts) — technical keyword hits
# ATS Structure (5 pts) — clean section headers
# Brevity (5 pts) — word count band
# GSI (10 pts) — grounded skill inference
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
GSI_FORBIDDEN = [
    "airflow", "spark", "kafka", "terraform", "mlflow", "weights & biases",
    "rlhf", "fairness audit", "ci/cd pipeline", "jenkins", "github actions",
]

def score_gsi(resume_text):
    lower = resume_text.lower()
    inferred = []; unsupported = []
    for evidence, skills in GSI_EVIDENCE_MAP.items():
        if evidence in lower:
            for skill in skills:
                if skill in lower and skill not in inferred:
                    inferred.append(skill)
    for f in GSI_FORBIDDEN:
        if f in lower and f not in CANDIDATE_PROFILE.lower():
            unsupported.append(f)
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
    # Fidelity (35)
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

    # Alignment (20)
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

    # Bullets (10)
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

    # Metrics (10)
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

    # Targeting (10)
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

    # Skills (5)
    sk = ["python", "pytorch", "tensorflow", "sql", "docker", "kubernetes", "aws", "langchain", "pinecone", "hadoop"]
    sh = sum(1 for k in sk if k in lower)
    if sh >= 9: skills_raw = 10
    elif sh >= 7: skills_raw = 8
    elif sh >= 5: skills_raw = 5
    elif sh >= 3: skills_raw = 3
    else: skills_raw = 0
    details["skills"] = {"raw": skills_raw, "weighted": round(skills_raw/10*5, 1)}

    # ATS (5)
    clean_headers = "professional experience" in lower and "education" in lower and "project" in lower
    if clean_headers: ats_raw = 10
    elif "experience" in lower and "education" in lower: ats_raw = 5
    else: ats_raw = 3
    details["ats_structure"] = {"raw": ats_raw, "weighted": round(ats_raw/10*5, 1)}

    # Brevity (5)
    wc = len(resume_text.split())
    if 380 <= wc <= 650: brevity_raw = 10
    elif 320 <= wc <= 700: brevity_raw = 8
    elif 250 <= wc <= 800: brevity_raw = 5
    else: brevity_raw = 3
    details["brevity"] = {"raw": brevity_raw, "weighted": round(brevity_raw/10*5, 1), "words": wc}

    # GSI (10)
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
# CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════════
FUSION_CONFIGS = [
    {
        "label": "Fusion-A: GLM 5.1 judge + KatCoder/MiMo/DeepSeek panel",
        "analysis_models": ["kwaipilot/kat-coder-pro-v2", "xiaomi/mimo-v2.5-pro", "deepseek/deepseek-v4-pro"],
        "judge_model": "z-ai/glm-5.1",
    },
    {
        "label": "Fusion-B: DeepSeek judge + KatCoder/MiMo/GLM panel",
        "analysis_models": ["kwaipilot/kat-coder-pro-v2", "xiaomi/mimo-v2.5-pro", "z-ai/glm-5.1"],
        "judge_model": "deepseek/deepseek-v4-pro",
    },
]

headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def call_and_score(payload, label):
    sys.stdout.write(f"\n  [{label}] Calling... "); sys.stdout.flush()
    start = time.time()
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
                             headers=headers, json=payload, timeout=300)
        elapsed = time.time() - start
        if resp.status_code == 200:
            d = resp.json()
            raw = d["choices"][0]["message"].get("content", "") or ""
            resume = re.sub(r'^```[\w]*\n?', '', raw)
            resume = re.sub(r'\n?```$', '', resume)
            resume = resume.strip()
            usage = d.get("usage", {})
            gates = check_gates(resume)
            sc, det = (0, {"total": 0, "band": "DQ"}) if gates["disqualified"] else weighted_score(resume)
            print(f"HTTP 200 | {elapsed:.1f}s | {len(resume.split())}w | Gates:{gates['gates_passed']}/10 | Score:{sc:.1f}")
            return {
                "ok": True, "content": resume, "word_count": len(resume.split()),
                "latency_s": round(elapsed, 2),
                "tokens_total": usage.get("total_tokens", 0),
                "tokens_prompt": usage.get("prompt_tokens", 0),
                "tokens_completion": usage.get("completion_tokens", 0),
                "model_used": d.get("model", "unknown"),
                "gates": gates, "score": sc, "band": det.get("band","N/A"), "details": det,
            }
        else:
            print(f"HTTP {resp.status_code}")
            return {"ok": False, "error": resp.text[:300], "latency_s": round(elapsed, 2)}
    except Exception as e:
        print(f"EXC: {str(e)[:80]}")
        return {"ok": False, "error": str(e)[:300], "latency_s": round(time.time()-start, 2)}

# ═══════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════
print("=" * 80)
print("FUSION CONFIG TEST — 3 Fusion calls with V4 scoring")
print("=" * 80)

results = []

for cfg in FUSION_CONFIGS:
    payload = {
        "model": "openrouter/fusion",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_MSG},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
    }
    if cfg["analysis_models"] is not None:
        payload["plugins"] = [{
            "id": "fusion",
            "analysis_models": cfg["analysis_models"],
            "model": cfg["judge_model"],
            "max_tool_calls": 2,
        }]
    r = call_and_score(payload, cfg["label"])
    r["config"] = cfg["label"]
    r["analysis_models"] = cfg["analysis_models"]
    r["judge_model"] = cfg["judge_model"]
    results.append(r)
    time.sleep(3)

# ═══════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SUMMARY TABLE")
print("=" * 80)
print(f"{'Config':<55} {'Score':>6} {'Band':<20} {'Gates':>6} {'Tokens':>7} {'Words':>6} {'Lat':>5}")
print("-" * 110)

for r in results:
    if r["ok"]:
        print(f"{r['config']:<55} {r['score']:>6.1f} {r['band']:<20} {r['gates']['gates_passed']:>4}/10 {r['tokens_total']:>7} {r['word_count']:>6} {r['latency_s']:>4.1f}s")
    else:
        print(f"{r['config']:<55} {'FAIL':>6} {'N/A':<20} {'-':>6} {'-':>7} {'-':>6} {'-':>5}")

print("-" * 110)

# Score breakdown for ok runs
print("\n" + "=" * 80)
print("SCORE BREAKDOWN")
print("=" * 80)
for r in results:
    if r["ok"] and r.get("details"):
        d = r["details"]
        print(f"\n{r['config']}:")
        print(f"  TOTAL: {d['total']:.1f} [{d['band']}]")
        for cat in ["fidelity","alignment","bullets","metrics","targeting","skills","ats_structure","brevity","gsi"]:
            v = d.get(cat, {})
            extra = ""
            if cat == "gsi" and v.get("inferred"):
                extra = f" → {v['inferred'][:3]}"
            if cat == "brevity":
                extra = f" ({v.get('words','')}w)"
            print(f"  {cat:<15}: {v['weighted']:>5.1f}{extra}")

# Save
out = {
    "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "results": results,
}
with open("fusion_config_test_results.json", "w") as f:
    json.dump(out, f, indent=2, default=str)

print(f"\nSaved to fusion_config_test_results.json")
print("\nCHECK YOUR OPENROUTER LOGS NOW to verify which panel models appear for each Fusion call.")
