#!/usr/bin/env python3
"""V3 Resume Writing — Batch 3: 7 more models. Same test, same scoring."""
import json, os, time, requests, sys, re

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY: print("ERROR: OPENROUTER_API_KEY_1 not set"); sys.exit(1)

# ── Same JD, candidate profile, prompt, and scoring as V3 batch 1 & 2 ──
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
VERIFIED_FACTS = {
    "forbidden": ["master", "phd", "ph.d", "doctorate", "m.s.", "m.a.", "mba",
                   "google", "microsoft", "amazon", "facebook", "meta", "apple",
                   "netflix", "openai", "anthropic", "top secret", "ts/sci",
                   "secret clearance"],
}

def call_model(model_id, tries=2):
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
                    "tokens": u.get("total_tokens", 0)}
        except Exception as e:
            if attempt < tries - 1: time.sleep(2); continue
            elapsed = time.time() - start; err = str(e)[:200]
            if resp is not None:
                try: err += f" | {resp.text[:300]}"
                except: pass
            return {"ok": False, "content": None, "latency": round(elapsed, 2), "tokens": 0, "error": err[:300]}

def score_resume(resume_text):
    lower = resume_text.lower(); details = {}; score = 0
    required_hits = sum(1 for kw in JD_KEYWORDS_REQUIRED if kw in lower)
    preferred_hits = sum(1 for kw in JD_KEYWORDS_PREFERRED if kw in lower)
    soft_hits = sum(1 for kw in JD_KEYWORDS_SOFT if kw in lower)
    details["ats"] = round((required_hits/len(JD_KEYWORDS_REQUIRED))*15 + (preferred_hits/len(JD_KEYWORDS_PREFERRED))*10 + (soft_hits/len(JD_KEYWORDS_SOFT))*5, 1)
    score += details["ats"]
    forbidden_count = sum(1 for w in VERIFIED_FACTS["forbidden"] if w in lower)
    details["fidelity"] = max(0, min(25, 25 - forbidden_count * 3)); score += details["fidelity"]
    details["forbidden"] = forbidden_count
    sections = {"header": any(x in lower for x in ["jeff calderon", "916", "jeff.d.calderon"]),
                "summary": any(x in lower[:500] for x in ["data scientist", "ml engineer", "years"]),
                "experience": "professional experience" in lower or "work experience" in lower,
                "projects": "project" in lower, "education": "education" in lower,
                "certifications": "certif" in lower or "security+" in lower}
    details["structure"] = sum(2.5 for v in sections.values() if v); score += details["structure"]
    lines = resume_text.split("\n")
    bullet_lines = [l.strip() for l in lines if l.strip().startswith(("-", "•", "*"))]
    action_verbs = ["developed","built","designed","deployed","implemented","architected","led","managed","created","applied","trained","fine-tuned","reduced","improved","optimized","automated","secured","delivered","collaborated","spearheaded","integrated","engineered","analyzed"]
    verb_count = sum(1 for b in bullet_lines for v in action_verbs if b.lower().strip("-•* ").startswith(v))
    metric_bullets = sum(1 for b in bullet_lines if re.search(r'\d+', b))
    bc = len(bullet_lines)
    bullet_score = (5 if bc>=10 else 3 if bc>=6 else 1 if bc>=3 else 0)
    vr = verb_count/max(bc,1); bullet_score += 5 if vr>=0.8 else 3 if vr>=0.5 else 1 if vr>0 else 0
    mr = metric_bullets/max(bc,1); bullet_score += 5 if mr>=0.5 else 3 if mr>=0.3 else 1 if mr>0 else 0
    details["bullets"] = bullet_score; details["bullet_count"] = bc; details["metric_bullets"] = metric_bullets; score += bullet_score
    jd_phrases = ["develop and deploy","pipeline","fine-tun","prompt engineering","embedding","prototype","bias","fairness","mlops","model scaling","monitoring","share knowledge","best practice","regulated industry","gpu compute","distributed training","container","defense","security","u.s. person","hybrid"]
    details["alignment"] = round(sum(1 for p in jd_phrases if p in lower) / len(jd_phrases) * 15, 1); score += details["alignment"]
    wc = len(resume_text.split()); details["words"] = wc
    if wc < 250: score -= 5
    elif wc > 1200: score -= 3
    details["score"] = round(max(0, min(100, score)), 1)
    return details["score"], details

MODELS = [
    ("z-ai/glm-5.1",                "GLM 5.1",             0.98, 3.08),
    ("deepseek/deepseek-v4-pro",     "DeepSeek V4 Pro",     0.43, 0.87),
    ("xiaomi/mimo-v2.5-pro",         "MiMo V2.5 Pro",       0.43, 0.87),
    ("minimax/minimax-m3",           "MiniMax M3",          0.30, 1.20),
    ("kwaipilot/kat-coder-pro-v2",   "Kat Coder Pro V2",    0.30, 1.20),
    ("moonshotai/kimi-k2.6:free",    "Kimi K2.6 (free)",    0.00, 0.00),
    ("anthropic/claude-sonnet-4.6",  "Claude Sonnet 4.6",   3.00, 15.00),
]

print("=" * 100)
print("V3 BATCH 3 — 7 More Models (same test, same scoring)")
print("=" * 100)
all_results = []

for model_id, label, price_in, price_out in MODELS:
    blended = (price_in * 3 + price_out) / 4
    print(f"\n{'─' * 100}")
    print(f"  {label} ({model_id}) — ${blended:.3f}/M blended")
    sys.stdout.write(f"  Generating... "); sys.stdout.flush()
    r = call_model(model_id)
    entry = {"model": label, "model_id": model_id, "ok": r["ok"],
             "latency": r["latency"], "tokens": r["tokens"],
             "price_blended": round(blended, 4)}
    if r["ok"] and r["content"]:
        resume = re.sub(r'^```[\w]*\n?', '', r["content"])
        resume = re.sub(r'\n?```$', '', resume)
        resume = resume.strip()
        sc, det = score_resume(resume)
        entry.update({"score": sc, "ats": det["ats"], "fidelity": det["fidelity"],
                       "structure": det["structure"], "bullets": det["bullets"],
                       "alignment": det["alignment"], "words": det["words"],
                       "forbidden": det["forbidden"], "bullet_count": det["bullet_count"],
                       "metric_bullets": det["metric_bullets"]})
        entry["cost"] = round((r["tokens"] / 1_000_000) * blended, 6)
        print(f"Score: {sc}/100 | {r['tokens']}tk | {r['latency']}s | ATS:{det['ats']} Bul:{det['bullets']} Ali:{det['alignment']} | Words:{det['words']}")
    else:
        entry["score"] = 0; entry["cost"] = 0; entry["forbidden"] = 0
        print(f"FAIL ({r.get('error','unknown')[:80]})")
    all_results.append(entry)

all_results.sort(key=lambda x: -x.get("score", 0))

# Merge with existing
combined_path = "/home/skystarved/dev_workspaces/v3_resume_writing_results.json"
with open(combined_path, 'r') as f: existing = json.load(f)
existing = [e for e in existing if e.get("model") not in [m["model"] for m in all_results]]
existing.extend(all_results)
existing.sort(key=lambda x: -x.get("score", 0))
with open(combined_path, 'w') as f: json.dump(existing, f, indent=2)

print("\n\n" + "=" * 100)
print("V3 COMBINED — All 18 Models")
print("=" * 100)
print(f"{'#':<3} {'Model':<26} {'Score':<7} {'ATS':<6} {'Fid':<5} {'Bul':<5} {'Ali':<6} {'Time':<7} {'Cost':<8}")
print("-" * 95)
for i, r in enumerate(existing, 1):
    sc = r.get("score", 0)
    if sc > 0:
        print(f"{i:<3} {r['model']:<26} {sc:<7.1f} {r.get('ats',0):<6.1f} {r.get('fidelity',0):<5.0f} {r.get('bullets',0):<5} {r.get('alignment',0):<6.1f} {r.get('latency',0):.0f}s{'':<3} ${r.get('cost',0):.5f}")
    else:
        print(f"{i:<3} {r['model']:<26} FAIL")
print("=" * 100)
