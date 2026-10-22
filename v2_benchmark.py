#!/usr/bin/env python3
"""
V2 RESUME PARSING BENCHMARK — Enhanced Scoring
===============================================
5 resumes (3 tech + 1 admin + 1 electrician) × 18 models
New: Name extraction, date accuracy, cross-domain testing.
"""
import json, os, time, requests, sys, re

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY: print("ERROR: OPENROUTER_API_KEY_1 not set"); sys.exit(1)

# ── Resumes: 3 old + 2 new domain ──
CALDERON_BASE = "/mnt/c/Users/jeffd/latexRoot/extracted_text"
NEW_BASE = "/home/skystarved/dev_workspaces/resume_experiment"

RESUMES = [
    (os.path.join(CALDERON_BASE, "Calderon_DataMAR25.pdf.txt"), "Calderon_DataMAR25"),
    (os.path.join(CALDERON_BASE, "Calderon_Boeing.pdf.txt"),    "Calderon_Boeing"),
    (os.path.join(CALDERON_BASE, "Calderon_Amazon.pdf.txt"),    "Calderon_Amazon"),
    (os.path.join(NEW_BASE, "Whitfield_AdminNC25.txt"),          "Whitfield_AdminNC25"),
    (os.path.join(NEW_BASE, "Holloway_ElecWA25.txt"),            "Holloway_ElecWA25"),
]

# ── All 18 models (V3 writing test set + V2 parsing originals) ──
MODELS = [
    # Original V2 parsing models (7)
    ("mistralai/codestral-2508",       "Mistral Codestral 2508", 0.200, 0.900),
    ("xiaomi/mimo-v2-flash",           "MiMo-V2-Flash",          0.100, 0.300),
    ("deepseek/deepseek-v4-flash",     "DeepSeek V4 Flash",      0.090, 0.300),
    ("google/gemma-4-31b-it",          "Gemma 4 31B",            0.120, 0.360),
    ("bytedance-seed/seed-2.0-lite",   "Seed 2.0 Lite",          0.250, 2.000),
    ("google/gemini-2.5-flash-lite",   "Gemini 2.5 Flash Lite",  0.100, 0.400),
    ("deepseek/deepseek-chat-v3-0324", "DeepSeek Chat V3 0324",  0.200, 0.770),
    # New models from V3 writing test (11)
    ("xiaomi/mimo-v2.5-pro",           "MiMo V2.5 Pro",          0.270, 0.810),
    ("x-ai/grok-4.3",                 "Grok 4.3",               1.250, 2.500),
    ("anthracite-org/magnum-v4-72b",   "Magnum V4 72B",          3.000, 5.000),
    ("anthropic/claude-sonnet-4.6",    "Claude Sonnet 4.6",      3.000, 15.000),
    ("openai/gpt-5-mini",             "GPT-5 Mini",              0.250, 2.000),
    ("kwaipilot/kat-coder-pro-v2",     "Kat Coder Pro V2",       0.250, 0.750),
    ("minimax/minimax-m3",             "MiniMax M3",             0.250, 0.750),
    ("anthropic/claude-3.5-haiku",     "Claude 3.5 Haiku",       0.800, 4.000),
    ("z-ai/glm-5.1",                  "GLM 5.1",                0.500, 3.500),
    ("deepseek/deepseek-v4-pro",       "DeepSeek V4 Pro",        0.270, 0.810),
    ("moonshotai/kimi-k2.6:free",      "Kimi K2.6 (free)",       0.000, 0.000),
]

# ── ENHANCED ANSWER KEY ──
ANSWER_KEY = {
    "Calderon_DataMAR25": {
        "title": "Operations Manager",
        "name": "Jeff Calderon",
        "experience_count": 4,
        "expected_companies": ["NOAA", "NOAA", "Naval Research Laboratory", "University of Maryland"],
        "education_count": 3,
        "certifications_count": 3,
        "projects_count": 4,
        "expected_skills": ["Python", "NoSQL", "MongoDB", "Azure Data Studio", "Git", "Docker", "Linux",
            "RESTful", "JSON", "XML", "AWS Lambda", "TensorFlow", "Keras", "PyTorch",
            "Pandas", "NumPy", "Matplotlib", "Seaborn", "Scikit-learn", "Jupyter",
            "C++", "SQL", "ETL", "data modeling", "visualization", "data mining", "APIs", "Smartsheet"],
        "total_bullets_expected": 10,
        "domain": "Technology",
        "volunteer_count": 0, "affiliations_count": 0,
    },
    "Calderon_Boeing": {
        "title": "Data Analyst",
        "name": "Jeff Calderon",
        "experience_count": 5,
        "expected_companies": ["WADEPS", "Everett Community College", "NOAA", "NOAA", "Naval Research Laboratory"],
        "education_count": 3,
        "certifications_count": 3,
        "projects_count": 3,
        "expected_skills": ["Python", "LLMs", "Playwright", "AWS", "LangChain", "Selenium",
            "Pinecone", "YOLO", "SAM", "cloud", "project management"],
        "total_bullets_expected": 14,
        "domain": "Technology",
        "volunteer_count": 0, "affiliations_count": 0,
    },
    "Calderon_Amazon": {
        "title": "Marine Data Analyst",
        "name": "Jeff Calderon",
        "experience_count": 3,
        "expected_companies": ["NOAA", "Naval Research Laboratory", "University of Maryland"],
        "education_count": 4,
        "certifications_count": 3,
        "projects_count": 0,
        "expected_skills": ["Python", "NoSQL", "MongoDB", "Azure Data Studio", "Git", "Docker",
            "Linux", "RESTful", "JSON", "XML", "AWS Lambda", "C++", "SQL", "Bash", "Ruby",
            "JavaScript", "ETL", "Data modeling", "visualization", "analysis", "data mining",
            "ArcGIS", "CARIS", "data schema design"],
        "total_bullets_expected": 10,
        "domain": "Technology",
        "volunteer_count": 0, "affiliations_count": 0,
    },
    "Whitfield_AdminNC25": {
        "title": "Senior Administrative Coordinator",
        "name": "Sandra R. Whitfield",
        "experience_count": 4,
        "expected_companies": ["WakeMed", "Triangle United Way", "Cargill Dermatology", "NC State"],
        "education_count": 2,
        "certifications_count": 3,
        "projects_count": 0,
        "expected_skills": ["Microsoft Office", "Word", "Excel", "PowerPoint", "Outlook",
            "SharePoint", "Zoom", "Teams", "DocuSign", "Concur",
            "Raiser's Edge", "NextGen EHR", "Slate CRM", "Smartsheet", "Canva",
            "calendar", "travel", "meeting", "records", "HIPAA", "budget", "vendor",
            "onboarding", "accounts payable", "data entry"],
        "total_bullets_expected": 20,
        "domain": "Administrative",
        "volunteer_count": 2, "affiliations_count": 0,
    },
    "Holloway_ElecWA25": {
        "title": "Journeyman Electrician",
        "name": "Marcus D. Holloway",
        "experience_count": 3,
        "expected_companies": ["Cascade Power", "Pacific Northwest Electrical", "IBEW"],
        "education_count": 2,
        "certifications_count": 4,
        "projects_count": 2,
        "expected_skills": ["NEC", "OSHA", "NFPA", "WAC",
            "conduit", "three-phase", "480V", "motor control",
            "VFD", "transfer switch", "fire alarm", "low-voltage",
            "Megger", "thermal", "AutoCAD", "Bluebeam",
            "Excel", "ServiceTitan"],
        "total_bullets_expected": 18,
        "domain": "Construction",
        "volunteer_count": 0, "affiliations_count": 2,
    },
}

# ── ENHANCED SYSTEM PROMPT ──
SYSTEM = """You are a resume parser. Output ONLY valid JSON. Do NOT include markdown, comments, or explanations.

The JSON MUST have these fields:
{
  "name": "Full name from top of resume",
  "title": "Most recent job title",
  "title_confidence": 0.0-1.0,
  "skills": ["skill1", "skill2"],
  "skill_count": <int>,
  "experience": [{"title": "", "company": "", "start_date": "MM/YYYY", "end_date": "MM/YYYY or Present", "bullets": ["bullet"], "skills": ["skill"]}],
  "education": [{"degree": "", "institution": "", "start_date": "MM/YYYY", "end_date": "MM/YYYY", "gpa": null, "honors": []}],
  "projects": [{"name": "", "description": "", "technologies": [], "url": null}],
  "certifications": [{"name": "", "issuer": "", "date_earned": "MM/YYYY"}],
  "domain": "",
  "overall_confidence": 0.0-1.0,
  "volunteer": [{"organization": "", "role": ""}],
  "affiliations": ["name"]
}

DATABASE RULES:
- Dates MUST be MM/YYYY format. Use "Present" for current jobs.
- Bullets should be ≤20 words.
- Extract ALL skills mentioned anywhere in the resume.
- Omit empty arrays/objects. Null is OK for missing optional values."""

# ── HELPERS ──
def call_model(model_id, text, tries=2):
    h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Parse this resume:\n\n{text}"}]
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
            if not content or content.strip() == "":
                content = d["choices"][0]["message"].get("reasoning") or ""
            return {"ok": True, "content": content, "latency": round(elapsed, 2),
                    "tokens": u.get("total_tokens", 0), "prompt": u.get("prompt_tokens", 0),
                    "completion": u.get("completion_tokens", 0)}
        except Exception as e:
            if attempt < tries - 1: time.sleep(2); continue
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
    return None

# ── ENHANCED SCORING (base 100 + name/date bonus = 110 max) ──
def score_against_answer(parsed, ak):
    score = 0; details = {}

    # ── SCHEMA (20 pts) ──
    expected_fields = {"name", "title", "title_confidence", "skills", "skill_count",
                       "experience", "education", "projects", "certifications",
                       "domain", "overall_confidence", "volunteer", "affiliations"}
    if isinstance(parsed, dict):
        fields_present = sum(1 for f in expected_fields if f in parsed)
        details["schema_fields"] = f"{fields_present}/{len(expected_fields)}"
        score += min(20, int(fields_present / len(expected_fields) * 20))
    else:
        details["schema_fields"] = "0/13"

    # ── NAME EXTRACTION (5 bonus pts) ──
    name = (parsed.get("name", "") or "").lower() if isinstance(parsed, dict) else ""
    expected_name = ak["name"].lower()
    name_parts = expected_name.split()
    name_match = 0
    if len(name_parts) >= 2:
        if name_parts[0] in name: name_match += 3
        if name_parts[-1] in name: name_match += 2
    elif expected_name in name:
        name_match = 5
    details["name_match"] = f"{name_match}/5"
    score += name_match

    # ── TITLE (10 pts) ──
    title = parsed.get("title", "").lower() if isinstance(parsed, dict) else ""
    expected_title = ak["title"].lower()
    if expected_title in title:
        details["title_match"] = True; score += 10
    else:
        details["title_match"] = False

    # ── EXPERIENCE (15+5 pts) ──
    exp = parsed.get("experience", []) if isinstance(parsed, dict) else []
    exp_count = len(exp) if isinstance(exp, list) else 0
    details["exp_count"] = exp_count; details["exp_expected"] = ak["experience_count"]
    ratio = min(exp_count, ak["experience_count"]) / max(exp_count, ak["experience_count"], 1)
    score += round(15 * ratio)
    if isinstance(exp, list):
        companies = [j.get("company", "").lower() for j in exp if isinstance(j, dict)]
        expected = [c.lower() for c in ak["expected_companies"]]
        matches = sum(1 for ec in expected if any(ec in comp for comp in companies))
        details["company_matches"] = f"{matches}/{len(expected)}"
        score += min(5, matches)

    # ── DATE ACCURACY (5 bonus pts) ──
    if isinstance(exp, list) and len(exp) > 0:
        date_ok = 0
        date_pattern = re.compile(r"^\d{1,2}/\d{4}$")
        for j in exp:
            if isinstance(j, dict):
                sd = j.get("start_date", "")
                ed = j.get("end_date", "")
                if isinstance(sd, str) and (date_pattern.match(sd) or re.match(r"^\d{4}$", sd)): date_ok += 1
                if isinstance(ed, str) and (date_pattern.match(ed) or ed.lower() == "present" or re.match(r"^\d{4}$", ed)): date_ok += 1
        details["date_score"] = f"{date_ok}/{len(exp)*2}"
        score += min(5, int(date_ok / max(len(exp), 1)))
    else:
        details["date_score"] = "0"

    # ── EDUCATION (10 pts) ──
    edu = parsed.get("education", []) if isinstance(parsed, dict) else []
    edu_count = len(edu) if isinstance(edu, list) else 0
    details["edu_count"] = edu_count; details["edu_expected"] = ak["education_count"]
    score += round(10 * min(edu_count, ak["education_count"]) / max(edu_count, ak["education_count"], 1))

    # ── CERTIFICATIONS (10 pts) ──
    certs = parsed.get("certifications", []) if isinstance(parsed, dict) else []
    cert_count = len(certs) if isinstance(certs, list) else 0
    details["cert_count"] = cert_count; details["cert_expected"] = ak["certifications_count"]
    score += round(10 * min(cert_count, ak["certifications_count"]) / max(cert_count, ak["certifications_count"], 1))

    # ── PROJECTS (10 pts) ──
    proj = parsed.get("projects", []) if isinstance(parsed, dict) else []
    proj_count = len(proj) if isinstance(proj, list) else 0
    details["proj_count"] = proj_count; details["proj_expected"] = ak["projects_count"]
    if ak["projects_count"] == 0: score += 10
    else: score += round(10 * min(proj_count, ak["projects_count"]) / max(proj_count, ak["projects_count"], 1))

    # ── SKILLS MATCH (10 pts) ──
    eskills = [s.lower() for s in parsed.get("skills", [])] if isinstance(parsed, dict) else []
    expected_skills = [s.lower() for s in ak["expected_skills"]]
    matches = sum(1 for es in expected_skills if any(es in exs for exs in eskills))
    details["skill_matches"] = f"{matches}/{len(expected_skills)}"
    details["skill_count"] = len(eskills)
    score += round(10 * min(matches / max(len(expected_skills), 1), 1.0))

    # ── BULLETS (5 pts) ──
    if isinstance(exp, list):
        bullets_total = sum(len(j.get("bullets", [])) for j in exp if isinstance(j, dict))
        details["bullet_count"] = bullets_total; details["bullet_expected"] = ak["total_bullets_expected"]
        score += round(5 * min(bullets_total, ak["total_bullets_expected"]) / max(bullets_total, ak["total_bullets_expected"], 1))

    # ── DOMAIN (5 pts) ──
    domain = (parsed.get("domain", "") or "").lower() if isinstance(parsed, dict) else ""
    ak_domain = ak["domain"].lower()
    domain_map = {"technology": ["technology", "tech", "data", "software", "it "],
                  "administrative": ["administrative", "admin", "office", "healthcare"],
                  "construction": ["construction", "electrical", "trades", "skilled"]}
    matched = False
    for ak_tag, domain_keywords in domain_map.items():
        if ak_tag in ak_domain:
            if any(kw in domain for kw in domain_keywords):
                matched = True; break
    if ak_domain in domain: matched = True
    details["domain_match"] = matched
    score += 5 if matched else 0

    # ── VOLUNTEER/EXTRA (5 pts) ──
    vol = parsed.get("volunteer", []) if isinstance(parsed, dict) else []
    aff = parsed.get("affiliations", []) if isinstance(parsed, dict) else []
    extra_score = 0
    if ak.get("volunteer_count", 0) > 0 and isinstance(vol, list):
        extra_score += min(3, len(vol))
    if ak.get("affiliations_count", 0) > 0 and isinstance(aff, list):
        extra_score += min(2, len(aff))
    details["volunteer_count"] = len(vol) if isinstance(vol, list) else 0
    details["affiliations_count"] = len(aff) if isinstance(aff, list) else 0
    details["extra_pts"] = extra_score
    score += extra_score

    details["total_score"] = min(score, 110)
    return min(score, 110), details

# ── MAIN ──
print("=" * 100)
print("V2 RESUME PARSING BENCHMARK — 18 Models × 5 Resumes (3 domains)")
print("=" * 100)
print("Scoring: Schema(20) + Name(5) + Title(10) + Experience(15+5) + Dates(5)")
print("         + Education(10) + Certs(10) + Projects(10) + Skills(10)")
print("         + Bullets(5) + Domain(5) + Volunteer/Affiliations(5) = 110 max")
print("=" * 100)

all_results = []

for model_id, label, price_in, price_out in MODELS:
    blended = (price_in * 3 + price_out) / 4  # 3:1 ratio
    print(f"\n{'─' * 100}")
    print(f"  {label} ({model_id}) — ${blended:.3f}/M blended (3:1)")
    print(f"{'─' * 100}")

    totals = {"score": 0, "tokens": 0, "time": 0, "successes": 0}

    for filepath, rname in RESUMES:
        with open(filepath) as f:
            text = f.read()

        sys.stdout.write(f"\n  ▶ {rname}... "); sys.stdout.flush()
        r = call_model(model_id, text)

        if r["ok"] and r["content"]:
            parsed = parse_json(r["content"])
            if parsed:
                sc, det = score_against_answer(parsed, ANSWER_KEY[rname])
                totals["score"] += sc; totals["tokens"] += r["tokens"]
                totals["time"] += r["latency"]; totals["successes"] += 1
                print(f"Score: {sc}/110 | {r['tokens']}tk | {r['latency']}s | Name:{det.get('name_match','?')} Dates:{det.get('date_score','?')} Skills:{det.get('skill_matches','?')}")
            else:
                totals["tokens"] += r["tokens"]; totals["time"] += r["latency"]
                print(f"JSON PARSE FAIL | {r['tokens']}tk | {r['latency']}s")
        else:
            totals["tokens"] += r.get("tokens", 0); totals["time"] += r.get("latency", 0)
            print(f"FAIL ({r.get('error', 'unknown')[:60]})")

    n = totals["successes"]
    avg = totals["score"] / max(n, 1)
    avg_pct = (avg / 110) * 100  # percentage of max
    cost = (totals["tokens"] / 1_000_000) * blended

    print(f"\n  ══ {label} SUMMARY ══")
    print(f"  Successes: {n}/5 | Score: {avg:.1f}/110 ({avg_pct:.1f}%) | Tokens: {totals['tokens']} | Time: {totals['time']:.1f}s | Cost: ${cost:.4f}")

    all_results.append({
        "model": label, "model_id": model_id,
        "avg_score": round(avg, 1), "avg_pct": round(avg_pct, 1),
        "total_tokens": totals["tokens"], "total_time": round(totals["time"], 1),
        "successes": n, "reliability": f"{n}/5",
        "price_in": price_in, "price_out": price_out, "price_blended": round(blended, 4),
        "cost": round(cost, 6), "time_per_resume": round(totals["time"] / 5, 1),
    })

# Save
with open("/home/skystarved/dev_workspaces/v2_benchmark_results.json", "w") as f:
    json.dump(all_results, f, indent=2)

print("\n\n" + "=" * 100)
print("V2 FINAL RESULTS (sorted by avg_pct)")
print("=" * 100)
all_results.sort(key=lambda x: -x["avg_pct"])
print(f"{'#':<3} {'Model':<26} {'Score':<8} {'%':<7} {'Time':<8} {'$/Res':<9} {'Price/M':<9} {'Reliab'}")
print("-" * 90)
for i, s in enumerate(all_results, 1):
    cost_per = f"${s['cost']/5:.5f}" if s['cost'] else "?"
    print(f"{i:<3} {s['model']:<26} {s['avg_score']:.1f}/110{'':<1} {s['avg_pct']:.1f}%{'':<2} {s['total_time']:.1f}s{'':<3} {cost_per:<9} ${s['price_blended']:<7.3f}/M {s['reliability']}")
print("=" * 100)
