#!/usr/bin/env python3
"""Qwen strategy test — Qwen3 Coder + 3.5 Flash + 3.7 Max, 3 runs each, V4 scoring, 10s delays."""
import json, os, time, requests, sys, re, numpy as np

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY: print("ERROR: KEY"); sys.exit(1)

# Prompts (same as V4)
SYS = """You are an expert ATS-optimized resume writer for data science and ML roles.
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

JD = """Data Scientist (Data Science) - Boeing Defense, Space & Security
Seeking a Mid-Level Data Scientist - GenAI. Role involves developing and optimizing advanced AI, ML, and GenAI models within BDS. Work with senior data scientists and cross-functional teams on AI-driven applications.
Required: Bachelor's in CS, ML, Math, CE, SE, AI, Physics or related. 3+ years data science or ML. 3+ years Python programming and familiarity with data engineering (Spark, Airflow, SQL).
Preferred: Master's or PhD in related field. Experience fine-tuning open-source models and integrating APIs. Deep learning frameworks (PyTorch, TensorFlow). AI ethics and governance for generative models. Data engineering tools (SQL, Spark, Airflow)."""

PROFILE = """VERIFIED CANDIDATE FACTS — DO NOT INVENT ANYTHING OUTSIDE THIS PROFILE:
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

USER_MSG = f"JOB DESCRIPTION:\n\n{JD}\n\nCANDIDATE PROFILE:\n\n{PROFILE}\n\nWrite the tailored resume now."

# Gates + scoring (identical to V4)
VERIFIED_EMPLOYERS = ["noaa","naval research laboratory","nrl","washington state","university of maryland","cern","everett community college","wsu","cogito metric"]
VERIFIED_DEGREES = ["b.s. data analytics","b.s. physics","a.a.s. computer science","bachelor"]
VERIFIED_CERTS = ["network security+","security+","comptia","cybersecurity analyst","ecc","data analytics"]
FORBIDDEN_DEGREES = ["master","phd","ph.d","doctorate","m.s.","m.a.","mba","m.eng","m.sc"]
FORBIDDEN_EMPLOYERS = ["google","microsoft","amazon","facebook","meta","apple","netflix","openai","anthropic"]
FORBIDDEN_CLEARANCE = ["top secret","ts/sci","secret clearance","ts sci","sci eligible"]

def check_gates(text):
    lower = text.lower(); critical = []; non_critical = []
    fd = [d for d in FORBIDDEN_DEGREES if d in lower]
    fe = [e for e in FORBIDDEN_EMPLOYERS if e in lower]
    fc = [c for c in FORBIDDEN_CLEARANCE if c in lower]
    if fd or fe or fc: critical.append(("G1",f"Invented: deg={fd} emp={fe} clr={fc}"))
    if fd: critical.append(("G2",f"Unverified degrees: {fd}"))
    if not ("jeff calderon" in lower and ("cogito metric" in lower or "c2c" in lower or "u.s. citizen" in lower)): critical.append(("G3","Identity"))
    if "```" in text or any(x in lower[:200] for x in ["here is","i've written","below is","certainly","sure!"]): critical.append(("G4","Non-resume output"))
    if not any(x in lower for x in ["jeff calderon","916.712","jeff.d.calderon"]): non_critical.append(("G5","Missing header"))
    if not ("professional experience" in lower or "experience" in lower[:500]): non_critical.append(("G5","Missing experience"))
    if "project" not in lower: non_critical.append(("G5","Missing projects"))
    if "education" not in lower: non_critical.append(("G5","Missing education"))
    wc = len(text.split())
    if wc < 320 or wc > 700: non_critical.append(("G6",f"Words {wc}"))
    fp = re.findall(r'\b(I|my|me|we)\s+(built|developed|created|designed|led|managed|implemented|deployed|worked)', lower)
    if fp: non_critical.append(("G7",f"First-person: {fp}"))
    if not ("c2c" in lower or "cogito metric" in lower): non_critical.append(("G8","No C2C"))
    if not ("boeing" in lower or "capstone" in lower or "defense" in lower or "h100" in lower): non_critical.append(("G9","No Boeing"))
    has_table = "|" in text and text.count("|") > 5
    if has_table: non_critical.append(("G10","Table markers"))
    gp = 10 - len(critical) - len(non_critical)
    return {"disqualified": len(critical) > 0, "gates_passed": gp, "critical": len(critical), "non_critical": len(non_critical)}

GSI_MAP = {"h100":["distributed training","gpu infrastructure","multi-gpu","gpu compute","accelerated computing"],"a100":["distributed training","gpu infrastructure","multi-gpu","gpu compute"],"docker":["containerization","container orchestration","containerized","container"],"kubernetes":["container orchestration","containerized deployment","cluster management","container"],"langchain":["retrieval-augmented generation","rag","llm orchestration","agent framework"],"pinecone":["vector database","vector search","embedding-based search"],"monte carlo":["simulation","probabilistic modeling","risk assessment"],"classified":["regulated environment","governance","compliance","security-cleared"],"security+":["cybersecurity","secure development","infosec"]}
GSI_FORBIDDEN = ["airflow","spark","kafka","terraform","mlflow","weights & biases","rlhf","fairness audit","ci/cd pipeline","jenkins","github actions"]

def score_gsi(text):
    lower = text.lower(); inferred = []; unsupported = []
    for ev, skills in GSI_MAP.items():
        if ev in lower:
            for s in skills:
                if s in lower and s not in inferred: inferred.append(s)
    for f in GSI_FORBIDDEN:
        if f in lower and f not in PROFILE.lower(): unsupported.append(f)
    actual = [s for s in inferred if s not in PROFILE.lower()]
    total = len(actual) + len(unsupported)
    if total == 0: return 0
    prec = len(actual) / total
    jd_kw = ["distributed training","gpu","evaluation","pipeline","container","governance","regulated","fine-tun","embedding","deploy","mlops"]
    useful = sum(1 for s in actual if any(kw in s for kw in jd_kw))
    use = useful / max(total, 1)
    raw = (prec * 0.6 + use * 0.4) * 10
    cap = 10 if len(actual) >= 3 else (8 if len(actual) >= 1 else 5)
    return round(min(raw, cap))

def weighted_score(text):
    lower = text.lower(); details = {}
    fc = sum(1 for w in FORBIDDEN_DEGREES + FORBIDDEN_EMPLOYERS + FORBIDDEN_CLEARANCE if w in lower)
    eh = sum(1 for e in VERIFIED_EMPLOYERS if e in lower)
    dh = sum(1 for d in VERIFIED_DEGREES if d in lower)
    ch = sum(1 for c in VERIFIED_CERTS if c in lower)
    if fc >= 2: fr = 0
    elif fc == 1: fr = 3
    elif eh >= 4 and dh >= 2 and ch >= 3: fr = 10
    elif eh >= 3: fr = 8
    else: fr = 5
    details["fid"] = round(fr/10*35, 1)
    themes = {"genai":["genai","generative ai","llm","large language model","fine-tun","prompt engineering"],"python":["python","sql","data engineer","etl","pipeline"],"eval":["evaluation","bias","fairness","model performance"],"gpu":["distributed training","gpu","h100","a100","multi-gpu"],"dk8s":["docker","kubernetes","container"],"gov":["governance","regulated","compliance","ethics"],"mlops":["mlops","collaborat","cross-functional","engineering team"],"deploy":["deploy","production","scale","monitoring"]}
    ht = sum(1 for kws in themes.values() if any(kw in lower for kw in kws))
    if ht >= 8: ar = 10
    elif ht >= 6: ar = 8
    elif ht >= 4: ar = 5
    elif ht >= 2: ar = 3
    else: ar = 0
    details["align"] = round(ar/10*20, 1)
    bullets = [l.strip() for l in text.split("\n") if l.strip().startswith(("-","\u2022","*"))]
    av = ["developed","built","designed","deployed","implemented","architected","led","managed","created","applied","trained","fine-tuned","reduced","improved","optimized","automated","secured","delivered","collaborated","spearheaded","integrated","engineered","analyzed","processed","orchestrated","directed","established"]
    vc = sum(1 for b in bullets for v in av if b.lower().strip("-\u2022* ").startswith(v))
    vr = vc / max(len(bullets), 1)
    if vr >= 0.8: br = 10
    elif vr >= 0.6: br = 8
    elif vr >= 0.4: br = 5
    elif vr >= 0.2: br = 3
    else: br = 0
    details["bul"] = round(br/10*10, 1)
    vmc = sum(["263" in lower, "500k" in lower or ("500" in lower and "funding" in lower), "40%" in lower or "40 %" in lower, "30" in lower and ("hour" in lower or "week" in lower), "10" in lower and "tb" in lower])
    if vmc >= 4: mr = 10
    elif vmc >= 3: mr = 8
    elif vmc >= 2: mr = 5
    elif vmc >= 1: mr = 3
    else: mr = 0
    details["met"] = round(mr/10*10, 1)
    eo = (5 if ("boeing" in lower[:500] or "capstone" in lower[:300]) else 0) + (3 if ("cogito metric" in lower or "nlp platform" in lower) else 0) + (2 if ("noaa" in lower and ("naval research" in lower or "nrl" in lower)) else (1 if ("noaa" in lower or "naval research" in lower or "nrl" in lower) else 0))
    if eo >= 8: tr = 10
    elif eo >= 6: tr = 8
    elif eo >= 4: tr = 5
    elif eo >= 2: tr = 3
    else: tr = 0
    details["tgt"] = round(tr/10*10, 1)
    sk = ["python","pytorch","tensorflow","sql","docker","kubernetes","aws","langchain","pinecone","hadoop"]
    sh = sum(1 for k in sk if k in lower)
    if sh >= 9: sr = 10
    elif sh >= 7: sr = 8
    elif sh >= 5: sr = 5
    elif sh >= 3: sr = 3
    else: sr = 0
    details["sk"] = round(sr/10*5, 1)
    if "professional experience" in lower and "education" in lower and "project" in lower: atsr = 10
    elif "experience" in lower and "education" in lower: atsr = 5
    else: atsr = 3
    details["ats"] = round(atsr/10*5, 1)
    wc = len(text.split())
    if 380 <= wc <= 650: bvr = 10
    elif 320 <= wc <= 700: bvr = 8
    elif 250 <= wc <= 800: bvr = 5
    else: bvr = 3
    details["brv"] = round(bvr/10*5, 1)
    gsi = score_gsi(text)
    details["gsi"] = round(gsi/10*10, 1)
    total = sum(details.values())
    return round(min(total, 100), 1), details

# MODELS — real pricing from OpenRouter API
MODELS = [
    ("qwen/qwen3-coder",         "Qwen3 Coder 480B",    0.22, 1.80),
    ("qwen/qwen3.5-flash-02-23", "Qwen 3.5 Flash",      0.07, 0.26),
    ("qwen/qwen3.7-max",         "Qwen 3.7 Max",        1.25, 3.75),
]

RUNS = 3
headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

print("=" * 90)
print(f"QWEN STRATEGY TEST — {len(MODELS)} models x {RUNS} runs | V4 scoring | 10s delays")
print("=" * 90)

all_results = []

for mid, label, p_in, p_out in MODELS:
    blended = (p_in * 3 + p_out) / 4
    print(f"\n{'='*90}")
    print(f"  {label} ({mid}) — ${p_in:.2f}/${p_out:.2f}/M  blended=${blended:.2f}/M")
    print(f"{'='*90}")

    runs = []
    for rn in range(1, RUNS + 1):
        sys.stdout.write(f"  Run {rn}/{RUNS}... "); sys.stdout.flush()
        start = time.time()
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
                headers=headers, timeout=300, json={
                    "model": mid,
                    "messages": [{"role":"system","content":SYS},{"role":"user","content":USER_MSG}],
                    "temperature": 0.0, "max_tokens": 4096,
                })
            elapsed = time.time() - start
            resp.raise_for_status()
            d = resp.json()
            raw = d["choices"][0]["message"].get("content","") or ""
            resume = re.sub(r'^```[\w]*\n?','',raw); resume = re.sub(r'\n?```$','',resume); resume = resume.strip()
            tokens = d.get("usage",{}).get("total_tokens",0)
            gates = check_gates(resume)
            if gates["disqualified"]:
                print(f"DQ | {gates['critical']} critical | {elapsed:.1f}s")
                runs.append({"run":rn,"disqualified":True,"gates":gates,"latency":elapsed,"tokens":tokens})
                continue
            sc, det = weighted_score(resume)
            cost = (tokens / 1_000_000) * blended
            band = "Production-ready" if sc >= 90 else ("Strong" if sc >= 80 else ("Usable" if sc >= 70 else "Weak"))
            print(f"{sc:.1f}/100 [{band}] | gates:{gates['gates_passed']}/10 | {tokens}tk | {elapsed:.1f}s | GSI:{det['gsi']:.0f}")
            runs.append({"run":rn,"disqualified":False,"score":sc,"gates":gates,"details":det,"latency":round(elapsed,2),"tokens":tokens,"cost":round(cost,6)})
        except Exception as e:
            elapsed = time.time() - start
            print(f"FAIL: {str(e)[:80]}")
            runs.append({"run":rn,"ok":False,"error":str(e)[:200],"latency":round(elapsed,2)})
        
        if rn < RUNS:
            sys.stdout.write("    (sleeping 10s)... "); sys.stdout.flush()
            time.sleep(10)
            print("done")

    scored = [r for r in runs if not r.get("disqualified") and r.get("score",0) > 0]
    dq = [r for r in runs if r.get("disqualified")]
    failed = [r for r in runs if not r.get("ok",True)]

    if scored:
        scores = [r["score"] for r in scored]
        avg = sum(scores) / len(scores)
        var = round(np.var(scores), 2) if len(scores) > 1 else 0
        best = max(scores)
    else:
        avg = 0; var = 0; best = 0

    print(f"  SUMMARY: avg={avg:.1f} best={best:.1f} var={var:.2f} | scored={len(scored)} dq={len(dq)} fail={len(failed)}")
    all_results.append({"model":label,"model_id":mid,"price_blended":round(blended,2),"runs":runs,"summary":{"avg_score":round(avg,1),"best_score":best,"variance":var,"scored":len(scored),"dq":len(dq),"fail":len(failed)}})

# Leaderboard
all_results.sort(key=lambda x: -x["summary"]["avg_score"])
print(f"\n{'='*90}")
print("LEADERBOARD — Qwen Strategy Test")
print(f"{'='*90}")
print(f"{'Model':<25} {'Avg':>6} {'Best':>6} {'Var':>6} {'Scored':>7} {'DQ':>4} {'Fail':>4} {'Cost/M':>8}")
print("-" * 70)
for m in all_results:
    s = m["summary"]
    print(f"{m['model']:<25} {s['avg_score']:>6.1f} {s['best_score']:>6.1f} {s['variance']:>6.2f} {s['scored']:>7} {s['dq']:>4} {s['fail']:>4} ${m['price_blended']:<7.2f}")

# Compare with V4 top
print(f"\n{'='*90}")
print("VS V4 BENCHMARK TOP MODELS")
print("=" * 90)
for name, score, var, cost in [("GLM 5.1",100.0,0.00,1.50),("Qwen 3 235B",97.3,14.22,0.10),("Grok 4.3",97.3,3.56,1.56),("Kat Coder Pro V2",95.0,10.67,0.53),("MiMo V2.5 Pro",93.2,2.72,0.54)]:
    print(f"  {name:<25} {score:>6.1f}  var={var:<6.2f}  ${cost:.2f}/M")
for m in all_results:
    s = m["summary"]
    print(f"  {m['model']:<25} {s['avg_score']:>6.1f}  var={s['variance']:<6.2f}  ${m['price_blended']:.2f}/M")

with open("qwen_strategy_test_results.json","w") as f:
    json.dump({"test":"Qwen Strategy","time":time.strftime("%Y-%m-%d %H:%M:%S"),"models":all_results}, f, indent=2, default=str)
print(f"\nSaved to qwen_strategy_test_results.json")