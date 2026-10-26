#!/usr/bin/env python3
"""
Test 3 new models: qwen3.6-35b-a3b, microsoft/phi-4, mistralai/codestral-2508
Run against 5 resumes and score against the answer key.
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
    ("qwen/qwen3.6-35b-a3b",          "Qwen 3.6 35B A3B"),
    ("microsoft/phi-4",                "Microsoft Phi-4"),
    ("mistralai/codestral-2508",       "Mistral Codestral 2508"),
]

# ANSWER KEY (same as benchmark script)
ANSWER_KEY = {
    "Calderon_DataMAR25": {
        "title": "Operations Manager", "experience_count": 4,
        "expected_companies": ["NOAA", "NOAA", "Naval Research Laboratory", "University of Maryland"],
        "education_count": 3, "certifications_count": 3, "projects_count": 4,
        "domain": "Technology",
    },
    "Calderon_CyberResearch": {
        "title": "Operations Manager", "experience_count": 6,
        "expected_companies": ["NOAA", "NOAA", "Naval Research Laboratory", "University of Maryland", "United States Air Force", "United States Air Force"],
        "education_count": 3, "certifications_count": 3, "projects_count": 0,
        "domain": "Technology",
    },
    "Calderon_Boeing": {
        "title": "Data Analyst", "experience_count": 5,
        "expected_companies": ["WADEPS", "Everett Community College", "NOAA", "NOAA", "Naval Research Laboratory"],
        "education_count": 3, "certifications_count": 3, "projects_count": 3,
        "domain": "Technology",
    },
    "Calderon_Amazon": {
        "title": "Marine Data Analyst", "experience_count": 3,
        "expected_companies": ["NOAA", "Naval Research Laboratory", "University of Maryland"],
        "education_count": 4, "certifications_count": 3, "projects_count": 0,
        "domain": "Technology",
    },
    "CalderonGOVResume": {
        "title": "Commissioned Officer", "experience_count": 4,
        "expected_companies": ["NOAA", "Naval Research Laboratory", "University of Maryland", "United States Air Force"],
        "education_count": 4, "certifications_count": 2, "projects_count": 0,
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
    if "<answer>" in content:
        s = content.find("<answer>") + 8; e = content.find("</answer>")
        if e > s:
            try: return json.loads(content[s:e].strip())
            except: pass
    return None

def score_against_answer(parsed, ak):
    score = 0; details = {}
    expected_fields = {"title", "title_confidence", "skills", "skill_count", "experience",
                       "education", "projects", "certifications", "domain", "overall_confidence"}
    if isinstance(parsed, dict):
        fields_present = sum(1 for f in expected_fields if f in parsed)
        details["schema_fields"] = fields_present
        score += min(20, fields_present * 2)
    else:
        details["schema_fields"] = 0
    
    title = parsed.get("title", "").lower() if isinstance(parsed, dict) else ""
    expected_title = ak["title"].lower()
    if expected_title in title:
        details["title_match"] = True; score += 10
    else:
        details["title_match"] = False; details["extracted_title"] = title[:60]
    
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
    
    edu = parsed.get("education", []) if isinstance(parsed, dict) else []
    edu_count = len(edu) if isinstance(edu, list) else 0
    details["edu_count"] = edu_count; details["edu_expected"] = ak["education_count"]
    edu_ratio = min(edu_count, ak["education_count"]) / max(edu_count, ak["education_count"], 1)
    score += round(10 * edu_ratio)
    
    certs = parsed.get("certifications", []) if isinstance(parsed, dict) else []
    cert_count = len(certs) if isinstance(certs, list) else 0
    details["cert_count"] = cert_count; details["cert_expected"] = ak["certifications_count"]
    cert_ratio = min(cert_count, ak["certifications_count"]) / max(cert_count, ak["certifications_count"], 1)
    score += round(10 * cert_ratio)
    
    proj = parsed.get("projects", []) if isinstance(parsed, dict) else []
    proj_count = len(proj) if isinstance(proj, list) else 0
    details["proj_count"] = proj_count; details["proj_expected"] = ak["projects_count"]
    if ak["projects_count"] > 0:
        proj_ratio = min(proj_count, ak["projects_count"]) / max(proj_count, ak["projects_count"], 1)
        score += round(10 * proj_ratio)
    else:
        score += 10 if proj_count == 0 else 5
    
    skills = parsed.get("skills", []) if isinstance(parsed, dict) else []
    if isinstance(skills, list) and len(skills) > 0:
        score += min(15, len(skills))
        details["skill_count"] = len(skills)
    else:
        details["skill_count"] = 0
    
    domain = parsed.get("domain", "") if isinstance(parsed, dict) else ""
    if domain and ak["domain"].lower() in domain.lower():
        score += 5; details["domain_match"] = True
    else:
        details["domain_match"] = False
    
    oc = parsed.get("overall_confidence") if isinstance(parsed, dict) else None
    if isinstance(oc, (int, float)) and oc >= 0.8:
        score += 5
    
    details["total_score"] = min(score, 100)
    return min(score, 100), details

# ── MAIN ──
print("=" * 100)
print("TESTING 3 NEW MODELS: qwen3.6-35b-a3b, phi-4, codestral-2508")
print("=" * 100)

all_results = []
for model_id, label in MODELS:
    print(f"\n{'─' * 100}")
    print(f"  {label} ({model_id})")
    print(f"{'─' * 100}")
    
    model_totals = {"score": 0, "tokens": 0, "time": 0, "skills": 0, "successes": 0}
    
    for rfile in RESUMES:
        with open(os.path.join(BASE, rfile)) as f:
            text = f.read()
        rname = rfile.replace(".pdf.txt", "")
        
        print(f"\n  ▶ {rname}...", end=" ", flush=True)
        r = call_model(model_id, text)
        
        entry = {"resume": rname, "ok": r["ok"], "latency": r["latency"],
                 "tokens": r["tokens"]}
        
        if r["ok"] and r["content"]:
            parsed = parse_json(r["content"])
            if parsed:
                sc, det = score_against_answer(parsed, ANSWER_KEY[rname])
                entry["score"] = sc
                entry["details"] = det
                model_totals["score"] += sc
                model_totals["tokens"] += r["tokens"]
                model_totals["time"] += r["latency"]
                model_totals["skills"] += det.get("skill_count", 0)
                model_totals["successes"] += 1
                print(f"Score: {sc}/100 | {r['tokens']} tokens | {r['latency']}s | Skills: {det.get('skill_count', 0)}")
            else:
                entry["score"] = 0
                entry["details"] = {"error": "JSON parse failed"}
                model_totals["tokens"] += r["tokens"]
                model_totals["time"] += r["latency"]
                print(f"FAIL (JSON parse error) | {r['tokens']} tokens | {r['latency']}s")
        else:
            entry["score"] = 0
            entry["details"] = {"error": r.get("error", "unknown")}
            model_totals["tokens"] += r["tokens"]
            model_totals["time"] += r["latency"]
            print(f"FAIL ({r.get('error', 'unknown')[:50]}) | {r['tokens']} tokens | {r['latency']}s")
        
        all_results.append({"model": label, "model_id": model_id, **entry})
    
    # Model summary
    n = model_totals["successes"]
    avg_score = model_totals["score"] / max(n, 1)
    avg_skills = model_totals["skills"] / max(n, 1)
    print(f"\n  ══ {label} SUMMARY ══")
    print(f"  Successes: {n}/5 | Avg Score: {avg_score:.1f} | Total Tokens: {model_totals['tokens']} | Total Time: {model_totals['time']:.1f}s | Avg Skills: {avg_skills:.1f}")
    
    all_results.append({
        "model": label,
        "model_id": model_id,
        "resume": "__SUMMARY__",
        "avg_score": round(avg_score, 1),
        "total_tokens": model_totals["tokens"],
        "total_time": round(model_totals["time"], 1),
        "successes": n,
        "avg_skills": round(avg_skills, 1),
    })

# Save results
with open("/home/skystarved/dev_workspaces/new_models_results.json", "w") as f:
    json.dump(all_results, f, indent=2)
print("\n\nResults saved to new_models_results.json")

# Print final summary
print("\n" + "=" * 100)
print("FINAL RESULTS")
print("=" * 100)
for r in all_results:
    if r["resume"] == "__SUMMARY__":
        print(f"{r['model']:<30} | Score: {r['avg_score']:.1f} | Tokens: {r['total_tokens']} | Time: {r['total_time']:.1f}s | Skills: {r['avg_skills']:.1f} | {r['successes']}/5")
print("=" * 100)
