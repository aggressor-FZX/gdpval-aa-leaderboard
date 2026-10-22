#!/usr/bin/env python3
"""
Quality-Focused Resume Parsing Comparison
Tests: DeepSeek V4 Flash, Qwen3.5 9B, Step 3.5 Flash (+ MiMo baseline)
Measures: schema compliance, skill count, extraction accuracy, bullet quality
"""
import json, os, time, requests, sys
from datetime import datetime, timezone

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
    ("xiaomi/mimo-v2-flash",          "MiMo-V2-Flash (baseline)"),
    ("deepseek/deepseek-v4-flash",    "DeepSeek V4 Flash"),
    ("qwen/qwen3.5-9b",               "Qwen3.5 9B"),
    ("stepfun/step-3.5-flash",        "Step 3.5 Flash"),
]

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

RULES: Bullets ≤20 words. Omit empty fields. Dates as MM/YYYY. No markdown. No comments."""

def call_model(model_id, text):
    headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Parse:\n\n{text}"}]
    payload = {"model": model_id, "messages": msgs, "temperature": 0.0, "max_tokens": 4096,
               "response_format": {"type": "json_object"}}
    
    resp = None
    start = time.time()
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=120)
        elapsed = time.time() - start
        
        if resp.status_code == 400:
            del payload["response_format"]
            start = time.time()
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=120)
            elapsed = time.time() - start
        
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        content = data["choices"][0]["message"].get("content")
        if content is None or content.strip() == "":
            content = data["choices"][0]["message"].get("reasoning", "")
        
        return {"ok": True, "content": content, "latency": round(elapsed, 2),
                "tokens": usage.get("total_tokens", 0), "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0)}
    except Exception as e:
        elapsed = time.time() - start
        err = str(e)
        if resp is not None:
            try: err += f" | {resp.text[:300]}"
            except: pass
        return {"ok": False, "error": err, "latency": round(elapsed, 2), "content": None, "tokens": 0,
                "prompt_tokens": 0, "completion_tokens": 0}

def parse_json(content):
    if not content: return None
    # Strip // comments
    clean = "\n".join(l for l in content.split("\n") if not l.strip().startswith("//"))
    # Direct
    try: return json.loads(clean)
    except: pass
    # Extract {...}
    s, e = clean.find("{"), clean.rfind("}")
    if s >= 0 and e > s:
        try: return json.loads(clean[s:e+1])
        except: pass
    # <answer> tags
    if "<answer>" in content:
        s = content.find("<answer>") + 8; e = content.find("</answer>")
        if e > s:
            try: return json.loads(content[s:e].strip())
            except: pass
    return None

def quality_score(d):
    """Score from 0-100, rewarding schema match, field population, data accuracy."""
    if not isinstance(d, dict): return 0, {}, {}
    
    scores = {}
    
    # 1. Schema: correct field names (20 pts)
    expected = {"title":0, "title_confidence":0, "skills":0, "skill_count":0,
                "experience":0, "education":0, "projects":0, "certifications":0,
                "domain":0, "overall_confidence":0}
    schema_ok = sum(1 for k in expected if k in d)
    scores["schema"] = round(schema_ok / len(expected) * 20, 1)
    
    # 2. Skill extraction quality (15 pts)
    skills = d.get("skills", [])
    skills_count = skills if isinstance(skills, list) else []
    # Penalize extremely short lists (<5) and reward completeness
    if len(skills_count) >= 30: scores["skills"] = 15
    elif len(skills_count) >= 20: scores["skills"] = 12
    elif len(skills_count) >= 10: scores["skills"] = 8
    elif len(skills_count) >= 5: scores["skills"] = 5
    else: scores["skills"] = 0
    
    # 3. Experience extraction (15 pts)
    exp = d.get("experience", [])
    if isinstance(exp, list):
        exp_count = len(exp)
        if exp_count >= 4: scores["experience"] = 15
        elif exp_count == 3: scores["experience"] = 12
        elif exp_count == 2: scores["experience"] = 8
        elif exp_count == 1: scores["experience"] = 5
        else: scores["experience"] = 0
        # Bonus for bullets in each experience
        bullets_total = sum(len(e.get("bullets", [])) for e in exp if isinstance(e, dict))
        scores["bullets"] = min(5, round(bullets_total / 3))
    else:
        scores["experience"] = 0
        scores["bullets"] = 0
    
    # 4. Education extraction (10 pts) - resume has 3 degrees
    edu = d.get("education", [])
    if isinstance(edu, list):
        edu_count = len(edu)
        if edu_count >= 3: scores["education"] = 10
        elif edu_count == 2: scores["education"] = 7
        elif edu_count == 1: scores["education"] = 4
        else: scores["education"] = 0
    else:
        scores["education"] = 0
    
    # 5. Certifications (10 pts) - resume has 3 certs
    certs = d.get("certifications", [])
    if isinstance(certs, list):
        cert_count = len(certs)
        if cert_count >= 3: scores["certifications"] = 10
        elif cert_count == 2: scores["certifications"] = 7
        elif cert_count == 1: scores["certifications"] = 4
        else: scores["certifications"] = 0
    else:
        scores["certifications"] = 0
    
    # 6. Projects (10 pts) - resume has 4 projects
    proj = d.get("projects", [])
    if isinstance(proj, list):
        proj_count = len(proj)
        if proj_count >= 4: scores["projects"] = 10
        elif proj_count == 3: scores["projects"] = 8
        elif proj_count == 2: scores["projects"] = 5
        elif proj_count == 1: scores["projects"] = 3
        else: scores["projects"] = 0
    else:
        scores["projects"] = 0
    
    # 7. Title confidence (5 pts)
    tc = d.get("title_confidence")
    if isinstance(tc, (int, float)) and tc >= 0.9: scores["title_conf"] = 5
    elif isinstance(tc, (int, float)) and tc >= 0.7: scores["title_conf"] = 3
    elif isinstance(tc, (int, float)): scores["title_conf"] = 1
    else: scores["title_conf"] = 0
    
    # 8. Domain (5 pts)
    if d.get("domain"): scores["domain"] = 5
    else: scores["domain"] = 0
    
    # 9. Overall confidence (5 pts)
    oc = d.get("overall_confidence")
    if isinstance(oc, (int, float)) and oc >= 0.8: scores["overall_conf"] = 5
    elif isinstance(oc, (int, float)): scores["overall_conf"] = 2
    else: scores["overall_conf"] = 0
    
    total = sum(scores.values())
    
    details = {
        "skills_count": len(skills_count),
        "experience_count": len(exp) if isinstance(exp, list) else 0,
        "education_count": len(edu) if isinstance(edu, list) else 0,
        "certifications_count": len(certs) if isinstance(certs, list) else 0,
        "projects_count": len(proj) if isinstance(proj, list) else 0,
        "bullets_total": bullets_total if isinstance(exp, list) else 0,
        "schema_fields_match": f"{schema_ok}/{len(expected)}",
    }
    
    return min(total, 100), scores, details

# ── Main ──
print("=" * 100)
print("QUALITY-FOCUSED PARSING COMPARISON — 4 models × 5 resumes")
print("=" * 100)

all_results = []
for model_id, label in MODELS:
    print(f"\n{'─' * 100}")
    print(f"  {label} ({model_id})")
    print(f"{'─' * 100}")
    
    model_totals = {"score": 0, "tokens": 0, "time": 0}
    model_details = []
    
    for rfile in RESUMES:
        with open(os.path.join(BASE, rfile)) as f:
            text = f.read()
        
        rname = rfile.replace(".pdf.txt", "")
        r = call_model(model_id, text)
        
        entry = {"resume": rname, "ok": r["ok"], "latency": r["latency"],
                 "tokens": r["tokens"], "prompt": r["prompt_tokens"], "completion": r["completion_tokens"]}
        
        if r["ok"] and r["content"]:
            parsed = parse_json(r["content"])
            if parsed:
                score, scores, details = quality_score(parsed)
                entry["score"] = score
                entry["scores"] = scores
                entry["details"] = details
                entry["keys"] = list(parsed.keys()) if isinstance(parsed, dict) else []
                model_totals["score"] += score
                model_totals["tokens"] += r["tokens"]
                model_totals["time"] += r["latency"]
                model_details.append(entry)
                
                print(f"\n  ▶ {rname}")
                print(f"    Score: {score:.0f}/100 | Tokens: {r['tokens']} | Time: {r['latency']}s")
                print(f"    Skills: {details['skills_count']} | Jobs: {details['experience_count']} | Edu: {details['education_count']} | Certs: {details['certifications_count']} | Projects: {details['projects_count']} | Bullets: {details['bullets_total']}")
                print(f"    Schema: {details['schema_fields_match']} | Keys: {list(parsed.keys())}")
            else:
                entry["score"] = 0
                entry["details"] = {"skills_count": 0}
                model_details.append(entry)
                print(f"\n  ▶ {rname} ❌ Invalid JSON: {r['content'][:80]}")
        else:
            entry["score"] = 0
            entry["details"] = {"skills_count": 0}
            model_details.append(entry)
            print(f"\n  ▶ {rname} ❌ Error: {r.get('error', 'unknown')[:80]}")
    
    all_results.append({"model": label, "results": model_details,
                        "avg_score": model_totals["score"] / max(len(model_details), 1),
                        "total_tokens": model_totals["tokens"],
                        "total_time": round(model_totals["time"], 1)})

# ── Final Scoreboard ──
print("\n\n" + "=" * 100)
print("FINAL SCOREBOARD")
print("=" * 100)
print(f"{'Model':30s} | {'Avg Score':10s} | {'Total Tokens':13s} | {'Total Time':11s} | {'Avg Out':7s}")
print("-" * 80)

for m in sorted(all_results, key=lambda x: x["avg_score"], reverse=True):
    avg_score = round(m["avg_score"], 1)
    avg_out = round(sum(r.get("details",{}).get("skills_count",0) for r in m["results"]) / max(len(m["results"]),1), 1)
    print(f"{m['model']:30s} | {avg_score:6.1f}%    | {m['total_tokens']:8d}     | {m['total_time']:6.1f}s   | {avg_out:4.1f}")

# ── Best at each category ──
print("\n\n" + "=" * 100)
print("BEST AT EACH METRIC")
print("=" * 100)

metrics = {
    "Most Skills Extracted": ("skills_count", "skills", max),
    "Most Jobs Found": ("experience_count", "experience", max),
    "Most Education Found": ("education_count", "education", max),
    "Most Certs Found": ("certifications_count", "certifications", max),
    "Most Projects Found": ("projects_count", "projects", max),
    "Best Schema Match": ("schema_fields_match", "schema", max),
    "Latency (fastest)": ("latency", "latency", min),
}

for metric_name, (detail_key, score_key, agg_fn) in metrics.items():
    best_val = None
    best_model = None
    for m in all_results:
        for r in m["results"]:
            val = None
            if score_key in ["latency"]:
                val = r.get(score_key)
            elif score_key in r.get("scores", {}):
                val = r["scores"].get(score_key)
            else:
                val = r.get("details", {}).get(detail_key, 0)
            
            if val is not None:
                if best_val is None or agg_fn == max and val > best_val or agg_fn == min and val < best_val:
                    best_val = val
                    best_model = m["model"]
    
    if isinstance(best_val, float) and score_key == "latency":
        print(f"  {metric_name:30s} → {best_model} ({best_val:.1f}s)")
    else:
        print(f"  {metric_name:30s} → {best_model} ({best_val})")

# Save
with open("resume_quality_results.json", "w") as f:
    json.dump(all_results, f, indent=2, default=str)
print(f"\n\nResults saved to resume_quality_results.json")
