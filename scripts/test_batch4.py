#!/usr/bin/env python3
"""
Test custom models with reasoning-model support.
Models: Ministral 14B, Ring 2.6 1T (reasoning), Aion 1.0 Mini (reasoning), DeepSeek Chat V3
Reasoning models: strip internal dialogue, extract only final JSON.
Uses SAME scoring as resume_parsing_benchmark.py.
"""
import json, os, time, requests, sys, re

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY: print("ERROR: OPENROUTER_API_KEY_1 not set"); sys.exit(1)
BASE = "/mnt/c/Users/jeffd/latexRoot/extracted_text"

RESUMES = [
    "Calderon_DataMAR25.pdf.txt", "Calderon_CyberResearch.pdf.txt",
    "Calderon_Boeing.pdf.txt", "Calderon_Amazon.pdf.txt", "CalderonGOVResume.pdf.txt",
]

MODELS = [
    ("mistralai/ministral-14b-2512",   "Ministral 14B",       False),
    ("inclusionai/ring-2.6-1t",        "Ring 2.6 1T",         True),
    ("aion-labs/aion-1.0-mini",        "Aion 1.0 Mini",       True),
    ("deepseek/deepseek-chat",         "DeepSeek Chat V3",    False),
]

PRICES = {
    "mistralai/ministral-14b-2512":  {"in": 0.2000, "out": 0.2000, "blended": 0.2000},
    "inclusionai/ring-2.6-1t":       {"in": 0.0750, "out": 0.6250, "blended": 0.2125},
    "aion-labs/aion-1.0-mini":       {"in": 0.7000, "out": 1.4000, "blended": 0.8750},
    "deepseek/deepseek-chat":        {"in": 0.2002, "out": 0.8001, "blended": 0.3502},
}

# ── GROUND TRUTH ANSWER KEY ──
ANSWER_KEY = {
    "Calderon_DataMAR25": {
        "title": "Operations Manager", "experience_count": 4,
        "expected_companies": ["NOAA", "NOAA", "Naval Research Laboratory", "University of Maryland"],
        "education_count": 3, "certifications_count": 3, "projects_count": 4,
        "expected_skills": ["Python", "NoSQL", "MongoDB", "Azure Data Studio", "Git", "Docker", "Linux",
            "RESTful", "JSON", "XML", "AWS Lambda", "TensorFlow", "Keras", "PyTorch",
            "Pandas", "NumPy", "Matplotlib", "Seaborn", "Scikit-learn", "Jupyter",
            "C++", "SQL", "ETL", "data modeling", "visualization", "data mining", "APIs", "Smartsheet"],
        "total_bullets_expected": 10, "domain": "Technology",
    },
    "Calderon_CyberResearch": {
        "title": "Operations Manager", "experience_count": 6,
        "expected_companies": ["NOAA", "NOAA", "Naval Research Laboratory", "University of Maryland", "United States Air Force", "United States Air Force"],
        "education_count": 3, "certifications_count": 3, "projects_count": 0,
        "expected_skills": ["Python", "Pandas", "NumPy", "Matplotlib", "Seaborn", "Scikit-learn",
            "APIs", "Cloud Services", "Project Management", "ETL", "Network Security", "Leadership", "data pipelines"],
        "total_bullets_expected": 20, "domain": "Technology",
    },
    "Calderon_Boeing": {
        "title": "Data Analyst", "experience_count": 5,
        "expected_companies": ["WADEPS", "Everett Community College", "NOAA", "NOAA", "Naval Research Laboratory"],
        "education_count": 3, "certifications_count": 3, "projects_count": 3,
        "expected_skills": ["Python", "LLMs", "Playwright", "AWS", "LangChain", "Selenium",
            "Pinecone", "YOLO", "SAM", "cloud", "project management"],
        "total_bullets_expected": 14, "domain": "Technology",
    },
    "Calderon_Amazon": {
        "title": "Marine Data Analyst", "experience_count": 3,
        "expected_companies": ["NOAA", "Naval Research Laboratory", "University of Maryland"],
        "education_count": 4, "certifications_count": 3, "projects_count": 0,
        "expected_skills": ["Python", "NoSQL", "MongoDB", "Azure Data Studio", "Git", "Docker",
            "Linux", "RESTful", "JSON", "XML", "AWS Lambda", "C++", "SQL", "Bash", "Ruby",
            "JavaScript", "ETL", "Data modeling", "visualization", "analysis", "data mining",
            "ArcGIS", "CARIS", "data schema design"],
        "total_bullets_expected": 10, "domain": "Technology",
    },
    "CalderonGOVResume": {
        "title": "Commissioned Officer", "experience_count": 4,
        "expected_companies": ["NOAA", "Naval Research Laboratory", "University of Maryland", "United States Air Force"],
        "education_count": 4, "certifications_count": 2, "projects_count": 0,
        "expected_skills": ["Python", "APIs", "Cloud Services", "Project Management", "policy review",
            "compliance", "contracting", "budgeting", "Network Security", "Leadership",
            "database administration", "server administration", "coding standards",
            "Linux", "C++", "MATLAB", "Pandas"],
        "total_bullets_expected": 14, "domain": "Technology",
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
def call_model(model_id, text, is_reasoning=False):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Parse:\n\n{text}"}]
    p = {"model": model_id, "messages": msgs, "temperature": 0.0, "max_tokens": 8192}
    if not is_reasoning:
        p["response_format"] = {"type": "json_object"}

    resp = None; start = time.time()
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=h, json=p, timeout=300)
        elapsed = time.time() - start
        if resp.status_code == 400 and not is_reasoning:
            del p["response_format"]
            start = time.time()
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=h, json=p, timeout=300)
            elapsed = time.time() - start
        resp.raise_for_status()
        d = resp.json()
        u = d.get("usage", {})

        content = d["choices"][0]["message"].get("content") or ""
        reasoning = d["choices"][0]["message"].get("reasoning") or ""

        # For reasoning models: if content null/empty, try reasoning field
        if (not content or content.strip() == "") and reasoning:
            content = reasoning

        # For reasoning models: try to extract just the final JSON from the reasoning chain
        if is_reasoning and content:
            # Common patterns for reasoning chain: final output after last <｜end▁of▁thinking｜> marker
            # Try to find the LAST complete JSON object in the output
            ext = extract_json_from_reasoning(content)
            if ext:
                content = ext

        return {"ok": True, "content": content, "latency": round(elapsed, 2),
                "tokens": u.get("total_tokens", 0), "prompt": u.get("prompt_tokens", 0),
                "completion": u.get("completion_tokens", 0),
                "had_reasoning": bool(reasoning)}
    except Exception as e:
        elapsed = time.time() - start
        err = str(e)[:200]
        if resp is not None:
            try: err += f" | {resp.text[:300]}"
            except: pass
        return {"ok": False, "content": None, "latency": round(elapsed, 2), "tokens": 0,
                "prompt": 0, "completion": 0, "error": err[:300]}

def extract_json_from_reasoning(content):
    """Extract the final JSON from a reasoning chain. Try multiple strategies."""
    # Strategy 1: Look for last fenced JSON block
    fence_matches = list(re.finditer(r'```(?:json)?\s*([\s\S]*?)```', content))
    if fence_matches:
        # Try the last fence block first
        for m in reversed(fence_matches):
            try:
                json_str = m.group(1).strip()
                # Remove comments
                json_str = "\n".join(l for l in json_str.split("\n") if not l.strip().startswith("//"))
                obj = json.loads(json_str)
                if isinstance(obj, dict) and "title" in obj:
                    return json_str
            except: pass

    # Strategy 2: Find the LAST {...} that has the expected fields
    braces = list(re.finditer(r'\{', content))
    if braces:
        # Try last few braces
        for m in reversed(braces[-5:]):
            s = m.start()
            depth = 1; i = s + 1
            while i < len(content) and depth > 0:
                if content[i] == '{': depth += 1
                elif content[i] == '}': depth -= 1
                i += 1
            if depth == 0:
                candidate = content[s:i]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict) and "title" in obj:
                        return candidate
                except: pass

    # Strategy 3: Remove everything before the LAST occurrence of common closing markers
    for marker in ["Final output:", "Final JSON:", "Output:", "Result:", "ANSWER:", "---"]:
        idx = content.rfind(marker)
        if idx >= 0:
            after = content[idx + len(marker):]
            s, e = after.find("{"), after.rfind("}")
            if s >= 0 and e > s:
                try:
                    obj = json.loads(after[s:e+1])
                    if isinstance(obj, dict) and "title" in obj:
                        return after[s:e+1]
                except: pass

    return None

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
    score += round(10 * min(edu_count, ak["education_count"]) / max(edu_count, ak["education_count"], 1))

    certs = parsed.get("certifications", []) if isinstance(parsed, dict) else []
    cert_count = len(certs) if isinstance(certs, list) else 0
    details["cert_count"] = cert_count; details["cert_expected"] = ak["certifications_count"]
    score += round(10 * min(cert_count, ak["certifications_count"]) / max(cert_count, ak["certifications_count"], 1))

    proj = parsed.get("projects", []) if isinstance(parsed, dict) else []
    proj_count = len(proj) if isinstance(proj, list) else 0
    details["proj_count"] = proj_count; details["proj_expected"] = ak["projects_count"]
    if ak["projects_count"] == 0: score += 10
    else: score += round(10 * min(proj_count, ak["projects_count"]) / max(proj_count, ak["projects_count"], 1))

    eskills = [s.lower() for s in parsed.get("skills", [])] if isinstance(parsed, dict) else []
    expected_skills = [s.lower() for s in ak["expected_skills"]]
    matches = sum(1 for es in expected_skills if any(es in exs for exs in eskills))
    details["skill_matches"] = f"{matches}/{len(expected_skills)}"
    details["skill_count"] = len(eskills)
    score += round(10 * min(matches / max(len(expected_skills), 1), 1.0))

    if isinstance(exp, list):
        bullets_total = sum(len(j.get("bullets", [])) for j in exp if isinstance(j, dict))
        details["bullet_count"] = bullets_total; details["bullet_expected"] = ak["total_bullets_expected"]
        score += round(5 * min(bullets_total, ak["total_bullets_expected"]) / max(bullets_total, ak["total_bullets_expected"], 1))

    domain = (parsed.get("domain", "") or "").lower() if isinstance(parsed, dict) else ""
    if ak["domain"].lower() in domain or domain in ["technology", "tech", "data"]:
        details["domain_match"] = True; score += 5
    else:
        details["domain_match"] = False

    return min(score, 100), details

# ── MAIN ──
print("=" * 100)
print("TESTING 4 MODELS (with reasoning-model extraction)")
print("=" * 100)
for m_id, label, is_r in MODELS:
    p = PRICES[m_id]
    flag = " [REASONING]" if is_r else ""
    print(f"  {label} ({m_id}){flag} — ${p['blended']:.4f}/M blended")
print("=" * 100)

all_summaries = []

for model_id, label, is_reasoning in MODELS:
    print(f"\n{'─' * 100}")
    print(f"  {label} ({model_id}) {'[REASONING]' if is_reasoning else ''}")
    print(f"{'─' * 100}")

    totals = {"score": 0, "tokens": 0, "time": 0, "skills": 0, "successes": 0, "reasoning_hits": 0}

    for rfile in RESUMES:
        with open(os.path.join(BASE, rfile)) as f:
            text = f.read()
        rname = rfile.replace(".pdf.txt", "")

        sys.stdout.write(f"\n  ▶ {rname}... "); sys.stdout.flush()
        r = call_model(model_id, text, is_reasoning)

        if r.get("had_reasoning"):
            totals["reasoning_hits"] += 1

        if r["ok"] and r["content"]:
            parsed = parse_json(r["content"])
            if parsed:
                sc, det = score_against_answer(parsed, ANSWER_KEY[rname])
                totals["score"] += sc; totals["tokens"] += r["tokens"]
                totals["time"] += r["latency"]; totals["skills"] += det.get("skill_count", 0)
                totals["successes"] += 1
                reason_note = " [reasoning]" if r.get("had_reasoning") else ""
                print(f"Score: {sc}/100 | {r['tokens']}tk | {r['latency']}s | Skills: {det.get('skill_matches','?')}{reason_note}")
            else:
                totals["tokens"] += r["tokens"]; totals["time"] += r["latency"]
                reason_note = " [reasoning]" if r.get("had_reasoning") else ""
                print(f"JSON PARSE FAIL | {r['tokens']}tk | {r['latency']}s{reason_note}")
        else:
            totals["tokens"] += r.get("tokens", 0); totals["time"] += r.get("latency", 0)
            print(f"FAIL ({r.get('error', 'unknown')[:60]})")

    n = totals["successes"]
    avg_score = totals["score"] / max(n, 1)
    avg_skills = totals["skills"] / max(n, 1)
    p = PRICES[model_id]

    print(f"\n  ══ {label} SUMMARY ══")
    print(f"  Successes: {n}/5 | Avg Score: {avg_score:.1f} | Tokens: {totals['tokens']} | Time: {totals['time']:.1f}s | Reasoning responses: {totals['reasoning_hits']}")

    all_summaries.append({
        "model": label, "model_id": model_id, "is_reasoning": is_reasoning,
        "avg_score": round(avg_score, 1), "total_tokens": totals["tokens"],
        "total_time": round(totals["time"], 1), "successes": n,
        "avg_skills": round(avg_skills, 1), "reasoning_hits": totals["reasoning_hits"],
        "price_in": p["in"], "price_out": p["out"], "price_blended": p["blended"],
        "reliability": f"{n}/5",
        "time_per_resume": round(totals["time"] / 5, 1),
    })

# Save
with open("/home/skystarved/dev_workspaces/batch4_results.json", "w") as f:
    json.dump(all_summaries, f, indent=2)

print("\n\nResults saved to batch4_results.json")
print("\n" + "=" * 100)
print("FINAL RESULTS")
print("=" * 100)
print(f"{'Model':<25} | {'Score':<7} | {'Tokens':<7} | {'Time':<8} | {'Success':<7} | {'Reason':<6} | {'Price/M':<10}")
print("-" * 105)
for s in all_summaries:
    flag = "✓" if s['is_reasoning'] else ""
    print(f"{s['model']:<25} | {s['avg_score']:<7.1f} | {s['total_tokens']:<7} | {s['total_time']:<8.1f}s | {s['successes']}/5     | {flag:<6} | ${s['price_blended']:<8.4f}/M")
print("=" * 100)
