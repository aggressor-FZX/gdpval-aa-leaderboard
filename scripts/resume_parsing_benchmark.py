#!/usr/bin/env python3
"""
Resume Parsing Benchmark — 5 Models × 5 Resumes with Answer Key
================================================================
Tests: MiMo-V2-Flash, gpt-oss-120b, DeepSeek V4 Flash,
       Tencent Hy3 Preview, Mistral Small 4
Against ground truth answer key extracted from the actual resumes.
"""

import json, os, time, requests, sys
from collections import defaultdict

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY: print("ERROR: OPENROUTER_API_KEY_1 not set"); sys.exit(1)
BASE = "/mnt/c/Users/jeffd/latexRoot/extracted_text"

RESUMES = [
    "Calderon_DataMAR25.pdf.txt",
    "Calderon_CyberResearch.pdf.txt",
    "Calderon_Boeing.pdf.txt",
    "Calderon_Amazon.pdf.txt",
    "CalderonGOVResume.pdf.txt",
]

MODELS = [
    ("xiaomi/mimo-v2-flash",          "MiMo-V2-Flash",           True),
    ("openai/gpt-oss-120b",           "gpt-oss-120b",            True),
    ("deepseek/deepseek-v4-flash",    "DeepSeek V4 Flash",       True),
    ("tencent/hy3-preview",           "Tencent Hy3 Preview",     True),
    ("mistralai/mistral-small-2603",  "Mistral Small 4",         True),
]

# ── GROUND TRUTH ANSWER KEY ───────────────────────────────────────────────────
# Derived from manual inspection of all 5 resume PDFs.
# Each key = resume shorthand name.

ANSWER_KEY = {
    "Calderon_DataMAR25": {
        "title": "Operations Manager",
        "experience_count": 4,
        "expected_companies": ["NOAA", "NOAA", "Naval Research Laboratory", "University of Maryland"],
        "education_count": 3,
        "expected_degrees": ["B.S. Data Analytics", "A.A.S. Computer Science", "B.S. Physics"],
        "certifications_count": 3,
        "projects_count": 4,
        "expected_skills": [
            "Python", "NoSQL", "MongoDB", "Azure Data Studio", "Git", "Docker", "Linux",
            "RESTful", "JSON", "XML", "AWS Lambda", "TensorFlow", "Keras", "PyTorch",
            "Pandas", "NumPy", "Matplotlib", "Seaborn", "Scikit-learn", "Jupyter",
            "C++", "SQL", "ETL", "data modeling", "visualization", "data mining",
            "APIs", "Smartsheet",
        ],
        "total_bullets_expected": 10,  # approximate
        "domain": "Technology",
    },
    "Calderon_CyberResearch": {
        "title": "Operations Manager",
        "experience_count": 6,
        "expected_companies": ["NOAA", "NOAA", "Naval Research Laboratory", "University of Maryland", "United States Air Force", "United States Air Force"],
        "education_count": 3,
        "expected_degrees": ["B.S. Physics", "B.S. Social Science", "A.A.S. Computer Science"],
        "certifications_count": 3,
        "projects_count": 0,
        "expected_skills": [
            "Python", "Pandas", "NumPy", "Matplotlib", "Seaborn", "Scikit-learn", "APIs",
            "Cloud Services", "Project Management", "ETL", "Network Security",
            "Leadership", "data pipelines",
        ],
        "total_bullets_expected": 20,
        "domain": "Technology",
    },
    "Calderon_Boeing": {
        "title": "Data Analyst",
        "experience_count": 5,
        "expected_companies": ["WADEPS", "Everett Community College", "NOAA", "NOAA", "Naval Research Laboratory"],
        "education_count": 3,
        "expected_degrees": ["B.S. Data Analytics", "A.A.S. Computer Science", "B.S. Physics"],
        "certifications_count": 3,
        "projects_count": 3,
        "expected_skills": [
            "Python", "LLMs", "Playwright", "AWS", "LangChain", "Selenium", "Pinecone",
            "YOLO", "SAM", "cloud", "project management",
        ],
        "total_bullets_expected": 14,
        "domain": "Technology",
    },
    "Calderon_Amazon": {
        "title": "Marine Data Analyst",
        "experience_count": 3,
        "expected_companies": ["NOAA", "Naval Research Laboratory", "University of Maryland"],
        "education_count": 4,
        "expected_degrees": ["B.S. Data Analytics", "A.A.S. Computer Science", "B.S. Physics", "B.S. Social Science"],
        "certifications_count": 3,
        "projects_count": 0,
        "expected_skills": [
            "Python", "NoSQL", "MongoDB", "Azure Data Studio", "Git", "Docker", "Linux",
            "RESTful", "JSON", "XML", "AWS Lambda", "C++", "SQL", "Bash", "Ruby",
            "JavaScript", "ETL", "Data modeling", "visualization", "analysis", "data mining",
            "ArcGIS", "CARIS", "data schema design",
        ],
        "total_bullets_expected": 10,
        "domain": "Technology",
    },
    "CalderonGOVResume": {
        "title": "Commissioned Officer",
        "experience_count": 4,
        "expected_companies": ["NOAA", "Naval Research Laboratory", "University of Maryland", "United States Air Force"],
        "education_count": 4,
        "expected_degrees": ["A.A.S. Computer Science", "B.S. Physics", "B.S. Social Science", "A.A.S. Industrial Management"],
        "certifications_count": 2,
        "projects_count": 0,
        "expected_skills": [
            "Python", "APIs", "Cloud Services", "Project Management", "policy review",
            "compliance", "contracting", "budgeting", "Network Security", "Leadership",
            "database administration", "server administration", "coding standards",
            "Linux", "C++", "MATLAB", "Pandas",
        ],
        "total_bullets_expected": 14,
        "domain": "Technology",
    },
}

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────

SYSTEM = """You are a resume parser. Output ONLY valid JSON with EXACTLY these fields:

{
  "title": "Most recent job title",
  "title_confidence": 0.0-1.0,
  "skills": ["skill1", "skill2"],
  "skill_count": <int>,
  "experience": [{"title": "", "company": "", "start_date": "MM/YYYY", "end_date": "MM/YYYY or Present", "bullets": ["bullet"], "skills": ["skill"]}],
  "education": [{"degree": "", "institution": "", "start_date": "MM/YYYY", "end_date": "MM/YYYY", "gpa": null, "honors": []}],
  "projects": [{"name": "", "description": "", "technologies": [], "url": null}],
  "certifications": [{"name": "", "issuer": "", "date_earned": "MM/YYYY"}],
  "domain": "",
  "overall_confidence": 0.0-1.0
}

No markdown. No comments. No explanations."""

# ── HELPERS ────────────────────────────────────────────────────────────────────

def call_model(model_id, text):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Parse:\n\n{text}"}]
    p = {"model": model_id, "messages": msgs, "temperature": 0.0, "max_tokens": 4096,
         "response_format": {"type": "json_object"}}
    resp = None; start = time.time()
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=h, json=p, timeout=300)
        elapsed = time.time() - start
        if resp.status_code == 400:
            del p["response_format"]
            start = time.time()
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=h, json=p, timeout=300)
            elapsed = time.time() - start
        resp.raise_for_status()
        d = resp.json()
        u = d.get("usage", {})
        content = d["choices"][0]["message"].get("content") or ""
        return {"ok": True, "content": content, "latency": round(elapsed, 2),
                "tokens": u.get("total_tokens", 0), "prompt": u.get("prompt_tokens", 0),
                "completion": u.get("completion_tokens", 0)}
    except Exception as e:
        elapsed = time.time() - start
        err = str(e)[:200]
        if resp is not None:
            try: err += f" | {resp.text[:300]}"
            except: pass
        return {"ok": False, "content": None, "latency": round(elapsed, 2), "tokens": 0,
                "prompt": 0, "completion": 0, "error": err[:300]}

def parse_json(content):
    if not content: return None
    clean = "\n".join(l for l in content.split("\n") if not l.strip().startswith("//"))
    try: return json.loads(clean)
    except: pass
    s, e = clean.find("{"), clean.rfind("}")
    if s >= 0 and e > s:
        try: return json.loads(clean[s:e+1])
        except: pass
    # <answer> tags (for Qwen-style models)
    if "<answer>" in content:
        s = content.find("<answer>") + 8; e = content.find("</answer>")
        if e > s:
            try: return json.loads(content[s:e].strip())
            except: pass
    return None

def score_against_answer(parsed, answer_key, resume_name):
    """
    Score from 0-100 by comparing extracted data against ground truth.
    """
    score = 0; details = {}
    ak = answer_key

    # --- 1. Schema completeness (20 pts) ---
    expected_fields = {"title", "title_confidence", "skills", "skill_count", "experience",
                       "education", "projects", "certifications", "domain", "overall_confidence"}
    if isinstance(parsed, dict):
        fields_present = sum(1 for f in expected_fields if f in parsed)
        details["schema_fields"] = fields_present
        score += min(20, fields_present * 2)
    else:
        details["schema_fields"] = 0
    
    # --- 2. Job title match (10 pts) ---
    title = parsed.get("title", "").lower() if isinstance(parsed, dict) else ""
    expected_title = ak["title"].lower()
    if expected_title in title:
        details["title_match"] = True
        score += 10
    else:
        details["title_match"] = False
        details["extracted_title"] = title[:60]
    
    # --- 3. Experience count (15 pts) ---
    exp = parsed.get("experience", []) if isinstance(parsed, dict) else []
    exp_count = len(exp) if isinstance(exp, list) else 0
    details["exp_count"] = exp_count
    details["exp_expected"] = ak["experience_count"]
    # Score proportional to match
    ratio = min(exp_count, ak["experience_count"]) / max(exp_count, ak["experience_count"], 1)
    score += round(15 * ratio)
    
    # Check how many expected companies appear in extracted experience
    if isinstance(exp, list):
        companies = [j.get("company", "").lower() for j in exp if isinstance(j, dict)]
        expected = [c.lower() for c in ak["expected_companies"]]
        matches = sum(1 for ec in expected if any(ec.lower() in comp for comp in companies))
        details["company_matches"] = f"{matches}/{len(expected)}"
        score += min(5, matches)
    
    # --- 4. Education count (10 pts) ---
    edu = parsed.get("education", []) if isinstance(parsed, dict) else []
    edu_count = len(edu) if isinstance(edu, list) else 0
    details["edu_count"] = edu_count
    details["edu_expected"] = ak["education_count"]
    edu_ratio = min(edu_count, ak["education_count"]) / max(edu_count, ak["education_count"], 1)
    score += round(10 * edu_ratio)
    
    # --- 5. Certifications (10 pts) ---
    certs = parsed.get("certifications", []) if isinstance(parsed, dict) else []
    cert_count = len(certs) if isinstance(certs, list) else 0
    details["cert_count"] = cert_count
    details["cert_expected"] = ak["certifications_count"]
    cert_ratio = min(cert_count, ak["certifications_count"]) / max(cert_count, ak["certifications_count"], 1)
    score += round(10 * cert_ratio)
    
    # --- 6. Projects (10 pts) ---
    proj = parsed.get("projects", []) if isinstance(parsed, dict) else []
    proj_count = len(proj) if isinstance(proj, list) else 0
    details["proj_count"] = proj_count
    details["proj_expected"] = ak["projects_count"]
    if ak["projects_count"] == 0:
        score += 10  # No projects expected, full credit
    else:
        proj_ratio = min(proj_count, ak["projects_count"]) / max(proj_count, ak["projects_count"], 1)
        score += round(10 * proj_ratio)
    
    # --- 7. Skills match (10 pts) ---
    extracted_skills = [s.lower() for s in parsed.get("skills", [])] if isinstance(parsed, dict) else []
    expected_skills = [s.lower() for s in ak["expected_skills"]]
    matches = sum(1 for es in expected_skills if any(es in exs for exs in extracted_skills))
    details["skill_matches"] = f"{matches}/{len(expected_skills)}"
    details["skill_count"] = len(extracted_skills)
    skill_ratio = matches / max(len(expected_skills), 1)
    score += round(10 * min(skill_ratio, 1.0))
    
    # --- 8. Bullet count (5 pts) ---
    if isinstance(exp, list):
        bullets_total = sum(len(j.get("bullets", [])) for j in exp if isinstance(j, dict))
        details["bullet_count"] = bullets_total
        details["bullet_expected"] = ak["total_bullets_expected"]
        bullet_ratio = min(bullets_total, ak["total_bullets_expected"]) / max(bullets_total, ak["total_bullets_expected"], 1)
        score += round(5 * bullet_ratio)
    else:
        details["bullet_count"] = 0
        details["bullet_expected"] = ak["total_bullets_expected"]
    
    # --- 9. Domain match (5 pts) ---
    domain = (parsed.get("domain", "") or "").lower() if isinstance(parsed, dict) else ""
    if ak["domain"].lower() in domain or domain in ["technology", "tech", "data"]:
        details["domain_match"] = True
        score += 5
    else:
        details["domain_match"] = False
        details["domain_extracted"] = domain[:40]
    
    return min(score, 100), details

# ── MAIN ───────────────────────────────────────────────────────────────────────

print("=" * 100)
print("RESUME PARSING BENCHMARK — 5 Models × 5 Resumes with Answer Key")
print("=" * 100)

all_results = []

for model_id, label, is_paid in MODELS:
    print(f"\n{'─' * 100}")
    print(f"  {label} ({model_id})")
    print(f"{'─' * 100}")
    
    model_entries = []
    
    for rfile in RESUMES:
        rname = rfile.replace(".pdf.txt", "")
        with open(os.path.join(BASE, rfile)) as f:
            text = f.read()
        
        r = call_model(model_id, text)
        
        entry = {"model": label, "resume": rname, "ok": r["ok"],
                 "latency": r["latency"], "tokens": r["tokens"],
                 "prompt": r["prompt"], "completion": r["completion"]}
        
        if r["ok"] and r["content"]:
            parsed = parse_json(r["content"])
            if parsed and isinstance(parsed, dict):
                score, details = score_against_answer(parsed, ANSWER_KEY[rname], rname)
                entry["score"] = score
                entry["details"] = details
                entry["keys"] = list(parsed.keys())
                model_entries.append(entry)
                
                print(f"\n  ▶ {rname}")
                print(f"    Score: {score:.0f}/100 | Tokens: {r['tokens']} (P:{r['prompt']} C:{r['completion']}) | Time: {r['latency']}s")
                print(f"    Title: {details.get('title_match','?')} | "
                      f"Jobs: {details['exp_count']}/{details['exp_expected']} | "
                      f"Edu: {details['edu_count']}/{details['edu_expected']} | "
                      f"Certs: {details['cert_count']}/{details['cert_expected']} | "
                      f"Proj: {details['proj_count']}/{details['proj_expected']}")
                print(f"    Skills: {details['skill_matches']} ({details['skill_count']} extracted) | "
                      f"Bullets: {details['bullet_count']}/{details['bullet_expected']} | "
                      f"Members: {details.get('company_matches','?')}")
            else:
                entry["score"] = 0
                entry["details"] = {"error": "not valid JSON"}
                model_entries.append(entry)
                print(f"\n  ▶ {rname} ❌ Invalid JSON: {(r['content'] or '')[:80]}")
        else:
            entry["score"] = 0
            entry["details"] = {"error": r.get("error", "unknown")[:80]}
            model_entries.append(entry)
            print(f"\n  ▶ {rname} ❌ Error: {r.get('error', 'unknown')[:100]}")
    
    all_results.append({"model": label, "entries": model_entries})

# ── SCOREBOARD ─────────────────────────────────────────────────────────────────

print("\n\n" + "=" * 100)
print("FINAL SCOREBOARD (Average over 5 resumes, scored against ground truth)")
print("=" * 100)
print(f"{'Model':30s} | {'Avg Score':10s} | {'Total Tokens':12s} | {'Total Time':11s} | {'Avg Jobs':8s} | {'Avg Edu':7s} | {'Avg Certs':8s} | {'Avg Skills':9s}")
print("-" * 110)

for m in all_results:
    scores = [e["score"] for e in m["entries"] if e["score"] > 0]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    total_tokens = sum(e["tokens"] for e in m["entries"])
    total_time = round(sum(e["latency"] for e in m["entries"]), 1)
    valid = [e for e in m["entries"] if e["ok"]]
    avg_jobs = round(sum(e.get("details",{}).get("exp_count",0) for e in valid) / max(len(valid),1), 1) if valid else 0
    avg_edu = round(sum(e.get("details",{}).get("edu_count",0) for e in valid) / max(len(valid),1), 1) if valid else 0
    avg_certs = round(sum(e.get("details",{}).get("cert_count",0) for e in valid) / max(len(valid),1), 1) if valid else 0
    avg_skills = round(sum(e.get("details",{}).get("skill_count",0) for e in valid) / max(len(valid),1), 1) if valid else 0
    
    print(f"{m['model']:30s} | {avg_score:6.1f}%    | {total_tokens:8d}     | {total_time:6.1f}s   | {avg_jobs:6.1f}  | {avg_edu:5.1f} | {avg_certs:6.1f} | {avg_skills:7.1f}")

# ── WINNERS ────────────────────────────────────────────────────────────────────

print("\n\n" + "=" * 100)
print("CATEGORY WINNERS")
print("=" * 100)

categories = {
    "Highest Avg Score": lambda e: sum(e["score"] for e in m["entries"]) / max(len([x for x in m["entries"] if x["score"] > 0]), 1),
    "Most Skills Extracted": lambda e: sum(e.get("details",{}).get("skill_count",0) for e in valid) / max(len(valid),1),
    "Most Experience Found": lambda e: sum(e.get("details",{}).get("exp_count",0) for e in valid) / max(len(valid),1),
    "Most Education Found": lambda e: sum(e.get("details",{}).get("edu_count",0) for e in valid) / max(len(valid),1),
    "Most Certs Found": lambda e: sum(e.get("details",{}).get("cert_count",0) for e in valid) / max(len(valid),1),
    "Fastest Total Time": lambda e: -sum(e["latency"] for e in m["entries"]),
    "Most Token Efficient": lambda e: -sum(e["tokens"] for e in m["entries"]),
}

for cat_name, metric_fn in categories.items():
    best_model = None; best_val = None
    for m in all_results:
        valid = [e for e in m["entries"] if e["ok"]]
        if valid:
            val = metric_fn(m)
            if best_val is None or val > best_val:
                best_val = val; best_model = m["model"]
    if best_model:
        if "Fastest" in cat_name or "Efficient" in cat_name:
            print(f"  {cat_name:30s} → {best_model} ({abs(round(best_val,1))}s)")
        else:
            print(f"  {cat_name:30s} → {best_model} ({round(best_val,1)})")

# ── SAVE ───────────────────────────────────────────────────────────────────────
out = json.dumps(all_results, indent=2, default=str)
with open("resume_parsing_benchmark.json", "w") as f:
    f.write(out)
print(f"\nResults saved to resume_parsing_benchmark.json")
