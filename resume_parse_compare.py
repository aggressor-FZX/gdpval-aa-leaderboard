#!/usr/bin/env python3
"""
Focused Resume Parsing Comparison
Tests models on 1 resume for parsing quality, speed, and cost.
"""
import json, os, time, requests, sys
from datetime import datetime, timezone

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY: print("ERROR: OPENROUTER_API_KEY_1 not set"); sys.exit(1)

BASE = "/mnt/c/Users/jeffd/latexRoot/extracted_text"
RESUME = "Calderon_DataMAR25.pdf.txt"

# Models to test (from AA leaderboard data)
MODELS = [
    ("xiaomi/mimo-v2-flash",          "MiMo-V2-Flash",         True),
    ("xiaomi/mimo-v2.5",              "MiMo-V2.5",             True),
    ("openai/gpt-oss-120b",           "gpt-oss-120b",          True),
    ("qwen/qwen3.5-9b",               "Qwen3.5 9B (reasoning)",True),
    ("qwen/qwen3.5-flash-02-23",      "Qwen3.5 Flash",         True),
    ("deepseek/deepseek-v4-flash",    "DeepSeek V4 Flash",     True),
    ("mistralai/mistral-small-2603",  "Mistral Small 4",       True),
    ("nvidia/nemotron-3-super-120b-a12b:free", "Nemotron 3 Super (free)", False),
    ("nvidia/nemotron-3-nano-30b-a3b:free",    "Nemotron 3 Nano 30B (free)", False),
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
    
    # Try with json_object mode first
    payload = {"model": model_id, "messages": msgs, "temperature": 0.0, "max_tokens": 4096,
               "response_format": {"type": "json_object"}}
    
    resp = None
    start = time.time()
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=120)
        elapsed = time.time() - start
        
        if resp.status_code == 400:
            # Model doesn't support json_object — retry without it
            del payload["response_format"]
            start = time.time()
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=120)
            elapsed = time.time() - start
        
        resp.raise_for_status()
        data = resp.json()
        
        usage = data.get("usage", {})
        content = data["choices"][0]["message"].get("content")
        # Reasoning models return content as null, output in 'reasoning' field
        if content is None or content.strip() == "":
            content = data["choices"][0]["message"].get("reasoning", "")
        
        return {"ok": True, "content": content, "latency": round(elapsed, 2),
                "tokens": usage.get("total_tokens", 0),
                "cost": None}  # OR doesn't return cost for most models
    except Exception as e:
        elapsed = time.time() - start
        err = str(e)
        if resp is not None:
            try: err += f" | {resp.text[:200]}"
            except: pass
        return {"ok": False, "error": err, "latency": round(elapsed, 2), "content": None, "tokens": 0}

def parse_json(content):
    """Parse JSON with multiple fallback strategies."""
    if not content: return None
    # Direct
    try: return json.loads(content)
    except: pass
    # Strip // comments
    clean = "\n".join(l for l in content.split("\n") if not l.strip().startswith("//"))
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

def score_json(d):
    """Score parsed JSON against expected schema (0-100%)."""
    if not isinstance(d, dict): return 0, "not a dict"
    score, total = 0, 10
    
    checks = [
        ("title", lambda: isinstance(d.get("title"), str) and len(d["title"]) > 0),
        ("skills", lambda: isinstance(d.get("skills"), list) and len(d["skills"]) > 0),
        ("experience", lambda: isinstance(d.get("experience"), list) and len(d["experience"]) > 0),
        ("education", lambda: isinstance(d.get("education"), list) and len(d["education"]) > 0),
        ("certifications", lambda: isinstance(d.get("certifications"), list)),
        ("projects", lambda: isinstance(d.get("projects"), list)),
        ("domain", lambda: isinstance(d.get("domain"), str) and len(d["domain"]) > 0),
        ("confidence", lambda: isinstance(d.get("overall_confidence"), (int, float))),
        ("title_confidence", lambda: isinstance(d.get("title_confidence"), (int, float))),
        ("skill_count", lambda: isinstance(d.get("skill_count"), int) and d["skill_count"] > 0),
    ]
    for name, fn in checks:
        if fn(): score += 1
    
    return round(score / total * 100, 1)

print("=" * 90)
print(f"RESUME PARSING COMPARISON — {len(MODELS)} models × 1 resume")
print(f"Resume: {RESUME}")
print(f"Started: {datetime.now(tz=timezone.utc).isoformat()}")
print("=" * 90)

with open(os.path.join(BASE, RESUME)) as f:
    resume_text = f.read()

print(f"\nResume size: {len(resume_text)} chars\n")

results = []
for model_id, label, is_paid in MODELS:
    print(f"{'─' * 90}")
    print(f"  {label} ({model_id})")
    print(f"{'─' * 90}")
    
    r = call_model(model_id, resume_text)
    
    entry = {"model": label, "paid": is_paid, "success": r["ok"],
             "latency": r["latency"], "tokens": r["tokens"], "error": r.get("error")}
    
    if r["ok"] and r["content"]:
        out_len = len(r["content"])
        parsed = parse_json(r["content"])
        if parsed:
            score = score_json(parsed)
            entry["score"] = score
            entry["output_chars"] = out_len
            # Show detected keys
            keys = list(parsed.keys()) if isinstance(parsed, dict) else []
            exp_c = len(parsed.get("experience", [])) if isinstance(parsed.get("experience"), list) else 0
            edu_c = len(parsed.get("education", [])) if isinstance(parsed.get("education"), list) else 0
            skl_c = len(parsed.get("skills", [])) if isinstance(parsed.get("skills"), list) else 0
            cer_c = len(parsed.get("certifications", [])) if isinstance(parsed.get("certifications"), list) else 0
            pro_c = len(parsed.get("projects", [])) if isinstance(parsed.get("projects"), list) else 0
            print(f"    ✅ Score: {score}% | Tokens: {r['tokens']} | Time: {r['latency']}s | Out: {out_len}ch")
            print(f"    Keys: {keys}")
            print(f"    Jobs:{exp_c} Edu:{edu_c} Skills:{skl_c} Certs:{cer_c} Projects:{pro_c}")
        else:
            entry["score"] = 0
            entry["output_chars"] = out_len
            print(f"    ❌ Invalid JSON: {r['content'][:100]}")
    else:
        entry["score"] = 0
        entry["output_chars"] = 0
        print(f"    ❌ Error: {r.get('error', 'unknown')}")
    
    results.append(entry)
    print()

# Summary
print("=" * 90)
print("SCOREBOARD")
print("=" * 90)
print(f"{'Model':35s} | {'Score':7s} | {'Tokens':7s} | {'Time':6s} | {'Out':6s} | {'Paid':5s}")
print("-" * 80)
for e in sorted(results, key=lambda x: x["score"], reverse=True):
    score = f"{e['score']:.0f}%" if e.get("score") else "FAIL"
    paid = "PAID" if e["paid"] else "FREE"
    out = e.get("output_chars", 0) or 0
    print(f"{e['model']:35s} | {score:>6s} | {e['tokens']:5d}  | {e['latency']:4.1f}s | {out:5d} | {paid:>4s}")

# Save
with open("resume_parse_results.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nResults saved to resume_parse_results.json")
