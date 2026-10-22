#!/usr/bin/env python3
"""
V3 RESUME WRITING BENCHMARK — LLM-Generated Tailored Resumes
=============================================================
Tests 8 models on writing an ATS-optimized, tailored resume from a job description
and verified candidate profile. Scores against reference output and JD keywords.
"""
import json, os, time, requests, sys, re
from collections import Counter

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY: print("ERROR: OPENROUTER_API_KEY_1 not set"); sys.exit(1)

# ── Job Description (Boeing BDS GenAI Data Scientist) ──
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

# ── Candidate Profile (verified from SKILL.md) ──
CANDIDATE_PROFILE = """
VERIFIED CANDIDATE FACTS — DO NOT INVENT ANYTHING OUTSIDE THIS PROFILE:

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

# ── Reference resume (from generate_boeing_v3.py output structure) ──
REFERENCE_RESUME = """
Jeff Calderon
916.712.8396  *  jeff.d.calderon@gmail.com  *  Marysville, WA  *  U.S. Citizen
linkedin.com/in/jeffdcalderon  *  github.com/aggressor-FZX  *  cogitometric.ai
Data Scientist  |  GenAI  |  ML Engineering  |  PyTorch  |  LLMs  |  GPU Distributed Training
Deep Learning: PyTorch, TensorFlow, PyTorch DDP, GPU clusters (H100/A100)  *  GenAI: LLM fine-tuning, RAG (LangChain, Pinecone), prompt engineering, embeddings  *  Data & Infra: SQL, Spark, Airflow, Docker, Kubernetes, AWS (Lambda, Glue, S3, IAM)

PROFESSIONAL EXPERIENCE
GenAI / ML Engineering Contributor (Boeing Defense Capstone), Washington State University  (08/2025 - 05/2026)
- Trained (PyTorch DDP, TensorFlow) and fine-tuned generative models on 263,000+ image datasets across NVIDIA H100/A100 GPU clusters for Boeing Defense aerial drone video analysis; maintained fully reproducible pipeline with deterministic evaluation and checkpointing in Docker containers on a Kubernetes-orchestrated cluster.
- Applied NLP embedding techniques and prompt engineering to semantic feature analysis of aerial imagery metadata, improving downstream classification accuracy.
- Collaborated with cross-functional team of engineers and researchers; documented MLOps standards (version-controlled code, fixed-seed evaluation, per-tick logging) adopted across the project for audit-ready results.

Data Scientist / GenAI Platform Architect, Cogito Metric LLC (C2C)  |  cogitometric.ai  (2024 - Present)
- Architected production GenAI platform: ingests unstructured text, generates semantic embeddings, routes through multi-agent LLM workflows (LangChain, Pinecone) - live system with real users delivering structured intelligence at scale.
- Deployed REST APIs for LLM inference on AWS Lambda; fine-tuned prompt strategies and retrieval-evaluation protocols to optimize model performance and ensure consistent output quality across production deployments.

Operations Manager, National Oceanic and Atmospheric Administration (NOAA)  (12/2019 - 05/2023)
- Developed Python-based statistical models and decision-support tools synthesizing high-dimensional sensor data from 13 research vessels; reduced manual reporting overhead by 40% across fleet operations.
- Architected a Government Official Travel analytics portal end-to-end, achieving 85% user adoption in the first month and cutting processing time by 60% through transparent real-time status tracking.

Marine Data Analyst, NOAA Commissioned Officer Corps  (12/2016 - 05/2019)
- Designed anomaly detection algorithms on geospatial datasets identifying navigation hazards for official U.S. nautical chart updates; iterated against ground-truth validation.
- Managed 10+ TB of multi-sensor oceanographic data with reproducible, governed pipelines and version-controlled workflows; delivered executive briefings translating complex sensor analysis into actionable operational recommendations.

Research Physicist, U.S. Naval Research Laboratory  (01/2014 - 06/2016)
- Developed Monte Carlo simulation pipelines (Python, C++) for probabilistic risk quantification and radiological threat detection; validated predictive models against empirical benchmarks - results secured $500K in federal R&D funding.
- Delivered results in a classified national security environment with rigorous governance, documentation, and validation standards.

PROJECTS
Enterprise AI Solutions Delivery Framework (2025): Designed and implemented an AI acceleration framework combining SQL, Python, and JSON APIs to deliver modular analytics solutions for enterprise clients.
Prompt Engineering & RAG for Document Intelligence (2024): Developed standardized prompt templates and tuning workflows for LLMs (GPT-4, Claude), integrated with Pinecone to achieve sub-second retrieval on large corpora.

EDUCATION & CERTIFICATIONS
B.S. Data Analytics, Washington State University (05/2026)     A.A.S. Computer Science, Everett CC (04/2024, 4.0 GPA)     B.S. Physics, University of Maryland (12/2015)
Certs: Network Security+ (CompTIA)  *  Cybersecurity Analyst (ECC)  *  Data Analytics (WSU)  *  Publication: J. Instrumentation (2016) - CERN/LHC"""

# ── Models ──
MODELS = [
    ("mistralai/codestral-2508",         "Mistral Codestral 2508",     0.200, 0.900),
    ("xiaomi/mimo-v2-flash",             "MiMo-V2-Flash",             0.100, 0.300),
    ("deepseek/deepseek-v4-flash",       "DeepSeek V4 Flash",         0.090, 0.300),
    ("google/gemma-4-31b-it",            "Gemma 4 31B",              0.120, 0.360),
    ("bytedance-seed/seed-2.0-lite",     "Seed 2.0 Lite",            0.250, 2.000),
    ("google/gemini-2.5-flash-lite",     "Gemini 2.5 Flash Lite",    0.100, 0.400),
    ("deepseek/deepseek-chat-v3-0324",   "DeepSeek Chat V3 0324",    0.200, 0.770),
    ("anthropic/claude-3.5-haiku",       "Claude 3.5 Haiku",         0.250, 1.250),
]

# ── System Prompt ──
SYSTEM = """You are an expert ATS-optimized resume writer for data science and ML roles.

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

# ── JD Keywords for ATS scoring ──
JD_KEYWORDS_REQUIRED = [
    "python", "sql", "spark", "airflow", "pytorch", "tensorflow",
    "deep learning", "genai", "generative ai", "llm", "mlops",
    "data science", "machine learning", "gpu", "docker", "kubernetes",
    "fine-tuning", "prompt engineering", "embeddings", "api",
    "bias", "fairness", "model evaluation", "distributed training",
    "pipeline", "deploy", "data engineering",
]

JD_KEYWORDS_PREFERRED = [
    "langchain", "pinecone", "rag", "aws", "nlp", "hugging face",
    "git", "linux", "security", "classified", "c2c", "cogito metric",
    "monte carlo", "anomaly detection", "hadoop", "etl",
    "peer-reviewed", "publication", "presentation",
]

JD_KEYWORDS_SOFT = [
    "cross-functional", "collaborat", "executive", "stakeholder",
    "briefing", "presentation", "documentation", "best practice",
    "regulated", "governance", "evaluation",
]

# ── Ground truth facts (for hallucination detection) ──
VERIFIED_FACTS = {
    "employers": ["cogito metric", "noaa", "naval research laboratory", "nrl",
                  "washington state", "university of maryland", "cern",
                  "everett community college", "wsu", "boeing", "umb"],
    "degrees": ["b.s. data analytics", "b.s. physics", "a.a.s. computer science",
                "bachelor", "associate"],
    "certs": ["network security+", "security+", "comptia", "cybersecurity analyst",
              "ecc", "data analytics"],
    "tools": ["python", "pytorch", "tensorflow", "langchain", "pinecone", "docker",
              "kubernetes", "aws", "sql", "spark", "hadoop", "git", "linux",
              "pandas", "numpy", "scikit-learn", "hugging face", "airflow",
              "lambda", "s3", "iam", "glue", "langgraph", "boto3", "c++",
              "jupyter", "power bi", "matlab"],
    "forbidden": ["master", "phd", "ph.d", "doctorate", "m.s.", "m.a.", "mba",
                   "google", "microsoft", "amazon", "facebook", "meta", "apple",
                   "netflix", "openai", "anthropic", "top secret", "ts/sci",
                   "secret clearance"],
}

def call_model(model_id, text, tries=2):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    msgs = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"JOB DESCRIPTION:\n\n{JD_TEXT}\n\nCANDIDATE PROFILE:\n\n{CANDIDATE_PROFILE}\n\nWrite the tailored resume now."}
    ]
    p = {"model": model_id, "messages": msgs, "temperature": 0.3, "max_tokens": 4096}
    resp = None; start = time.time()
    for attempt in range(tries):
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=h, json=p, timeout=300)
            elapsed = time.time() - start
            if resp.status_code == 400:
                p["response_format"] = {"type": "text"}
                start = time.time()
                resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=h, json=p, timeout=300)
                elapsed = time.time() - start
            resp.raise_for_status()
            d = resp.json()
            u = d.get("usage", {})
            content = d["choices"][0]["message"].get("content") or ""
            if not content or content.strip() == "":
                content = d["choices"][0]["message"].get("reasoning") or ""
            return {"ok": True, "content": content, "latency": round(elapsed, 2),
                    "tokens": u.get("total_tokens", 0), "prompt": u.get("prompt_tokens", 0),
                    "completion": u.get("completion_tokens", 0)}
        except Exception as e:
            if attempt < tries - 1: time.sleep(2); continue
            elapsed = time.time() - start; err = str(e)[:200]
            if resp is not None:
                try: err += f" | {resp.text[:300]}"
                except: pass
            return {"ok": False, "content": None, "latency": round(elapsed, 2), "tokens": 0,
                    "prompt": 0, "completion": 0, "error": err[:300]}

# ── SCORING ──
def score_resume(resume_text):
    """Score the generated resume against JD keywords and fact fidelity."""
    lower = resume_text.lower()
    details = {}
    score = 0

    # ── 1. ATS KEYWORD COVERAGE (30 pts) ──
    required_hits = sum(1 for kw in JD_KEYWORDS_REQUIRED if kw in lower)
    preferred_hits = sum(1 for kw in JD_KEYWORDS_PREFERRED if kw in lower)
    soft_hits = sum(1 for kw in JD_KEYWORDS_SOFT if kw in lower)

    req_score = (required_hits / len(JD_KEYWORDS_REQUIRED)) * 15
    pref_score = (preferred_hits / len(JD_KEYWORDS_PREFERRED)) * 10
    soft_score = (soft_hits / len(JD_KEYWORDS_SOFT)) * 5

    details["ats_required"] = f"{required_hits}/{len(JD_KEYWORDS_REQUIRED)}"
    details["ats_preferred"] = f"{preferred_hits}/{len(JD_KEYWORDS_PREFERRED)}"
    details["ats_soft"] = f"{soft_hits}/{len(JD_KEYWORDS_SOFT)}"
    details["ats_score"] = round(req_score + pref_score + soft_score, 1)
    score += details["ats_score"]

    # ── 2. FACT FIDELITY (25 pts) ──
    # Check for forbidden credentials
    forbidden_count = 0
    for word in VERIFIED_FACTS["forbidden"]:
        if word in lower:
            forbidden_count += 1

    # Count verified employer mentions
    employer_hits = sum(1 for emp in VERIFIED_FACTS["employers"] if emp in lower)
    degree_hits = sum(1 for deg in VERIFIED_FACTS["degrees"] if deg in lower)
    cert_hits = sum(1 for cert in VERIFIED_FACTS["certs"] if cert in lower)

    fidelity = 25
    fidelity -= forbidden_count * 3  # Heavy penalty for invented credentials
    fidelity = max(0, min(25, fidelity))

    details["forbidden_hits"] = forbidden_count
    details["forbidden_words"] = [w for w in VERIFIED_FACTS["forbidden"] if w in lower]
    details["employer_coverage"] = f"{employer_hits}/{len(VERIFIED_FACTS['employers'])}"
    details["fidelity_score"] = fidelity
    score += fidelity

    # ── 3. SECTION STRUCTURE (15 pts) ──
    sections = {
        "header/contact": any(x in lower for x in ["jeff calderon", "916", "jeff.d.calderon"]),
        "summary/profile": any(x in lower[:500] for x in ["data scientist", "ml engineer", "years of experience"]),
        "professional experience": "professional experience" in lower or "work experience" in lower,
        "projects": "project" in lower,
        "education": "education" in lower,
        "certifications": "certif" in lower or "security+" in lower,
    }
    section_score = sum(2.5 for v in sections.values() if v)
    details["sections"] = {k: v for k, v in sections.items()}
    details["section_score"] = section_score
    score += section_score

    # ── 4. BULLET QUALITY (15 pts) ──
    lines = resume_text.split("\n")
    bullet_lines = [l.strip() for l in lines if l.strip().startswith(("-", "•", "*"))]
    action_verbs = ["developed", "built", "designed", "deployed", "implemented", "architected",
                    "led", "managed", "created", "applied", "trained", "fine-tuned",
                    "reduced", "improved", "optimized", "automated", "secured", "delivered",
                    "collaborated", "spearheaded", "integrated", "engineered", "analyzed"]

    verb_count = sum(1 for b in bullet_lines for v in action_verbs if b.lower().strip("-•* ").startswith(v))
    # Count bullets with numbers (quantified metrics)
    metric_bullets = sum(1 for b in bullet_lines if re.search(r'\d+', b))
    bullet_count = len(bullet_lines)

    bullet_score = 0
    if bullet_count >= 10: bullet_score += 5
    elif bullet_count >= 6: bullet_score += 3
    elif bullet_count >= 3: bullet_score += 1

    verb_ratio = verb_count / max(bullet_count, 1)
    if verb_ratio >= 0.8: bullet_score += 5
    elif verb_ratio >= 0.5: bullet_score += 3
    elif verb_ratio > 0: bullet_score += 1

    metric_ratio = metric_bullets / max(bullet_count, 1)
    if metric_ratio >= 0.5: bullet_score += 5
    elif metric_ratio >= 0.3: bullet_score += 3
    elif metric_ratio > 0: bullet_score += 1

    details["bullet_count"] = bullet_count
    details["action_verb_count"] = verb_count
    details["metric_bullets"] = metric_bullets
    details["bullet_score"] = bullet_score
    score += bullet_score

    # ── 5. JD ALIGNMENT / REFERENCE SIMILARITY (15 pts) ──
    # Check how well the resume maps to the specific JD responsibilities
    jd_phrases = [
        "develop and deploy", "pipeline", "fine-tun", "prompt engineering",
        "embedding", "prototype", "bias", "fairness", "mlops",
        "model scaling", "monitoring", "share knowledge", "best practice",
        "regulated industry", "gpu compute", "distributed training",
        "container", "defense", "security", "u.s. person", "hybrid",
    ]
    alignment_hits = sum(1 for p in jd_phrases if p in lower)
    alignment_score = (alignment_hits / len(jd_phrases)) * 15
    details["jd_alignment"] = f"{alignment_hits}/{len(jd_phrases)}"
    details["alignment_score"] = round(alignment_score, 1)
    score += alignment_score

    # ── Word count penalty ──
    word_count = len(resume_text.split())
    details["word_count"] = word_count
    if word_count < 250: score -= 5   # Too short
    elif word_count > 1200: score -= 3  # Too long (should be ~1 page)

    details["total_score"] = round(max(0, min(100, score)), 1)
    return details["total_score"], details

# ── MAIN ──
print("=" * 100)
print("V3 RESUME WRITING BENCHMARK — 8 Models tailoring resumes for Boeing GenAI role")
print("=" * 100)
print(f"JD: Boeing Defense — Data Scientist (GenAI), Seattle/Arlington")
print(f"Candidate: Jeff Calderon (verified profile from SKILL.md)")
print(f"Scoring: ATS keywords(30) + Fact fidelity(25) + Structure(15) + Bullets(15) + JD alignment(15)")
print("=" * 100)

all_results = []

for model_id, label, price_in, price_out in MODELS:
    blended = (price_in * 3 + price_out) / 4
    print(f"\n{'─' * 100}")
    print(f"  {label} ({model_id}) — ${blended:.3f}/M blended")
    print(f"{'─' * 100}")

    sys.stdout.write(f"  Generating resume... "); sys.stdout.flush()
    r = call_model(model_id, JD_TEXT)

    entry = {"model": label, "model_id": model_id, "ok": r["ok"],
             "latency": r["latency"], "tokens": r["tokens"],
             "price_in": price_in, "price_out": price_out,
             "price_blended": round(blended, 4)}

    if r["ok"] and r["content"]:
        resume = r["content"]
        # Strip markdown fences if present
        resume = re.sub(r'^```[\w]*\n?', '', resume)
        resume = re.sub(r'\n?```$', '', resume)
        resume = resume.strip()

        sc, det = score_resume(resume)
        entry["score"] = sc; entry["details"] = det
        entry["resume_length"] = len(resume)
        entry["resume_words"] = det["word_count"]
        cost = (r["tokens"] / 1_000_000) * blended
        entry["cost"] = round(cost, 6)

        print(f"Score: {sc}/100 | {r['tokens']}tk | {r['latency']}s | "
              f"ATS:{det['ats_score']:.1f} Fid:{det['fidelity_score']} "
              f"Sec:{det['section_score']:.1f} Bul:{det['bullet_score']} "
              f"Ali:{det['alignment_score']:.1f} | Words:{det['word_count']}")

        # Print first 200 chars of resume for quick check
        preview = resume[:150].replace('\n', ' | ')
        print(f"  Preview: {preview}...")
    else:
        entry["score"] = 0; entry["details"] = {"error": r.get("error", "unknown")}
        entry["cost"] = 0
        print(f"FAIL ({r.get('error', 'unknown')[:80]})")

    all_results.append(entry)

# Sort by score
all_results.sort(key=lambda x: -x.get("score", 0))

# Save
with open("/home/skystarved/dev_workspaces/v3_resume_writing_results.json", "w") as f:
    # Convert to serializable format
    serializable = []
    for r in all_results:
        sr = {k: v for k, v in r.items() if k != "details"}
        sr["details"] = {k: str(v) if not isinstance(v, (int, float, str, bool, list, dict)) else v
                         for k, v in r.get("details", {}).items()}
        serializable.append(sr)
    json.dump(serializable, f, indent=2)

print("\n\n" + "=" * 100)
print("V3 FINAL RESULTS — Resume Writing Benchmark")
print("=" * 100)
print(f"{'#':<3} {'Model':<26} {'Score':<7} {'ATS(30)':<8} {'Fid(25)':<8} {'Sec(15)':<8} {'Bul(15)':<8} {'Ali(15)':<8} {'Time':<8} {'Cost':<8}")
print("-" * 110)
for i, r in enumerate(all_results, 1):
    d = r.get("details", {})
    if isinstance(d, dict) and "ats_score" in d:
        print(f"{i:<3} {r['model']:<26} {r['score']:<7.1f} "
              f"{d['ats_score']:<8.1f} {d['fidelity_score']:<8} "
              f"{d['section_score']:<8.1f} {d['bullet_score']:<8} "
              f"{d['alignment_score']:<8.1f} "
              f"{r['latency']:.0f}s{'':<3} ${r.get('cost', 0):.5f}")
    else:
        print(f"{i:<3} {r['model']:<26} FAIL{'':<7} {'—':<8} {'—':<8} {'—':<8} {'—':<8} {'—':<8} {r['latency']:.0f}s")
print("=" * 100)

# Best by category
print("\nBEST BY CATEGORY:")
for cat, key in [("ATS Keywords", "ats_score"), ("Fact Fidelity", "fidelity_score"),
                  ("Section Structure", "section_score"), ("Bullet Quality", "bullet_score"),
                  ("JD Alignment", "alignment_score")]:
    best = max((r for r in all_results if isinstance(r.get("details", {}).get(key), (int, float))),
               key=lambda x: x["details"][key], default=None)
    if best:
        print(f"  {cat}: {best['model']} ({best['details'][key]})")
print("=" * 100)
