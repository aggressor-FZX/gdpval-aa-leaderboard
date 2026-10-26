#!/usr/bin/env python3
"""
Test 3 Qwen models with SAME scoring as resume_parsing_benchmark.py
Uses the original ANSWER_KEY and score_against_answer from the benchmark.
"""
import json, os, time, requests, sys

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
    ("qwen/qwen3.6-flash",       "Qwen 3.6 Flash"),
    ("qwen/qwen3.6-27b",         "Qwen 3.6 27B"),
    ("qwen/qwen3.5-flash-02-23", "Qwen 3.5 Flash"),
]

# OpenRouter pricing (verified)
PRICES = {
    "qwen/qwen3.6-flash":       {"in": 0.188, "out": 1.125, "blended": 0.422},
    "qwen/qwen3.6-27b":         {"in": 0.289, "out": 2.400, "blended": 0.817},
    "qwen/qwen3.5-flash-02-23": {"in": 0.065, "out": 0.260, "blended": 0.114},
}

# ── GROUND TRUTH ANSWER KEY (same as resume_parsing_benchmark.py) ──

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
        "total_bullets_expected": 10,
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

# ── HELPERS ──

def call_model(model_id, text, tries=2):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Parse:\n\n{text}"}]
    p = {"model": model_id, "messages": msgs, "temperature": 0.0, "max_tokens": 4096,
         "response_format": {"type": "json_object"}}
    resp = None; start = time.time()
    for attempt in range(tries):
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
            # Qwen reasoning models may put content in reasoning field
            if not content or content.strip() == "":
                content = d["choices"][0]["message"].get("reasoning") or ""
            return {"ok": True, "content": content, "latency": round(elapsed, 2),
                    "tokens": u.get("total_tokens", 0), "prompt": u.get("prompt_tokens", 0),
                    "completion": u.get("completion_tokens", 0)}
        except Exception as e:
            if attempt < tries - 1:
                time.sleep(2)
                continue
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
    if "<answer>" in content:
        s = content.find("<answer>") + 8; e = content.find("</answer>")
        if e > s:
            try: return json.loads(content[s:e].strip())
            except: pass
    return None

# ── SAME SCORING AS BENCHMARK ──

def score_against_answer(parsed, ak):
    """Identical to resume_parsing_benchmark.py scoring function."""
    score = 0; details = {}
    
    # 1. Schema completeness (20 pts)
    expected_fields = {"title", "title_confidence", "skills", "skill_count", "experience",
                       "education", "projects", "certifications", "domain", "overall_confidence"}
    if isinstance(parsed, dict):
        fields_present = sum(1 for f in expected_fields if f in parsed)
        details["schema_fields"] = fields_present
        score += min(20, fields_present * 2)
    else:
        details["schema_fields"] = 0
    
    # 2. Job title match (10 pts)
    title = parsed.get("title", "").lower() if isinstance(parsed, dict) else ""
    expected_title = ak["title"].lower()
    if expected_title in title:
        details["title_match"] = True; score += 10
    else:
        details["title_match"] = False; details["extracted_title"] = title[:60]
    
    # 3. Experience count (15 pts)
    exp = parsed.get("experience", []) if isinstance(parsed, dict) else []
    exp_count = len(exp) if isinstance(exp, list) else 0
    details["exp_count"] = exp_count; details["exp_expected"] = ak["experience_count"]
    ratio = min(exp_count, ak["experience_count"]) / max(exp_count, ak["experience_count"], 1)
    score += round(15 * ratio)
    if isinstance(exp, list):
        companies = [j.get("company", "").lower() for j in exp if isinstance(j, dict)]
        expected = [c.lower() for c in ak["expected_companies"]]
        matches = sum(1 for ec in expected if any(ec.lower() in comp for comp in companies))
        details["company_matches"] = f"{matches}/{len(expected)}"
        score += min(5, matches)
    
    # 4. Education count (10 pts)
    edu = parsed.get("education", []) if isinstance(parsed, dict) else []
    edu_count = len(edu) if isinstance(edu, list) else 0
    details["edu_count"] = edu_count; details["edu_expected"] = ak["education_count"]
    edu_ratio = min(edu_count, ak["education_count"]) / max(edu_count, ak["education_count"], 1)
    score += round(10 * edu_ratio)
    
    # 5. Certifications (10 pts)
    certs = parsed.get("certifications", []) if isinstance(parsed, dict) else []
    cert_count = len(certs) if isinstance(certs, list) else 0
    details["cert_count"] = cert_count; details["cert_expected"] = ak["certifications_count"]
    cert_ratio = min(cert_count, ak["certifications_count"]) / max(cert_count, ak["certifications_count"], 1)
    score += round(10 * cert_ratio)
    
    # 6. Projects (10 pts)
    proj = parsed.get("projects", []) if isinstance(parsed, dict) else []
    proj_count = len(proj) if isinstance(proj, list) else 0
    details["proj_count"] = proj_count; details["proj_expected"] = ak["projects_count"]
    if ak["projects_count"] == 0:
        score += 10
    else:
        proj_ratio = min(proj_count, ak["projects_count"]) / max(proj_count, ak["projects_count"], 1)
        score += round(10 * proj_ratio)
    
    # 7. Skills match (10 pts)
    extracted_skills = [s.lower() for s in parsed.get("skills", [])] if isinstance(parsed, dict) else []
    expected_skills = [s.lower() for s in ak["expected_skills"]]
    matches = sum(1 for es in expected_skills if any(es in exs for exs in extracted_skills))
    details["skill_matches"] = f"{matches}/{len(expected_skills)}"
    details["skill_count"] = len(extracted_skills)
    skill_ratio = matches / max(len(expected_skills), 1)
    score += round(10 * min(skill_ratio, 1.0))
    
    # 8. Bullet count (5 pts)
    if isinstance(exp, list):
        bullets_total = sum(len(j.get("bullets", [])) for j in exp if isinstance(j, dict))
        details["bullet_count"] = bullets_total; details["bullet_expected"] = ak["total_bullets_expected"]
        bullet_ratio = min(bullets_total, ak["total_bullets_expected"]) / max(bullets_total, ak["total_bullets_expected"], 1)
        score += round(5 * bullet_ratio)
    else:
        details["bullet_count"] = 0; details["bullet_expected"] = ak["total_bullets_expected"]
    
    # 9. Domain match (5 pts)
    domain = (parsed.get("domain", "") or "").lower() if isinstance(parsed, dict) else ""
    if ak["domain"].lower() in domain or domain in ["technology", "tech", "data"]:
        details["domain_match"] = True; score += 5
    else:
        details["domain_match"] = False; details["domain_extracted"] = domain[:40]
    
    details["total_score"] = min(score, 100)
    return min(score, 100), details

# ── MAIN ──
print("=" * 100)
print("TESTING 3 QWEN MODELS (using SAME scoring as original benchmark)")
print("=" * 100)
print(f"Models: {', '.join(m[1] for m in MODELS)}")
print(f"Scoring: Identical to resume_parsing_benchmark.py")
print("=" * 100)

all_summaries = []

for model_id, label in MODELS:
    print(f"\n{'─' * 100}")
    print(f"  {label} ({model_id})")
    price = PRICES[model_id]
    print(f"  Price: in=${price['in']:.3f}/M out=${price['out']:.3f}/M blended=${price['blended']:.3f}/M")
    print(f"{'─' * 100}")
    
    model_totals = {"score": 0, "tokens": 0, "time": 0, "skills": 0, "successes": 0}
    
    for rfile in RESUMES:
        with open(os.path.join(BASE, rfile)) as f:
            text = f.read()
        rname = rfile.replace(".pdf.txt", "")
        
        sys.stdout.write(f"\n  ▶ {rname}... "); sys.stdout.flush()
        r = call_model(model_id, text)
        
        entry = {"model": label, "resume": rname, "ok": r["ok"], "latency": r["latency"],
                 "tokens": r["tokens"]}
        
        if r["ok"] and r["content"]:
            parsed = parse_json(r["content"])
            if parsed:
                sc, det = score_against_answer(parsed, ANSWER_KEY[rname])
                model_totals["score"] += sc
                model_totals["tokens"] += r["tokens"]
                model_totals["time"] += r["latency"]
                model_totals["skills"] += det.get("skill_count", 0)
                model_totals["successes"] += 1
                print(f"Score: {sc}/100 | {r['tokens']}tk | {r['latency']}s | Skills: {det.get('skill_matches','?')}")
            else:
                model_totals["tokens"] += r["tokens"]; model_totals["time"] += r["latency"]
                print(f"JSON PARSE FAIL | {r['tokens']}tk | {r['latency']}s")
        else:
            model_totals["tokens"] += r["tokens"]; model_totals["time"] += r["latency"]
            print(f"FAIL ({r.get('error', 'unknown')[:50]}) | {r['tokens']}tk | {r['latency']}s")
    
    n = model_totals["successes"]
    avg_score = model_totals["score"] / max(n, 1)
    avg_skills = model_totals["skills"] / max(n, 1)
    
    print(f"\n  ══ {label} SUMMARY ══")
    print(f"  Successes: {n}/5 | Avg Score: {avg_score:.1f} | Tokens: {model_totals['tokens']} | Time: {model_totals['time']:.1f}s | Avg Skills: {avg_skills:.1f}")
    
    all_summaries.append({
        "model": label,
        "model_id": model_id,
        "avg_score": round(avg_score, 1),
        "total_tokens": model_totals["tokens"],
        "total_time": round(model_totals["time"], 1),
        "successes": n,
        "avg_skills": round(avg_skills, 1),
        "price_in": price["in"],
        "price_out": price["out"],
        "price_blended": price["blended"],
        "reliability": f"{n}/5",
        "speed_per_resume": round(model_totals["time"] / 5, 1) if n > 0 else None,
    })

# Save results
with open("/home/skystarved/dev_workspaces/qwen_models_results.json", "w") as f:
    json.dump(all_summaries, f, indent=2)

print("\n\nResults saved to qwen_models_results.json")
print("\n" + "=" * 100)
print("FINAL RESULTS")
print("=" * 100)
print(f"{'Model':<25} | {'Score':<7} | {'Tokens':<7} | {'Time':<8} | {'Skills':<7} | {'Success':<7} | {'Price/M':<10}")
print("-" * 100)
for s in all_summaries:
    print(f"{s['model']:<25} | {s['avg_score']:<7.1f} | {s['total_tokens']:<7} | {s['total_time']:<8.1f}s | {s['avg_skills']:<7.1f} | {s['successes']}/5     | ${s['price_blended']:<9.3f}")
print("=" * 100)
