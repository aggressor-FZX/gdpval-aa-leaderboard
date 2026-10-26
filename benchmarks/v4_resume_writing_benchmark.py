#!/usr/bin/env python3
"""
V4 RESUME WRITING BENCHMARK — Gated + Weighted + Grounded Skill Inference
========================================================================
9 models × 3 runs each = 27 total runs.
Hard gates (G1-G10) → Disqualified/Scorable
Weighted 100-pt scorecard with Grounded Skill Inference (GSI) category.
Max/high effort where supported.
"""
import json, os, time, requests, sys, re, numpy as np
from collections import Counter

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY: print("ERROR: OPENROUTER_API_KEY_1 not set"); sys.exit(1)

# ═══════════════════════════════════════════════════════════════════
# PROMPTS (same as V3)
# ═══════════════════════════════════════════════════════════════════
JD_TEXT = """Data Scientist (Data Science) - Boeing Defense, Space & Security

Seeking a Mid-Level Data Scientist - GenAI. Role involves developing and optimizing advanced AI, ML, and GenAI models within BDS. Work with senior data scientists and cross-functional teams on AI-driven applications.

Required: Bachelor's in CS, ML, Math, CE, SE, AI, Physics or related. 3+ years data science or ML. 3+ years Python programming and familiarity with data engineering (Spark, Airflow, SQL).

Preferred: Master's or PhD in related field. Experience fine-tuning open-source models and integrating APIs. Deep learning frameworks (PyTorch, TensorFlow). AI ethics and governance for generative models. Data engineering tools (SQL, Spark, Airflow).

Position Responsibilities:
- Develop and deploy models
- Design pipelines for model fine-tuning and evaluation
- Develop prompt engineering strategies and embedding techniques
- Prototype applications addressing business needs
- Assist in model performance evaluation and bias/fairness assessments
- Collaborate with MLOps and engineering teams for model scaling and monitoring
- Share AI/ML/GenAI knowledge and best practices

Successful candidates have: Proficiency with deep learning frameworks (PyTorch, TensorFlow). Experience developing GenAI solutions in regulated industries. Familiarity with GPU compute infrastructure and distributed training. Familiarity with container technologies (Docker, Kubernetes).

U.S. Person required. Hybrid role in Seattle, WA or Arlington, VA."""

CANDIDATE_PROFILE = """VERIFIED CANDIDATE FACTS — DO NOT INVENT ANYTHING OUTSIDE THIS PROFILE:

Name: Jeff Calderon
Entity: Cogito Metric LLC (cogitometric.ai) — C2C available
Contact: 916.712.8396 | jeff.d.calderon@gmail.com | Marysville, WA | U.S. Citizen
GitHub: github.com/aggressor-FZX | LinkedIn: linkedin.com/in/jeffdcalderon

Positioning: Data scientist and ML engineer with 10+ years in statistical modeling, NLP, and production AI. Built a live semantic-search and LLM platform (embeddings, RAG, multi-agent workflows). Physics background with peer-reviewed publication; Security+ certified; prior classified national security work (NRL). Available for C2C.

TECHNICAL SKILLS:
NLP/ML: PyTorch, TensorFlow, Scikit-learn, LangChain, LangGraph, Hugging Face; transformer architectures; text classification, sentiment analysis, entity recognition, semantic embeddings; RAG pipeline design; vector search (Pinecone); LLM fine-tuning, prompt engineering; anomaly detection; multi-agent orchestration.
Large-Scale Data: Python (Pandas, NumPy, Boto3), SQL, Hadoop/HDFS, distributed computing, AWS (Lambda, Glue, Step Functions, S3, IAM), pipeline design, ETL at scale.
Security & Research: CompTIA Network Security+, Cybersecurity Analyst (ECC), classified NRL environment, experimental design, Monte Carlo simulation, peer-reviewed publication, Git, Docker, Linux.

PROFESSIONAL EXPERIENCE:
1. Data Analyst Intern — Washington State Data Exchange for Public Safety (04/2025-Present): ETL, Python/SQL, Power BI, variance reports for law enforcement/EMS.
2. Operations Manager — NOAA (12/2019-05/2023): Python stats/models for 13-vessel fleet; exec reporting; -40% reporting overhead.
3. Marine Data Analyst — NOAA Commissioned Officer Corps (12/2016-05/2019): 10+ TB multi-sensor data; unsupervised ML/anomaly detection; -30 hrs/week via automation.
4. Research Physicist — U.S. Naval Research Laboratory (01/2014-06/2016): Monte Carlo simulation (Python, C++) for probabilistic risk quantification; classified environment; secured $500K federal R&D funding.
5. Faculty Assistant Researcher — UMD/CERN (01/2013-04/2015): Hadoop + LHC grid on multi-TB datasets; gradient-based solvers; co-authored J. Instrumentation (2016).

KEY PROJECTS:
- Cogito Metric NLP Platform (2024-Present): Production platform ingesting unstructured text → embeddings → multi-agent LLM workflows; RAG with LangChain + Pinecone; REST APIs on AWS Lambda.
- Boeing Defense Capstone (08/2025-05/2026): Trained/fine-tuned generative models on 263K+ image datasets across H100/A100 GPU clusters; Docker/Kubernetes orchestration; MLOps standards.
- Monte Carlo Risk Modeling — NRL: Probabilistic detection algorithms; classified environment; briefed non-technical program directors.

EDUCATION:
- B.S. Data Analytics, Washington State University (05/2026, 4.0 GPA)
- B.S. Physics, University of Maryland (12/2015)
- A.A.S. Computer Science, Everett CC (4.0 GPA)

CERTIFICATIONS:
- Network Security+, CompTIA (07/2024)
- Cybersecurity Analyst, Everett Community College (07/2024)
- Data Analytics, Washington State University (12/2024)

ANTI-PATTERNS (DO NOT DO):
- Do NOT invent employers, degrees, certs, clearance levels, or metrics not listed above.
- Do NOT claim Master's or PhD — candidate has Bachelor's degrees only.
- Do NOT use first person ("I built..."). Use third-person action verbs.
- Keep to roughly one page of content."""

SYSTEM_PROMPT = """You are an expert ATS-optimized resume writer for data science and ML roles.

TASK: Write a tailored resume for the JOB DESCRIPTION below, using ONLY the VERIFIED CANDIDATE FACTS provided. 

RULES:
1. Output the resume as plain text with clear section headers (HEADER, PROFESSIONAL EXPERIENCE, PROJECTS, EDUCATION & CERTIFICATIONS).
2. Map the candidate's experience to the job requirements using the keywords from the JD.
3. Start each bullet with a strong action verb. Include quantified metrics wherever possible.
4. Do NOT invent employers, degrees, certifications, tools, or metrics outside the verified facts.
5. Keep to roughly one page of content (about 400-600 words).
6. Include "C2C available" or "Cogito Metric LLC" since the candidate is a contractor.
7. Match the JD's language: this is a GenAI/Data Science role at Boeing Defense. Emphasize the Boeing capstone project, GPU/distributed training, GenAI platform work, and security credentials.
8. Output ONLY the resume text. No explanations, no markdown fences, no commentary."""

# ═══════════════════════════════════════════════════════════════════
# VERIFIED FACTS FOR GATE CHECKING
# ═══════════════════════════════════════════════════════════════════
VERIFIED_EMPLOYERS = ["noaa", "naval research laboratory", "nrl", "washington state",
    "university of maryland", "cern", "everett community college", "wsu", "cogito metric"]
VERIFIED_DEGREES = ["b.s. data analytics", "b.s. physics", "a.a.s. computer science", "bachelor"]
VERIFIED_CERTS = ["network security+", "security+", "comptia", "cybersecurity analyst", "ecc", "data analytics"]
VERIFIED_METRICS = ["263", "500k", "40%", "30", "10+ tb", "13", "1000", "4.0", "2016"]
VERIFIED_LOCATIONS = ["marysville", "wa", "washington", "seattle", "everett"]
FORBIDDEN_DEGREES = ["master", "phd", "ph.d", "doctorate", "m.s.", "m.a.", "mba", "m.eng", "m.sc"]
FORBIDDEN_EMPLOYERS = ["google", "microsoft", "amazon", "facebook", "meta", "apple", "netflix", "openai", "anthropic"]
FORBIDDEN_CLEARANCE = ["top secret", "ts/sci", "secret clearance", "ts sci", "sci eligible"]

# ═══════════════════════════════════════════════════════════════════
# HARD GATES (G1-G10)
# ═══════════════════════════════════════════════════════════════════
def check_gates(resume_text):
    """Run all 10 hard gates. Returns (passed, critical_fails, non_critical, report)."""
    lower = resume_text.lower()
    report = []
    critical = []
    non_critical = []

    # G1: No invented facts
    forbidden_deg = [d for d in FORBIDDEN_DEGREES if d in lower]
    forbidden_emp = [e for e in FORBIDDEN_EMPLOYERS if e in lower]
    forbidden_clr = [c for c in FORBIDDEN_CLEARANCE if c in lower]
    if forbidden_deg or forbidden_emp or forbidden_clr:
        details = []
        if forbidden_deg: details.append(f"degrees:{forbidden_deg}")
        if forbidden_emp: details.append(f"employers:{forbidden_emp}")
        if forbidden_clr: details.append(f"clearance:{forbidden_clr}")
        critical.append(("G1", f"Invented facts: {', '.join(details)}"))
    else:
        report.append(("G1", "PASS"))

    # G2: Degree integrity
    if forbidden_deg:
        critical.append(("G2", f"Unverified degrees: {forbidden_deg}"))
    else:
        report.append(("G2", "PASS"))

    # G3: Identity integrity
    has_name = "jeff calderon" in lower
    has_c2c = "cogito metric" in lower or "c2c" in lower
    has_citizen = "u.s. citizen" in lower or "us citizen" in lower
    if not (has_name and (has_c2c or has_citizen)):
        missing = []
        if not has_name: missing.append("name")
        if not has_c2c: missing.append("contractor entity")
        if not has_citizen: missing.append("citizenship")
        critical.append(("G3", f"Identity failure: missing {missing}"))
    else:
        report.append(("G3", "PASS"))

    # G4: Output is resume only (no explanations, no markdown fences, no meta)
    has_fence = "```" in resume_text
    has_explanation = any(x in lower[:200] for x in ["here is", "i've written", "below is", "certainly", "sure!"])
    if has_fence or has_explanation:
        critical.append(("G4", f"Non-resume output: fence={has_fence} explanation={has_explanation}"))
    else:
        report.append(("G4", "PASS"))

    # G5: Required sections
    has_header = any(x in lower for x in ["jeff calderon", "916.712", "jeff.d.calderon"])
    has_exp = "professional experience" in lower or "work experience" in lower or "experience" in lower[:500]
    has_proj = "project" in lower
    has_edu = "education" in lower
    sections_ok = has_header and has_exp and has_proj and has_edu
    if not sections_ok:
        missing_sections = []
        if not has_header: missing_sections.append("HEADER")
        if not has_exp: missing_sections.append("EXPERIENCE")
        if not has_proj: missing_sections.append("PROJECTS")
        if not has_edu: missing_sections.append("EDUCATION")
        non_critical.append(("G5", f"Missing sections: {missing_sections}"))
    else:
        report.append(("G5", "PASS"))

    # G6: Word count band (320-700, target 400-600)
    wc = len(resume_text.split())
    if wc < 320 or wc > 700:
        non_critical.append(("G6", f"Word count {wc} outside 320-700 band"))
    else:
        report.append(("G6", f"PASS ({wc} words)"))

    # G7: Third-person (no first person in bullets)
    first_person = re.findall(r'\b(I|my|me|we)\s+(built|developed|created|designed|led|managed|implemented|deployed|worked)', lower)
    if first_person:
        non_critical.append(("G7", f"First-person language: {first_person}"))
    else:
        report.append(("G7", "PASS"))

    # G8: Contractor signal
    if not ("c2c" in lower or "cogito metric" in lower):
        non_critical.append(("G8", "Missing C2C/Cogito Metric signal"))
    else:
        report.append(("G8", "PASS"))

    # G9: Boeing relevance
    if not ("boeing" in lower or "capstone" in lower or "defense" in lower or "h100" in lower or "gpu cluster" in lower):
        non_critical.append(("G9", "No Boeing/defense relevance found"))
    else:
        report.append(("G9", "PASS"))

    # G10: ATS readability (no tables, no multi-column layout markers)
    has_table_markers = "|" in resume_text and resume_text.count("|") > 5
    has_decorative = any(c in resume_text for c in ["═══", "───", "══", "──"])
    if has_table_markers:
        non_critical.append(("G10", "Table/multi-column markers detected"))
    elif has_decorative and resume_text.count("─") > 20:
        non_critical.append(("G10", "Excessive decorative characters"))
    else:
        report.append(("G10", "PASS"))

    # Determine disqualification
    disqualified = len(critical) > 0
    all_gates_passed = len(critical) == 0 and len(non_critical) == 0

    return {
        "disqualified": disqualified,
        "all_passed": all_gates_passed,
        "critical_fails": critical,
        "non_critical_fails": non_critical,
        "passes": report,
        "gates_passed": 10 - len(critical) - len(non_critical),
        "critical_count": len(critical),
        "non_critical_count": len(non_critical),
    }

# ═══════════════════════════════════════════════════════════════════
# GROUNDED SKILL INFERENCE (GSI) — 10 pts
# ═══════════════════════════════════════════════════════════════════
# Map: profile evidence → well-supported adjacent skills
GSI_EVIDENCE_MAP = {
    "h100": ["distributed training", "gpu infrastructure", "multi-gpu", "gpu compute", "accelerated computing"],
    "a100": ["distributed training", "gpu infrastructure", "multi-gpu", "gpu compute"],
    "docker": ["containerization", "container orchestration", "containerized", "container"],
    "kubernetes": ["container orchestration", "containerized deployment", "cluster management", "container"],
    "pytorch ddp": ["distributed training", "multi-gpu training", "parallel training"],
    "langchain": ["retrieval-augmented generation", "rag", "llm orchestration", "agent framework"],
    "pinecone": ["vector database", "vector search", "embedding-based search", "similarity search"],
    "embeddings": ["representation learning", "semantic search", "vector embeddings", "embedding-based retrieval"],
    "llm fine-tuning": ["model adaptation", "transfer learning"],
    "semantic search": ["information retrieval", "retrieval systems"],
    "rest api": ["api development", "model serving", "inference endpoint"],
    "aws lambda": ["serverless", "cloud functions", "scalable inference"],
    "monte carlo": ["simulation", "probabilistic modeling", "risk assessment", "uncertainty quantification"],
    "anomaly detection": ["outlier detection", "pattern recognition", "unsupervised learning"],
    "mlops": ["model versioning", "reproducibility", "experiment tracking", "evaluation"],
    "classified": ["regulated environment", "governance", "compliance", "security-cleared"],
    "security+": ["cybersecurity", "secure development", "infosec"],
}
# Skills that are too far from evidence — penalize if claimed as direct experience
GSI_FORBIDDEN_INFERENCE = [
    "airflow", "spark", "kafka", "terraform", "mlflow", "weights & biases",
    "rlhf", "fairness audit", "ai governance lead", "responsible ai lead",
    "dataops", "feature store", "model registry", "a/b testing framework",
    "ci/cd pipeline", "jenkins", "github actions",
]

def score_gsi(resume_text):
    """Score grounded skill inference from 0-10."""
    lower = resume_text.lower()
    inferred = []
    supported = []
    unsupported = []

    for evidence, adjacent_skills in GSI_EVIDENCE_MAP.items():
        if evidence in lower:
            for skill in adjacent_skills:
                if skill in lower:
                    if skill not in inferred:
                        inferred.append(skill)
                        supported.append(skill)

    # Check for overreach
    for forbidden in GSI_FORBIDDEN_INFERENCE:
        if forbidden in lower:
            has_direct = False
            # Check if profile actually supports it
            profile_lower = CANDIDATE_PROFILE.lower()
            # These skills are NEVER in the profile, so if claimed as experience it's unsupported
            if forbidden not in profile_lower:
                unsupported.append(forbidden)

    # Also check if inferred skills are in profile (they shouldn't be — GSI is about NEW inferences)
    actual_inferred = [s for s in inferred if s not in CANDIDATE_PROFILE.lower()]

    total_inferred = len(actual_inferred) + len(unsupported)
    if total_inferred == 0:
        return {"score": 0, "precision": 1.0, "usefulness": 0.0, "inferred": [], "unsupported": [], "note": "No skill inference attempted"}

    precision = len(actual_inferred) / total_inferred if total_inferred > 0 else 1.0

    # Usefulness: how many inferred skills match JD keywords
    jd_keywords = ["distributed training", "gpu", "evaluation", "pipeline", "container", "governance", "regulated", "fine-tun", "embedding", "deploy", "mlops"]
    useful_inferred = [s for s in actual_inferred if any(kw in s for kw in jd_keywords)]
    usefulness = len(useful_inferred) / max(total_inferred, 1)

    # Combine into 0-10 score
    # Weight: precision 0.6, usefulness 0.4
    raw = (precision * 0.6 + usefulness * 0.4) * 10

    # Scale based on how many valid inferences (quality over quantity)
    # 1-2 good inferences = cap at 8, 3+ = full 10
    if len(actual_inferred) >= 3: cap = 10
    elif len(actual_inferred) >= 1: cap = 8
    else: cap = 5
    gsi_score = min(raw, cap)

    return {
        "score": round(gsi_score),
        "precision": round(precision, 2),
        "usefulness": round(usefulness, 2),
        "inferred_supported": actual_inferred,
        "inferred_unsupported": unsupported,
        "count_supported": len(actual_inferred),
        "count_total": total_inferred,
    }

# ═══════════════════════════════════════════════════════════════════
# WEIGHTED SCORECARD (100 pts)
# ═══════════════════════════════════════════════════════════════════
def weighted_score(resume_text):
    """Full weighted scoring: 35+20+10+10+10+5+5+5 = 100"""
    lower = resume_text.lower()
    details = {}

    # Factual fidelity (35) — anchored: check forbidden words, verified content presence
    forbidden_count = sum(1 for w in FORBIDDEN_DEGREES + FORBIDDEN_EMPLOYERS + FORBIDDEN_CLEARANCE if w in lower)
    employer_hits = sum(1 for e in VERIFIED_EMPLOYERS if e in lower)
    degree_hits = sum(1 for d in VERIFIED_DEGREES if d in lower)
    cert_hits = sum(1 for c in VERIFIED_CERTS if c in lower)
    metric_hits = sum(1 for m in VERIFIED_METRICS if m in lower)

    if forbidden_count >= 2: fidelity_raw = 0
    elif forbidden_count == 1: fidelity_raw = 3
    elif employer_hits >= 4 and degree_hits >= 2 and cert_hits >= 3: fidelity_raw = 10
    elif employer_hits >= 3: fidelity_raw = 8
    else: fidelity_raw = 5
    details["fidelity"] = {"raw": fidelity_raw, "weighted": round(fidelity_raw / 10 * 35, 1), "forbidden": forbidden_count, "employers": employer_hits, "degrees": degree_hits, "certs": cert_hits}

    # JD alignment (20)
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
    theme_scores = {}
    for theme, keywords in jd_themes.items():
        hits = sum(1 for kw in keywords if kw in lower)
        theme_scores[theme] = min(hits, 1)
    alignment_raw = sum(theme_scores.values())
    scaled = alignment_raw / len(jd_themes) * 10
    # Map scale: 0 → 0, 1-2 → 3, 3-4 → 5, 5-6 → 8, 7-8 → 10
    if scaled >= 9: align_raw = 10
    elif scaled >= 7: align_raw = 8
    elif scaled >= 5: align_raw = 5
    elif scaled >= 3: align_raw = 3
    else: align_raw = 0
    details["alignment"] = {"raw": align_raw, "weighted": round(align_raw / 10 * 20, 1), "themes": theme_scores}

    # Bullet quality (10)
    lines = resume_text.split("\n")
    bullets = [l.strip() for l in lines if l.strip().startswith(("-", "•", "*"))]
    action_verbs = ["developed","built","designed","deployed","implemented","architected","led","managed","created","applied","trained","fine-tuned","reduced","improved","optimized","automated","secured","delivered","collaborated","spearheaded","integrated","engineered","analyzed","processed","orchestrated","directed","established"]
    verb_count = sum(1 for b in bullets for v in action_verbs if b.lower().strip("-•* ").startswith(v))
    verb_ratio = verb_count / max(len(bullets), 1)
    avg_bullet_len = sum(len(b.split()) for b in bullets) / max(len(bullets), 1)
    if verb_ratio >= 0.8 and 8 <= avg_bullet_len <= 25: bullet_raw = 10
    elif verb_ratio >= 0.6 and 6 <= avg_bullet_len <= 30: bullet_raw = 8
    elif verb_ratio >= 0.4: bullet_raw = 5
    elif verb_ratio >= 0.2: bullet_raw = 3
    else: bullet_raw = 0
    details["bullets"] = {"raw": bullet_raw, "weighted": round(bullet_raw / 10 * 10, 1), "count": len(bullets), "verb_ratio": round(verb_ratio, 2)}

    # Quantified impact (10)
    metric_pattern = r'\b(\d+[\+\-]?\s*(%|TB|hours|week|vessel|K|million|M|billion)?)\b'
    metric_mentions = len(re.findall(metric_pattern, lower))
    has_263k = "263" in lower
    has_500k = "500k" in lower or "500" in lower and "funding" in lower
    has_40pct = "40%" in lower or "40 %" in lower
    has_30hr = "30" in lower and ("hour" in lower or "week" in lower)
    has_10tb = "10" in lower and "tb" in lower
    verified_metrics_count = sum([has_263k, has_500k, has_40pct, has_30hr, has_10tb])
    if verified_metrics_count >= 4: metrics_raw = 10
    elif verified_metrics_count >= 3: metrics_raw = 8
    elif verified_metrics_count >= 2: metrics_raw = 5
    elif verified_metrics_count >= 1: metrics_raw = 3
    else: metrics_raw = 0
    details["metrics"] = {"raw": metrics_raw, "weighted": round(metrics_raw / 10 * 10, 1), "verified_count": verified_metrics_count}

    # Experience targeting (10)
    boeing_first = "boeing" in lower[:500] or "capstone" in lower[:300]
    has_cogito = "cogito metric" in lower or "nlp platform" in lower
    has_noaa = "noaa" in lower
    has_nrl = "naval research" in lower or "nrl" in lower
    exp_order = 0
    if boeing_first: exp_order += 5
    if has_cogito: exp_order += 3
    if has_noaa and has_nrl: exp_order += 2
    elif has_noaa or has_nrl: exp_order += 1
    if exp_order >= 8: targeting_raw = 10
    elif exp_order >= 6: targeting_raw = 8
    elif exp_order >= 4: targeting_raw = 5
    elif exp_order >= 2: targeting_raw = 3
    else: targeting_raw = 0
    details["targeting"] = {"raw": targeting_raw, "weighted": round(targeting_raw / 10 * 10, 1), "boeing_first": boeing_first}

    # Skills coverage (5)
    skill_keywords = ["python", "pytorch", "tensorflow", "sql", "docker", "kubernetes", "aws", "langchain", "pinecone", "hadoop"]
    skill_hits = sum(1 for k in skill_keywords if k in lower)
    if skill_hits >= 9: skills_raw = 10
    elif skill_hits >= 7: skills_raw = 8
    elif skill_hits >= 5: skills_raw = 5
    elif skill_hits >= 3: skills_raw = 3
    else: skills_raw = 0
    details["skills"] = {"raw": skills_raw, "weighted": round(skills_raw / 10 * 5, 1), "hits": skill_hits}

    # ATS structure (5)
    clean_headers = "professional experience" in lower and "education" in lower and "project" in lower
    reverse_chrono = lower.find("2025") < lower.find("2019") or lower.find("present") < lower.find("2019")
    has_sections = lower.count("professional experience") + lower.count("education") + lower.count("project") >= 3
    if clean_headers and reverse_chrono and has_sections: ats_raw = 10
    elif clean_headers and has_sections: ats_raw = 8
    elif has_sections: ats_raw = 5
    elif clean_headers: ats_raw = 3
    else: ats_raw = 0
    details["ats_structure"] = {"raw": ats_raw, "weighted": round(ats_raw / 10 * 5, 1)}

    # Brevity and focus (5)
    wc = len(resume_text.split())
    if 380 <= wc <= 650: brevity_raw = 10
    elif 320 <= wc <= 700: brevity_raw = 8
    elif 250 <= wc <= 800: brevity_raw = 5
    elif wc >= 800: brevity_raw = 3
    else: brevity_raw = 0
    details["brevity"] = {"raw": brevity_raw, "weighted": round(brevity_raw / 10 * 5, 1), "words": wc}

    # Grounded Skill Inference (10 — replaces old "extra" category)
    gsi = score_gsi(resume_text)
    details["gsi"] = {"raw": gsi["score"], "weighted": round(gsi["score"] / 10 * 10, 1), "inferred": gsi.get("inferred", gsi.get("inferred_supported", [])), "unsupported": gsi.get("unsupported", gsi.get("inferred_unsupported", [])), "precision": gsi["precision"], "usefulness": gsi["usefulness"]}

    # Total
    total = sum(details[k]["weighted"] for k in ["fidelity", "alignment", "bullets", "metrics", "targeting", "skills", "ats_structure", "brevity", "gsi"])
    details["total"] = round(min(total, 100), 1)

    # Decision band
    if details["total"] >= 90: band = "Production-ready"
    elif details["total"] >= 80: band = "Strong candidate"
    elif details["total"] >= 70: band = "Usable with edits"
    elif details["total"] >= 60: band = "Weak"
    else: band = "Not deployable"
    details["band"] = band

    return details["total"], details

# ═══════════════════════════════════════════════════════════════════
# MODEL LIST — 9 models
# ═══════════════════════════════════════════════════════════════════
MODELS = [
    ("qwen/qwen3-235b-a22b-thinking-2507", "Qwen 3 235B Thinking", 0.10, 0.10, True),
    ("x-ai/grok-4.3",                      "Grok 4.3",             1.25, 2.50, False),
    ("xiaomi/mimo-v2.5-pro",               "MiMo V2.5 Pro",        0.43, 0.87, False),
    ("anthracite-org/magnum-v4-72b",        "Magnum V4 72B",        3.00, 5.00, False),
    ("openai/gpt-5",                        "GPT-5",                1.25, 10.00, False),
    ("openrouter/fusion",                   "OpenRouter Fusion",    50.00, 100.00, False),  # Multi-model orchestration cost
    ("z-ai/glm-5.1",                        "GLM 5.1",              0.98, 3.08, False),
    ("kwaipilot/kat-coder-pro-v2",          "Kat Coder Pro V2",     0.30, 1.20, False),
    ("moonshotai/kimi-k2.6",                "Kimi K2.6",            0.68, 3.41, False),
]

# ═══════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════
def call_model(model_id, is_reasoning=False, tries=2):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"JOB DESCRIPTION:\n\n{JD_TEXT}\n\nCANDIDATE PROFILE:\n\n{CANDIDATE_PROFILE}\n\nWrite the tailored resume now."}
    ]
    p = {"model": model_id, "messages": msgs, "temperature": 0.0 if not is_reasoning else 0.3, "max_tokens": 4096}
    if is_reasoning:
        p["reasoning"] = {"effort": "high"}
    resp = None; start = time.time()
    for attempt in range(tries):
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=h, json=p, timeout=300)
            elapsed = time.time() - start
            resp.raise_for_status()
            d = resp.json()
            u = d.get("usage", {})
            content = d["choices"][0]["message"].get("content") or ""
            if not content or content.strip() == "":
                content = d["choices"][0]["message"].get("reasoning") or ""
            return {"ok": True, "content": content, "latency": round(elapsed, 2), "tokens": u.get("total_tokens", 0)}
        except Exception as e:
            if attempt < tries - 1: time.sleep(2); continue
            elapsed = time.time() - start; err = str(e)[:200]
            if resp is not None:
                try: err += f" | {resp.text[:300]}"
                except: pass
            return {"ok": False, "content": None, "latency": round(elapsed, 2), "tokens": 0, "error": err[:300]}

RUNS_PER_MODEL = 3
print("=" * 100)
print(f"V4 RESUME WRITING BENCHMARK — {len(MODELS)} models × {RUNS_PER_MODEL} runs")
print("Hard gates (G1-G10) → Weighted scorecard (100 pts) → Grounded Skill Inference")
print("=" * 100)

all_runs = []

for model_id, label, price_in, price_out, is_reasoning in MODELS:
    blended = (price_in * 3 + price_out) / 4
    print(f"\n{'='*100}")
    print(f"  {label} ({model_id}) — ${blended:.3f}/M {'[REASONING/HIGH EFFORT]' if is_reasoning else ''}")
    print(f"{'='*100}")

    model_runs = []
    for run_num in range(1, RUNS_PER_MODEL + 1):
        sys.stdout.write(f"  Run {run_num}/{RUNS_PER_MODEL}... "); sys.stdout.flush()
        r = call_model(model_id, is_reasoning)

        if not r["ok"] or not r["content"]:
            print(f"FAIL ({r.get('error', 'unknown')[:60]})")
            model_runs.append({"run": run_num, "ok": False, "error": r.get("error", "unknown")[:200]})
            continue

        resume = re.sub(r'^```[\w]*\n?', '', r["content"])
        resume = re.sub(r'\n?```$', '', resume)
        resume = resume.strip()

        # GATES
        gates = check_gates(resume)

        if gates["disqualified"]:
            print(f"DISQUALIFIED — {gates['critical_count']} critical fails: {[c[1] for c in gates['critical_fails']]}")
            model_runs.append({"run": run_num, "ok": True, "disqualified": True, "gates": gates, "latency": r["latency"], "tokens": r["tokens"]})
            continue

        # WEIGHTED SCORING (only for scorable runs)
        sc, det = weighted_score(resume)
        cost = (r["tokens"] / 1_000_000) * blended

        nf = gates["non_critical_count"]
        print(f"Score: {sc:.1f}/100 [{det['band']}] | {gates['gates_passed']}/10 gates (+{nf} non-critical) | {r['tokens']}tk | {r['latency']}s | GSI:{det['gsi']['raw']}")

        model_runs.append({
            "run": run_num, "ok": True, "disqualified": False,
            "score": sc, "band": det["band"],
            "gates": gates, "details": det,
            "latency": r["latency"], "tokens": r["tokens"], "cost": round(cost, 6),
        })

    # Model summary: average top N runs (or all scored runs if <3)
    scored_runs = [r for r in model_runs if not r.get("disqualified") and r.get("score", 0) > 0]
    disqualified = [r for r in model_runs if r.get("disqualified")]
    failed = [r for r in model_runs if not r.get("ok")]

    if len(scored_runs) >= 2:
        scored_runs.sort(key=lambda x: -x["score"])
        top3 = scored_runs[:3]
        avg_score = sum(r["score"] for r in top3) / len(top3)
        avg_fidelity = sum(r["details"]["fidelity"]["weighted"] for r in top3) / len(top3)
        avg_alignment = sum(r["details"]["alignment"]["weighted"] for r in top3) / len(top3)
        best = top3[0]["score"]
        variance = round(np.var([r["score"] for r in top3]), 2) if len(top3) > 1 else 0
    elif len(scored_runs) == 1:
        avg_score = scored_runs[0]["score"]
        avg_fidelity = scored_runs[0]["details"]["fidelity"]["weighted"]
        avg_alignment = scored_runs[0]["details"]["alignment"]["weighted"]
        best = avg_score; variance = 0
    else:
        avg_score = 0; avg_fidelity = 0; avg_alignment = 0; best = 0; variance = 0

    pass_rate = len(scored_runs) / RUNS_PER_MODEL
    dq_rate = len(disqualified) / RUNS_PER_MODEL
    fail_rate = len(failed) / RUNS_PER_MODEL

    print(f"  ── SUMMARY: avg={avg_score:.1f} best={best:.1f} var={variance:.2f} | pass={pass_rate:.0%} dq={dq_rate:.0%} fail={fail_rate:.0%} | fid={avg_fidelity:.1f} align={avg_alignment:.1f}")

    all_runs.append({
        "model": label, "model_id": model_id,
        "price_blended": round(blended, 4),
        "runs": model_runs,
        "summary": {
            "avg_score": round(avg_score, 1), "best_score": best,
            "variance": variance, "pass_rate": round(pass_rate, 2),
            "dq_rate": round(dq_rate, 2), "fail_rate": round(fail_rate, 2),
            "avg_fidelity": round(avg_fidelity, 1), "avg_alignment": round(avg_alignment, 1),
            "scored_count": len(scored_runs), "dq_count": len(disqualified), "fail_count": len(failed),
        }
    })

# ═══════════════════════════════════════════════════════════════════
# FINAL LEADERBOARD
# ═══════════════════════════════════════════════════════════════════
all_runs.sort(key=lambda x: -x["summary"]["avg_score"])

print("\n\n" + "=" * 120)
print("V4 FINAL LEADERBOARD")
print("=" * 120)
print(f"{'#':<3} {'Model':<26} {'Avg':<7} {'Best':<7} {'Var':<6} {'Pass':<6} {'DQ':<6} {'Fidelity':<9} {'Align':<6} {'Band'}")
print("-" * 105)
for i, m in enumerate(all_runs, 1):
    s = m["summary"]
    if s["avg_score"] > 0:
        band = "Production" if s["avg_score"] >= 90 else "Strong" if s["avg_score"] >= 80 else "Usable" if s["avg_score"] >= 70 else "Weak"
        print(f"{i:<3} {m['model']:<26} {s['avg_score']:<7.1f} {s['best_score']:<7.1f} {s['variance']:<6.2f} {s['pass_rate']:<6.0%} {s['dq_rate']:<6.0%} {s['avg_fidelity']:<9.1f} {s['avg_alignment']:<6.1f} {band}")
    else:
        print(f"{i:<3} {m['model']:<26} DISQ/F AIL{'':<7} —      —      {s['pass_rate']:<6.0%} {s['dq_rate']:<6.0%} —         —      —")
print("=" * 120)

# Save
with open("/home/skystarved/dev_workspaces/v4_benchmark_results.json", "w") as f:
    # Keep it serializable
    serializable = []
    for m in all_runs:
        sm = {k: v for k, v in m.items()}
        sm["runs"] = [{k2: str(v2) if not isinstance(v2, (int, float, str, bool, list, dict, type(None))) else v2 for k2, v2 in r.items()} for r in m["runs"]]
        serializable.append(sm)
    json.dump(serializable, f, indent=2, default=str)

print(f"\nSaved to v4_benchmark_results.json — {sum(m['summary']['scored_count'] for m in all_runs)} scored, {sum(m['summary']['dq_count'] for m in all_runs)} disqualified, {sum(m['summary']['fail_count'] for m in all_runs)} failed")
