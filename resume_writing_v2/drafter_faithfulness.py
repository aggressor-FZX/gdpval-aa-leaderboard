"""Drafter-faithfulness harness — tests what the Imaginator drafter ACTUALLY does.

THE TASK (read from stages/drafter.py, not assumed)
---------------------------------------------------
The drafter is NOT asked to author a resume from a profile. It rewrites RAW
EXPERIENCE NOTES into STAR bullets under hard fact-preservation constraints:

  * company names must match the input exactly
  * only technologies named in the input may appear
  * metrics ONLY from a verified-metric list, value AND unit together
    ("30 hours", never a bare "30")
  * bullets 15-25 words, strong action verb first
  * no activity the source does not describe
  * "A bullet without a metric is NOT a failure"

So the thing worth measuring is FAITHFULNESS + FORMAT, not prose beauty. A model
that writes lovely bullets and invents "reduced latency 40%" has failed, and a
generic prose-quality score would reward it.

METRICS
-------
  fabrication   mentions of a technology/company NOT in the input (auto-fail)
  metric_fidelity  numbers used that are absent from the verified list, or
                   present but with the unit stripped
  format        bullets 15-25 words, starts with a strong verb, yields JSON
  coverage      how many source experiences survived into the output
  style         vague-verb usage ("Worked on", "Responsible for", "Strategized")

A model is only recommended if fabrication is 0 AND metric_fidelity is clean.
"""
from __future__ import annotations

import json
import re

# ── The test fixture: deliberately realistic, deliberately sparse ───────────
# Sparse metrics and thin technoony detail are what make fabrication tempting.
FIXTURE_EXPERIENCES = [
    {
        "company": "Cogito Metric",
        "role": "Data Engineer",
        "duration": "04/2024 - Present",
        "bullets": [
            "Built the resume parsing pipeline that processes incoming candidate resumes",
            "Reduced how long the parsing step takes by about 40% after reworking it",
            "Worked with Postgres and Python for the storage layer",
            "Handled a fairly large amount of archived document data",
            "Talked to the recruiting team about what fields they needed",
        ],
    },
    {
        "company": "NOAA",
        "role": "Data Analyst",
        "duration": "06/2021 - 03/2024",
        "bullets": [
            "Made charts and reports for weather data on a weekly cadence",
            "Cleaned messy oceanographic datasets before analysis",
            "Presented findings to a small group of scientists",
        ],
    },
]

VERIFIED_METRICS = [
    {"value": "40", "unit": "%", "kind": "percent"},
    {"value": "30", "unit": "hours", "kind": "duration"},
]

JOB_AD = """Data Scientist (Data Science) - Boeing Defense, Space & Security
- Develop and deploy Generative AI and large language model solutions,
  including retrieval-augmented generation and fine-tuning.
- Build data pipelines and ETL processes in Python and SQL.
- Work with distributed training and GPU infrastructure (H100 clusters).
- Containerize workloads with Docker and Kubernetes.
- Collaborate cross-functionally; support MLOps and CI/CD.
Required: Python, PyTorch, SQL, Docker, Kubernetes, AWS, LangChain.
"""

# Everything a model is allowed to name, derived from the fixture.
ALLOWED_TECH = {
    "postgres", "postgresql", "python", "sql", "excel", "tableau",
    "pandas", "numpy", "jupyter", "git", "parquet", "csv",
}
ALLOWED_COMPANIES = {"cogito metric", "noaa"}
# Technologies that appear ONLY in the JD — using them is fabrication.
# Matched on WORD BOUNDARIES: a plain substring test matched "rag" inside
# "storage", which flagged a faithful response as fabricated.
JD_ONLY_TECH = {
    "pytorch", "tensorflow", "docker", "kubernetes", "aws", "langchain",
    "h100", "gpu", "gpus", "pinecone", "spark", "airflow", "hadoop", "cuda",
    "rag", "retrieval-augmented", "fine-tun", "finetun", "genai", "llm",
    "llms", "mlops", "ci/cd",
}
_JD_RE = {t: re.compile(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])") for t in JD_ONLY_TECH}
ALLOWED_NUMBERS = {"40", "30"}          # from VERIFIED_METRICS
UNITS = {"%", "percent", "hours", "hour", "hrs", "hr"}

STRONG_VERBS = {
    "built", "engineered", "deployed", "optimized", "refactored", "led",
    "automated", "designed", "reduced", "cut", "accelerated", "delivered",
    "migrated", "implemented", "developed", "streamlined", "consolidated",
    "standardized", "analyzed", "cleaned", "presented", "created",
    "improved", "partnered", "collaborated", "reworked", "processed",
    "architected", "instrumented", "scaled", "eliminated", "validated",
}
VAGUE_VERBS = ("worked on", "responsible for", "strategized", "pioneered",
               "helped with", "assisted with", "was involved in",
               "participated in", "handled")


def _words(s: str) -> int:
    return len(re.findall(r"\b[\w'%.-]+\b", s))


def _numbers_in(text: str) -> list[tuple[str, str]]:
    """(value, trailing-context) for each number, to check unit retention."""
    out = []
    for m in re.finditer(r"(?<!\w)(\d[\d,]*\.?\d*)([^\d]{0,14})", text):
        val = m.group(1).replace(",", "")
        out.append((val, m.group(2).lower()))
    return out


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of a possibly-fenced response."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    start = t.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def score_response(text: str, experiences=None, verified_metrics=None) -> dict:
    exps = experiences or FIXTURE_EXPERIENCES
    vmetrics = verified_metrics or VERIFIED_METRICS
    allowed_nums = {m["value"] for m in vmetrics}

    parsed = extract_json(text)
    bullets: list[str] = []
    companies_out: list[str] = []
    schema_ok = False
    if parsed and isinstance(parsed.get("rewritten_experiences"), list):
        schema_ok = True
        for e in parsed["rewritten_experiences"]:
            if isinstance(e, dict):
                if e.get("company"):
                    companies_out.append(str(e["company"]))
                for b in (e.get("bullets") or []):
                    bullets.append(str(b))
    else:
        bullets = [ln.strip("-•* ").strip()
                   for ln in text.splitlines() if ln.strip().startswith(("-", "•", "*"))]

    # Scan ONLY the bullet content, not the whole JSON blob. The model also
    # emits metadata such as "quantification_score": 0.33 and a style rationale;
    # scanning the raw text counted that 0.33 as a fabricated metric.
    scan = " \n".join(bullets)
    if parsed:
        for e in parsed.get("rewritten_experiences") or []:
            if isinstance(e, dict):
                scan += " " + " ".join(str(x) for x in (e.get("metrics_used") or []))
                scan += " " + str(e.get("style_transfer_rationale") or "")
    low = scan.lower()

    # ── fabrication: JD-only technologies named anywhere in the bullets ─────
    fab_tech = sorted({t for t, rx in _JD_RE.items() if rx.search(low)})
    # companies: any capitalised org-looking token not in the allowed set
    fab_companies = []
    for c in re.findall(r"\b([A-Z][A-Za-z&.\-]+(?:\s+[A-Z][A-Za-z&.\-]+){0,2})\b", scan):
        cl = c.lower().strip()
        if cl in ALLOWED_COMPANIES or any(a in cl for a in ALLOWED_COMPANIES):
            continue
        if cl in ("cogito", "metric", "noaa"):
            continue
        # ignore sentence-initial verbs and common non-org words
        if cl.split()[0] in STRONG_VERBS or cl in (
                "data", "scientist", "boeing", "defense", "space", "security"):
            continue
        if any(k in cl for k in ("inc", "llc", "corp", "ltd", "company")):
            fab_companies.append(c)

    # ── metric fidelity ────────────────────────────────────────────────────
    bad_numbers = []
    unit_stripped = []
    for val, tail in _numbers_in(scan):
        if val not in allowed_nums:
            bad_numbers.append(val)
        elif not any(u in tail for u in UNITS):
            unit_stripped.append(val)

    # ── format ─────────────────────────────────────────────────────────────
    lens = [_words(b) for b in bullets]
    in_band = sum(1 for n in lens if 15 <= n <= 25)
    starts_strong = sum(
        1 for b in bullets
        if b.split() and b.split()[0].lower().strip(",:") in STRONG_VERBS)
    vague = [b for b in bullets if any(v in b.lower() for v in VAGUE_VERBS)]

    # ── coverage ───────────────────────────────────────────────────────────
    src_companies = {e["company"].lower() for e in exps}
    cov = len({c.lower() for c in companies_out} & src_companies)

    n = max(len(bullets), 1)
    return {
        "schema_ok": schema_ok,
        "n_bullets": len(bullets),
        "fabricated_tech": fab_tech,
        "fabricated_company": fab_companies,
        "bad_numbers": sorted(set(bad_numbers)),
        "unit_stripped": sorted(set(unit_stripped)),
        "in_band_pct": round(in_band / n * 100, 1),
        "strong_start_pct": round(starts_strong / n * 100, 1),
        "vague_bullets": len(vague),
        "company_coverage": f"{cov}/{len(src_companies)}",
        "avg_words": round(sum(lens) / n, 1) if bullets else 0,
        "clean": bool(not fab_tech and not fab_companies
                      and not bad_numbers and not unit_stripped
                      and schema_ok and cov == len(src_companies)),
        "_bullets": bullets,
    }


def build_prompts(experiences=None, job_ad: str = JOB_AD,
                  verified_metrics=None) -> tuple[str, str]:
    """Reconstruct the drafter's system + user prompt faithfully.

    Simplified only in that the golden-bullet library and seniority verb tables
    are omitted (they vary per deployment); every TRUTH CONSTRAINT and the
    evidence boundary are preserved verbatim in substance.
    """
    exps = experiences or FIXTURE_EXPERIENCES
    vm = verified_metrics or VERIFIED_METRICS

    system = """You are an elite Technical Resume Writer. Rewrite the user's raw
notes into high-impact, metric-driven STAR bullets. You may NOT invent jobs or
change the employment history.

### STYLE TRANSFER RULES (MANDATORY):
1. Strong Verbs: use "Deployed," "Engineered," "Refactored," "Optimized," "Led,"
   "Built" - NOT "Strategized," "Pioneered," "Worked on".
2. NORMALIZE TERMINOLOGY ONLY: you MAY restate an activity the input already
   describes with a clearer term for the SAME activity. You may NOT add a tool,
   technology, platform or activity the input does not contain. "database work"
   does NOT license "Python and SQL" unless the input or verified skills say so.
3. Only Use Real Metrics: only include metrics that appear EXPLICITLY in the
   verified metrics list. Do NOT invent them.
4. One Thought Per Bullet. Keep bullets punchy (15-25 words max).
5. Front-Load the Impact: start with the result or a strong verb.

### TRUTH CONSTRAINTS (VIOLATION = FAILURE)
1. COMPANY NAMES: use ONLY the companies in the input:
   """ + json.dumps([e["company"] for e in exps]) + """
   Do NOT invent company names.
2. JOB TITLES: preserve the actual role hierarchy; do not promote.
3. TECHNOLOGY - EVIDENCE ONLY: use technologies named in the input. Listing
   PyTorch does not establish "analyzed deep learning model internals".
4. JD KEYWORD WEAVING - NO NEW CLAIMS: reuse JD vocabulary ONLY to relabel an
   activity the input already describes. Do NOT fabricate experiences to match
   JD requirements.
5. METRICS - EVIDENCE ONLY: use a number ONLY when it appears in the verified
   metrics list, and keep the value AND unit together (write "30 hours", never a
   bare "30"). A bullet without a metric is NOT a failure.
6. STRONG BULLETS REQUIRED: each bullet 15-25 words, starting with a strong verb.
7. DATE FORMAT: copy the EXACT start and end dates from the input Duration field.

BAD VS GOOD:
Weak: "Strategized deployment of models." (vague, passive)
Hallucinated (BAD): copying "Must have 5 years of Python" from the job ad as
"I have 5 years of Python". DO NOT DO THIS.

Output JSON schema:
{"rewritten_experiences": [{"company": "MUST MATCH INPUT EXACTLY",
 "role": "Original or Polished Title", "bullets": ["...", "..."],
 "metrics_used": ["<value> <unit>"], "style_transfer_rationale": "..."}],
 "seniority_applied": "...", "quantification_score": 0.0}
"""

    metrics_block = "\n".join(
        f"- {m['value']} {m['unit']} ({m['kind']})" for m in vm)

    user = f"""User Experiences (JSON) - THIS IS THE SOURCE OF TRUTH.
Each experience has a 'bullets' field with the ORIGINAL bullet content. Mine it
for metrics, technologies, action verbs and domain language.
DO NOT fabricate anything not in these descriptions.

{json.dumps(exps, indent=2)}

Target Job Description - FOR CONTEXT ONLY (DO NOT COPY):
{job_ad[:3000]}

=== EVIDENCE BOUNDARY ===
Research about this occupation is NOT evidence about this candidate. You may
align vocabulary with the job description, but you may never introduce a tool,
platform, method, credential, project or accomplishment that the User
Experiences above do not contain. If the job description asks for something the
candidate's material does not mention, leave it out.

=== VERIFIED METRICS (extracted from the candidate's own resume) ===
{metrics_block}

METRIC RULE (evidence only):
- Use a number ONLY when it appears in the verified list above and keep its
  value AND unit together (write "30 hours", never a bare "30").
- If a useful metric is missing, leave the bullet unquantified. NEVER estimate.
"""
    return system, user
