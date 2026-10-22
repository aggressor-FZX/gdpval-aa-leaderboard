#!/usr/bin/env python3
"""
Resume Parsing Experiment — Models × 5 Resumes
===============================================
Tests how well different models parse resume text into structured JSON.
Measures: cost, speed, JSON validity, field completeness, output size.
"""

import json
import os
import time
import requests
import sys
from datetime import datetime, timezone
from collections import defaultdict

# ── Configuration ──────────────────────────────────────────────────────────────

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY_1")
if not OPENROUTER_KEY:
    print("ERROR: OPENROUTER_API_KEY_1 not set in environment")
    sys.exit(1)

BASE_DIR = "/mnt/c/Users/jeffd/latexRoot/extracted_text"

RESUME_FILES = [
    "Calderon_DataMAR25.pdf.txt",
    "Calderon_CyberResearch.pdf.txt",
    "Calderon_Boeing.pdf.txt",
    "Calderon_Amazon.pdf.txt",
    "CalderonGOVResume.pdf.txt",
]

MODELS = [
    {"id": "xiaomi/mimo-v2-flash",              "label": "MiMo-V2-Flash",              "paid": True},
    {"id": "qwen/qwen3-8b",                     "label": "Qwen3 8B",                   "paid": True},
    {"id": "openai/gpt-oss-120b",               "label": "gpt-oss-120b",               "paid": True},
    {"id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", "label": "Nemotron 3 Nano Omni 30B (free)", "paid": False},
    {"id": "xiaomi/mimo-v2.5",                  "label": "MiMo-V2.5",                  "paid": True},
    {"id": "deepseek/deepseek-v4-flash",        "label": "DeepSeek V4 Flash",          "paid": True},
    {"id": "mistralai/mistral-small-2603",      "label": "Mistral Small 4",            "paid": True},
]

# NOTE: User requested 8 models but:
# - gpt-oss-120b (low) and (high) are same model ID on OpenRouter → tested once
# - Qwen3.5 9B is reasoning-only on OpenRouter → substituted with Qwen3 8B
# - Qwen3.5 4B not available on OpenRouter → substituted with Qwen3 8B
# - Sarvam 30B (high) not available on OpenRouter → skipped
# - Nemotron 3 Nano Omni only available as free tier → tested as free

# ── System Prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a resume parsing engine. Extract structured JSON from resume text.

OUTPUT ONLY valid JSON. No markdown fences, no explanations, no commentary.

SCHEMA:
{
  "title": "Most recent job title",
  "title_confidence": 0.0-1.0,
  "skills": ["skill1", "skill2", ...],
  "skill_count": <int>,
  "classified_skills": {
    "languages": ["Python", "SQL", ...],
    "tools": ["Docker", "Git", ...],
    "methods": ["Machine Learning", "ETL", ...]
  },
  "experience": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "start_date": "MM/YYYY",
      "end_date": "MM/YYYY or Present",
      "location": "City, State",
      "bullets": ["bullet1", "bullet2", ...],
      "skills": ["skill1", ...]
    }
  ],
  "education": [
    {
      "degree": "Degree Name",
      "institution": "School Name",
      "start_date": "MM/YYYY",
      "end_date": "MM/YYYY",
      "gpa": "GPA or null",
      "location": "City, State",
      "honors": ["honor1", ...]
    }
  ],
  "projects": [
    {
      "name": "Project Name",
      "description": "Brief description",
      "technologies": ["tech1", ...],
      "url": "url or null",
      "date": "MM/YYYY or null"
    }
  ],
  "certifications": [
    {
      "name": "Cert Name",
      "issuer": "Issuer",
      "date_earned": "MM/YYYY",
      "expiration": "MM/YYYY or null",
      "credential_id": "ID or null"
    }
  ],
  "domain": "Technology or other domain",
  "overall_confidence": 0.0-1.0,
  "timestamp": "ISO timestamp",
  "version": "1.0.0"
}

OUTPUT TOKEN REDUCTION RULES:
- Each bullet <=20 words
- Omit any key with null or empty value
- Dates as MM/YYYY format only
- Skills as flat strings, not objects
- No padding, no explanations, no markdown"""

# ── Helpers ────────────────────────────────────────────────────────────────────

def load_resume(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def call_model(model_cfg, resume_text):
    """Call OpenRouter and return results dict."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
    }

    base_payload = {
        "model": model_cfg["id"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this resume into JSON:\n\n{resume_text}"},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
    }

    resp = None
    start = time.time()
    try:
        # Try with json_object mode first
        payload = {**base_payload, "response_format": {"type": "json_object"}}
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers, json=payload, timeout=120,
        )
        elapsed = time.time() - start

        # If 400 (model doesn't support json_object), retry without it
        if resp.status_code == 400:
            start = time.time()
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=base_payload, timeout=120,
            )
            elapsed = time.time() - start

        resp.raise_for_status()
        data = resp.json()

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        # Cost from OpenRouter
        provider_info = data.get("provider", "")
        if isinstance(provider_info, dict):
            cost = provider_info.get("cost", None)
            if cost is not None:
                cost = float(cost)
        else:
            cost = None

        content = data["choices"][0]["message"].get("content")
        # Handle reasoning models that return content=null
        if content is None:
            content = data["choices"][0]["message"].get("reasoning", "")
            if not content:
                content = ""

        return {
            "success": True,
            "content": content,
            "latency_sec": round(elapsed, 2),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost,
        }
    except Exception as e:
        elapsed = time.time() - start
        error_msg = str(e)
        if resp is not None:
            try:
                error_msg += f" | {resp.text[:300]}"
            except Exception:
                pass
        return {
            "success": False,
            "error": error_msg,
            "latency_sec": round(elapsed, 2),
            "content": None,
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "cost_usd": None,
        }


def validate_json_structure(parsed):
    """Score how well the JSON matches the expected schema."""
    if not isinstance(parsed, dict):
        return {"score": 0, "total": 10, "pct": 0.0, "details": {"error": "not a dict"}}

    score = 0
    total = 0
    details = {}

    required_fields = ["title", "skills", "experience", "education", "overall_confidence"]
    for f in required_fields:
        total += 1
        if f in parsed and parsed[f] is not None:
            score += 1
            details[f] = "present"
        else:
            details[f] = "missing"

    total += 1
    if isinstance(parsed.get("skills"), list) and len(parsed["skills"]) > 0:
        score += 1
        details["skills_list"] = f"{len(parsed['skills'])} skills"
    else:
        details["skills_list"] = "empty/missing"

    total += 1
    if isinstance(parsed.get("experience"), list) and len(parsed["experience"]) > 0:
        score += 1
        details["experience_count"] = len(parsed["experience"])
    else:
        details["experience_count"] = 0

    total += 1
    if isinstance(parsed.get("education"), list) and len(parsed["education"]) > 0:
        score += 1
        details["education_count"] = len(parsed["education"])
    else:
        details["education_count"] = 0

    total += 1
    if isinstance(parsed.get("certifications"), list):
        score += 1
        details["certifications"] = len(parsed["certifications"])
    else:
        details["certifications"] = "missing"

    total += 1
    if isinstance(parsed.get("projects"), list):
        score += 1
        details["projects"] = len(parsed["projects"])
    else:
        details["projects"] = "missing"

    total += 1
    if isinstance(parsed.get("classified_skills"), dict):
        score += 1
        details["classified_skills"] = "present"
    else:
        details["classified_skills"] = "missing"

    total += 1
    if parsed.get("domain"):
        score += 1
        details["domain"] = parsed["domain"]
    else:
        details["domain"] = "missing"

    total += 1
    if isinstance(parsed.get("overall_confidence"), (int, float)):
        score += 1
        details["overall_confidence"] = parsed["overall_confidence"]
    else:
        details["overall_confidence"] = "missing"

    pct = round(score / total * 100, 1) if total > 0 else 0
    return {"score": score, "total": total, "pct": pct, "details": details}


def count_json_size(obj):
    return len(json.dumps(obj, default=str))


def try_parse_json(content):
    """Try to parse JSON from content, with fallback extraction."""
    if not content:
        return None, "empty content"
    try:
        parsed = json.loads(content)
        return parsed, None
    except json.JSONDecodeError:
        pass
    # Remove // style comments (common in model outputs)
    lines = content.split('\n')
    clean_lines = [l for l in lines if not l.strip().startswith('//')]
    clean = '\n'.join(clean_lines)
    try:
        parsed = json.loads(clean)
        return parsed, None
    except json.JSONDecodeError:
        pass
    # Try extracting {...} block from cleaned content
    start = clean.find("{")
    end = clean.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(clean[start:end+1])
            return parsed, None
        except json.JSONDecodeError:
            pass
    # Try extracting from <answer> tags
    if "<answer>" in content:
        start = content.find("<answer>") + len("<answer>")
        end = content.find("</answer>")
        if end > start:
            try:
                parsed = json.loads(content[start:end].strip())
                return parsed, None
            except json.JSONDecodeError:
                pass
    return None, content[:300]


# ── Main Experiment ────────────────────────────────────────────────────────────

def run_experiment():
    results = []

    print("=" * 100)
    print("RESUME PARSING EXPERIMENT — %d Models × %d Resumes" % (len(MODELS), len(RESUME_FILES)))
    print("Started:", datetime.now(tz=timezone.utc).isoformat())
    print("=" * 100)

    for model_cfg in MODELS:
        model_label = model_cfg["label"]
        print(f"\n{'─' * 100}")
        print(f"MODEL: {model_label} ({model_cfg['id']})")
        print(f"{'─' * 100}")

        for resume_file in RESUME_FILES:
            resume_path = os.path.join(BASE_DIR, resume_file)
            resume_name = resume_file.replace(".pdf.txt", "").replace(".docx.txt", "")

            if not os.path.exists(resume_path):
                print(f"  ⚠ SKIP: {resume_file} not found")
                continue

            resume_text = load_resume(resume_path)
            print(f"\n  ▶ {resume_name} ({len(resume_text)} chars)")

            result = call_model(model_cfg, resume_text)

            entry = {
                "model": model_label,
                "model_id": model_cfg["id"],
                "resume": resume_name,
                "resume_chars": len(resume_text),
                "success": result["success"],
                "latency_sec": result["latency_sec"],
                "prompt_tokens": result["prompt_tokens"],
                "completion_tokens": result["completion_tokens"],
                "total_tokens": result["total_tokens"],
                "cost_usd": result["cost_usd"],
                "validation": None,
                "output_size": None,
                "error": result.get("error"),
            }

            if result["success"] and result["content"]:
                parsed, err = try_parse_json(result["content"])
                if parsed is not None and isinstance(parsed, dict):
                    validation = validate_json_structure(parsed)
                    entry["validation"] = validation
                    entry["output_size"] = count_json_size(parsed)
                    print(f"    ✅ Valid JSON | Score: {validation['pct']}% | "
                          f"Tokens: {result['total_tokens']} | "
                          f"Time: {result['latency_sec']}s | "
                          f"Cost: ${result['cost_usd'] or 'N/A'} | "
                          f"Output: {entry['output_size']} chars")
                else:
                    preview = (err or result["content"])[:200]
                    entry["validation"] = {"score": 0, "total": 10, "pct": 0,
                                           "details": {"error": "not valid JSON", "preview": preview}}
                    entry["output_size"] = len(result["content"])
                    print(f"    ❌ Invalid JSON: {preview[:100]}")
            else:
                print(f"    ❌ API Error: {result.get('error', 'unknown')}")

            results.append(entry)

    return results


def print_summary(results):
    """Print summary tables."""
    print("\n\n" + "=" * 120)
    print("SUMMARY TABLE")
    print("=" * 120)

    by_model = defaultdict(list)
    for r in results:
        by_model[r["model"]].append(r)

    header = f"{'Model':35s} | {'Success':8s} | {'Avg Score':10s} | {'Avg Tokens':11s} | {'Avg Time':9s} | {'Avg Cost':9s} | {'Avg Out':8s}"
    print(header)
    print("-" * 120)

    for model_label, entries in sorted(by_model.items()):
        successes = sum(1 for e in entries if e["success"])
        valid_scores = [e["validation"]["pct"] for e in entries if e["success"] and e["validation"]]
        avg_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0
        avg_tokens = round(sum(e["total_tokens"] for e in entries) / len(entries))
        avg_time = round(sum(e["latency_sec"] for e in entries) / len(entries), 1)
        costs = [e["cost_usd"] for e in entries if e["cost_usd"] is not None]
        avg_cost = f"${round(sum(costs)/len(costs), 4):.4f}" if costs else "N/A"
        outs = [e["output_size"] for e in entries if e["output_size"]]
        avg_out = round(sum(outs) / len(outs)) if outs else 0

        succ_str = f"{successes}/{len(entries)}"
        print(f"{model_label:35s} | {succ_str:>8s} | {avg_score:8.1f}%  | {avg_tokens:8d}    | {avg_time:6.1f}s  | {avg_cost:>8s}  | {avg_out:5d}")

    print("-" * 120)

    # Best value
    print("\n\nBEST VALUE (Score per Dollar)")
    print("-" * 60)
    scored = []
    for model_label, entries in by_model.items():
        costs = [e["cost_usd"] for e in entries if e["cost_usd"] is not None]
        scores = [e["validation"]["pct"] for e in entries if e["success"] and e["validation"]]
        if costs and scores:
            total_cost = sum(costs)
            avg_s = sum(scores) / len(scores)
            scored.append((model_label, avg_s, total_cost, avg_s / total_cost if total_cost > 0 else float("inf")))

    scored.sort(key=lambda x: x[3], reverse=True)
    print(f"{'Rank':5s} | {'Model':35s} | {'Avg Score':10s} | {'Total Cost':11s} | {'Score/$':10s}")
    print("-" * 75)
    for i, (model, avg_s, tot_c, ratio) in enumerate(scored, 1):
        ratio_str = f"{ratio:.1f}" if ratio != float("inf") else "∞ (free)"
        print(f"{i:5d} | {model:35s} | {avg_s:8.1f}%  | ${tot_c:.4f}     | {ratio_str:>8s}")

    # Per-resume
    print("\n\nPER-RESUME BREAKDOWN")
    print("=" * 120)
    resume_names = sorted(set(r["resume"] for r in results))
    for rname in resume_names:
        print(f"\n── {rname} ──")
        r_entries = [r for r in results if r["resume"] == rname]
        print(f"{'Model':35s} | {'Score':7s} | {'Tokens':8s} | {'Time':6s} | {'Cost':8s} | {'Out':5s}")
        print("-" * 80)
        for e in sorted(r_entries, key=lambda x: x["validation"]["pct"] if x["validation"] else 0, reverse=True):
            score = f"{e['validation']['pct']:.0f}%" if e["validation"] else "FAIL"
            cost = f"${e['cost_usd']:.4f}" if e["cost_usd"] else "N/A"
            out = e["output_size"] or 0
            print(f"{e['model']:35s} | {score:>6s}  | {e['total_tokens']:6d}  | {e['latency_sec']:4.1f}s | {cost:>7s} | {out:4d}")


if __name__ == "__main__":
    results = run_experiment()
    print_summary(results)

    output_path = "resume_parsing_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n\nResults saved to {output_path}")