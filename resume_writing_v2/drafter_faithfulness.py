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

# ── Full-resume fixture (structure test) ───────────────────────────────────
# !! SYNTHETIC TEST FIXTURE — NOT CANDIDATE DATA !!
#
# The school years and certificate dates below are INVENTED for this test. They
# exist only so "did the model copy the year exactly?" is measurable; without a
# source year there is nothing to copy.
#
# They are NOT claims about Jeff Calderon. The production profile in task.py
# deliberately omits graduation and certification years, and a real resume must
# always take those dates from the candidate's uploaded source documents.
#
# WHY THEY MUST NEVER REACH USER-FACING OUTPUT:
#   1. A fabricated graduation year in a resume sent to an employer is a
#      misrepresentation. It is materially different from a missing year, which
#      is merely incomplete.
#   2. Education and certification years are identity-adjacent claims. Inventing
#      one is indistinguishable from inventing a degree.
#   3. Test A has NO gate that detects an invented year (G1-G4 check employers,
#      degrees and clearance only), so nothing downstream would catch a leak.
#   4. These specific values exist only in a scorer fixture and were never
#      verified against any document. Tracing them back to a real source is
#      impossible by construction.
#
# If a future change makes the harness copy FIXTURE_EDUCATION or
# FIXTURE_CERTIFICATIONS into a prompt for real users, that is a defect, not a
# configuration choice.
FIXTURE_EDUCATION = [
    {"school": "Washington State University",
     "credential": "B.S. Data Analytics", "years": "2015 - 2019"},
    {"school": "Washington State University",
     "credential": "B.S. Physics", "years": "2013 - 2017"},
    {"school": "Bates Technical College",
     "credential": "A.A.S. Computer Science", "years": "2011 - 2013"},
]

FIXTURE_CERTIFICATIONS = [
    {"name": "CompTIA Security+", "issuer": "CompTIA", "date": "03/2023"},
    {"name": "Cybersecurity Analyst", "issuer": "ECC", "date": "07/2022"},
    {"name": "Data Analytics Certificate", "issuer": "Coursera", "date": "11/2021"},
]

REQUIRED_SECTIONS = ("experience", "education", "certifications")

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_PRESENT = {"present", "current", "now", "ongoing", "today", "date"}


def parse_date(s):
    """Normalise one date to (year, month|None), or 'present'.

    Accepts 04/2024, 2024-04, Apr 2024, April 2024, 2024, Present. Returns None
    when nothing parseable is found, so a wrong format is a failure rather than
    a silent pass.
    """
    if s is None:
        return None
    t = str(s).strip().lower()
    if not t:
        return None
    # a bare "Present" with a stray word such as "Present (remote)"
    for p in _PRESENT:
        if t == p or t.startswith(p + " ") or t.startswith(p + "("):
            return "present"
    # 04/2024 or 4/2024 or 2024/04
    m = re.search(r"\b(0?[1-9]|1[0-2])\s*[/.-]\s*(\d{4})\b", t)
    if m:
        return (int(m.group(2)), int(m.group(1)))
    m = re.search(r"\b(\d{4})\s*[/.-]\s*(0?[1-9]|1[0-2])\b", t)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    # Apr 2024 / April 2024
    m = re.search(r"\b([a-z]{3,9})\.?\s*,?\s*(\d{4})\b", t)
    if m and m.group(1) in _MONTHS:
        return (int(m.group(2)), _MONTHS[m.group(1)])
    # bare year
    m = re.search(r"\b(19|20)\d{2}\b", t)
    if m:
        return (int(m.group(0)), None)
    return None


def parse_range(s):
    """Split a duration string into (start, end). Handles '-', '–', 'to'."""
    if s is None:
        return (None, None)
    t = str(s).strip()
    parts = re.split(r"\s*(?:-|–|—|\bto\b)\s*", t, maxsplit=1)
    if len(parts) == 1:
        return (parse_date(parts[0]), None)
    return (parse_date(parts[0]), parse_date(parts[1]))


def _date_eq(a, b) -> bool:
    """Exact date comparison. A dropped month is a FAILURE, not a nuance.

    The prompt says to copy employment dates exactly, including the month. An
    earlier version tolerated a missing month on either side, which let
    '2021 - 2024' pass for a source of '06/2021 - 03/2024' — precisely the
    silent-pass bug these self-tests exist to catch.
    """
    if a is None or b is None:
        return False
    return a == b


def _context(text: str, pos: int, before: int = 1, after: int = 3) -> str:
    """Text from `before` lines up to `after` lines down, around `pos`.

    Models place dates above the company (`04/2024 - Present` / `Data Engineer`
    / `Cogito Metric`) as often as below it. Searching only forward failed a
    correct resume for its layout, which is not a truth or format error.
    """
    lines = text.splitlines()
    # locate the line index containing pos
    count = 0
    idx = 0
    for i, ln in enumerate(lines):
        nxt = count + len(ln) + 1
        if pos < nxt:
            idx = i
            break
        count = nxt
    lo = max(0, idx - before)
    hi = min(len(lines), idx + after + 1)
    return " ".join(lines[lo:hi])


def _line_index_at(text: str, pos: int) -> int:
    lines = text.splitlines()
    count = 0
    for i, ln in enumerate(lines):
        nxt = count + len(ln) + 1
        if pos < nxt:
            return i
        count = nxt
    return max(0, len(lines) - 1)


def _nearest_lines(text: str, pos: int,
                   offsets=(0, 1, -1, 2, -2)) -> list[str]:
    """Single lines around `pos`, nearest first, WITHOUT concatenating them.

    A concatenated window bleeds into the neighbouring entry — two education
    rows borrowed each other's graduation years and both were reported as
    invented. Callers take the first line that contains what they are looking
    for, which is order-independent and cannot borrow from a sibling.
    """
    lines = text.splitlines()
    idx = _line_index_at(text, pos)
    out = []
    for off in offsets:
        j = idx + off
        if 0 <= j < len(lines):
            out.append(lines[j])
    return out


def _dates_by_distance(text: str, pos: int, pattern: str,
                       max_distance: int = 3) -> list[str]:
    """Date-like matches from the CLOSEST line(s) that contain any.

    Checks both directions at each distance and stops at the first distance
    that yields a match. This is order-independent, which matters because the
    three common layouts put the date on the same line, above the label, or
    below it:

        Data Engineer, Cogito Metric — 04/2024 - Present     (same line)
        04/2024 - Present / Data Engineer / Cogito Metric    (above)
        Cogito Metric / Data Engineer / 04/2024 - Present    (below)

    Using a fixed preference (above-first) made every certificate in the
    below-layout borrow the PRECEDING certificate's date.
    """
    lines = text.splitlines()
    idx = _line_index_at(text, pos)
    for d in range(0, max_distance + 1):
        cands = []
        for j in ({idx} if d == 0 else {idx - d, idx + d}):
            if 0 <= j < len(lines):
                cands.extend(re.findall(pattern, lines[j], re.IGNORECASE))
        if cands:
            return cands
    return []


def _line_at(text: str, pos: int) -> str:
    """The single line containing `pos`, truncated at both newlines.

    Windows measured in CHARACTERS spill from one credential line into the
    next, which made two B.S. rows borrow each other's graduation years and
    report both as invented. Scope to the line instead.
    """
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    if end < 0:
        end = len(text)
    return text[start:end]

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


_DATE_TOKEN = re.compile(
    r"\b(?:0?[1-9]|1[0-2])/\d{4}\b|\b(?:19|20)\d{2}\b")


def _numbers_in(text: str) -> list[tuple[str, str]]:
    """(value, trailing-context) for each number, to check unit retention.

    Dates are removed first. '04/2024' contains a bare 4 and a bare 2024, both
    of which were reported as FABRICATED METRICS — a resume that copied its
    dates correctly was being penalised for it. Metrics and dates are different
    contracts and must not share a scanner.
    """
    text = _DATE_TOKEN.sub(" ", text)
    out = []
    for m in re.finditer(r"(?<!\w)(\d[\d,]*\.?\d*)([^\d]{0,14})", text):
        val = m.group(1).replace(",", "").rstrip(".")
        if val in ("", "."):
            continue
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


def score_structure(text: str, experiences=None, education=None,
                    certifications=None) -> dict:
    """Score the STRUCTURAL contract of a full resume.

    Six checks, each independent and each reported separately, because "the
    resume is bad" is not actionable but "the dates were right and the order was
    reversed" is:

      1. sections     required headings present (experience/education/certs)
      2. order        experience entries in reverse-chronological order
      3. dates        every experience duration copied EXACTLY from source
      4. education    school years copied exactly, and no invented years
      5. certs        certification dates copied exactly
      6. formatting   plain text, no markdown pipes/tables, ATS-parseable

    Nothing here judges prose. A beautifully written resume with an invented
    graduation year fails, which is the correct outcome.
    """
    exps = experiences or FIXTURE_EXPERIENCES
    edu = education or FIXTURE_EDUCATION
    certs = certifications or FIXTURE_CERTIFICATIONS

    low = text.lower()

    # ── 1. required sections ───────────────────────────────────────────────
    sec_patterns = {
        "experience": r"\b(professional\s+)?experience\b|\bwork\s+history\b|\bemployment\b",
        "education": r"\beducation\b|\bacademic\b",
        "certifications": r"\bcertificat|\bcertifications?\b|\blicen[sc]es?\b",
    }
    sections_found = {k: bool(re.search(v, low))
                      for k, v in sec_patterns.items()}
    missing_sections = [k for k, v in sections_found.items() if not v]

    # ── 2. reverse-chronological order ─────────────────────────────────────
    # Locate each source company in the output and record its position. The
    # input is already reverse-chronological, so the positions must ascend.
    positions = []
    for e in exps:
        rx = re.compile(re.escape(e["company"].lower()))
        m = rx.search(low)
        positions.append((e["company"], m.start() if m else None))
    found_pos = [(c, p) for c, p in positions if p is not None]
    order_ok = None
    if len(found_pos) >= 2:
        order_ok = all(found_pos[i][1] < found_pos[i + 1][1]
                       for i in range(len(found_pos) - 1))
    order_note = ""
    if order_ok is False:
        order_note = ("expected " + " -> ".join(c for c, _ in found_pos)
                      + " (input is reverse-chronological)")

    # ── 3. experience dates ────────────────────────────────────────────────
    date_results = []
    for e in exps:
        src_start, src_end = parse_range(e.get("duration"))
        # find the company, then look for a date range within 220 chars after
        m = re.search(re.escape(e["company"]), text, re.IGNORECASE)
        # Dates may sit on the company line, above it, or below it. Take the
        # NEAREST single line that holds a date range, so a sibling entry's
        # dates are never borrowed.
        found, got_start, got_end = [], None, None
        if m:
            found = _dates_by_distance(
                text, m.start(),
                r"(?:0?[1-9]|1[0-2])\s*[/.-]\s*\d{4}"
                r"|[A-Za-z]{3,9}\.?\s+\d{4}|\b(?:19|20)\d{2}\b"
                r"|\b(?:Present|Current|Now)\b", max_distance=3)
            parsed = [parse_date(f) for f in found]
            got_start = parsed[0] if parsed else None
            got_end = parsed[1] if len(parsed) > 1 else None
        start_ok = _date_eq(got_start, src_start)
        end_ok = _date_eq(got_end, src_end)
        date_results.append({
            "company": e["company"],
            "source": e.get("duration"),
            "found": found[:2],
            "start_ok": start_ok,
            "end_ok": end_ok,
        })
    dates_ok = all(d["start_ok"] and d["end_ok"] for d in date_results)

    # ── 4. education years ─────────────────────────────────────────────────
    edu_results = []
    for ed in edu:
        school = ed["school"].lower()
        cred = ed["credential"].lower()
        # locate the credential line, since WSU appears twice
        pos = None
        for needle in (cred, school):
            mm = low.find(needle)
            if mm >= 0:
                pos = mm
                break
        want = re.findall(r"\b(?:19|20)\d{2}\b", ed["years"])
        # Take the NEAREST line that contains at least two years (a range), so
        # two adjacent credentials cannot share a year list.
        found_years: list[str] = []
        if pos is not None:
            for ln in _nearest_lines(text, pos):
                stamped = re.findall(r"\b(?:19|20)\d{2}\b", ln)
                if len(stamped) >= 2:
                    found_years = stamped
                    break
        exact = [y for y in want if y in found_years]
        invented = [y for y in found_years if y not in want]
        edu_results.append({
            "credential": ed["credential"],
            "source_years": ed["years"],
            "found_years": found_years[:4],
            "years_ok": len(exact) == len(want) and not invented,
            "invented_years": invented,
        })
    education_ok = all(r["years_ok"] for r in edu_results)

    # ── 5. certification dates ─────────────────────────────────────────────
    cert_results = []
    for c in certs:
        pos = low.find(c["name"].lower())
        # The cert date may precede the name. Take the nearest single line
        # holding a date, and stop looking once one is found.
        found: list[str] = []
        if pos >= 0:
            found = _dates_by_distance(
                text, pos,
                r"(?:0?[1-9]|1[0-2])\s*[/.-]\s*\d{4}"
                r"|\b[A-Za-z]{3,9}\.?\s+\d{4}|\b(?:19|20)\d{2}\b",
                max_distance=2)
        want = parse_date(c["date"])
        ok = any(_date_eq(parse_date(f), want) for f in found)
        cert_results.append({"name": c["name"], "source": c["date"],
                             "found": found[:2], "date_ok": ok})
    certs_ok = all(r["date_ok"] for r in cert_results)

    # ── 6. formatting / ATS-parseability ───────────────────────────────────
    pipes = text.count("|")
    # a real markdown table needs a separator row such as |---|---|
    has_table = bool(re.search(r"\|\s*:?-{2,}:?\s*\|", text))
    has_fence = "```" in text
    # two or more spaces between capitalised runs suggests column layout
    col_layout = bool(re.search(r"[A-Za-z]{3,}\s{3,}[A-Za-z]{3,}", text))
    formatting_ok = not has_table and not has_fence

    structural_clean = (not missing_sections and order_ok is not False
                        and dates_ok and education_ok and certs_ok
                        and formatting_ok)

    return {
        "missing_sections": missing_sections,
        "sections_found": sections_found,
        "order_ok": order_ok,
        "order_note": order_note,
        "dates_ok": dates_ok,
        "date_detail": date_results,
        "education_ok": education_ok,
        "education_detail": edu_results,
        "certs_ok": certs_ok,
        "cert_detail": cert_results,
        "formatting_ok": formatting_ok,
        "has_markdown_table": has_table,
        "has_code_fence": has_fence,
        "suspected_column_layout": col_layout,
        "pipe_count": pipes,
        "structural_clean": bool(structural_clean),
    }


_HEADING_RE = re.compile(
    r"^\s*(?:[A-Z][A-Z &/]+|PROFESSIONAL EXPERIENCE|WORK EXPERIENCE|"
    r"EDUCATION|CERTIFICATIONS|SKILLS|SUMMARY|PROJECTS)\s*:?\s*$")
_DATE_RANGE_RE = re.compile(
    r"(?:0?[1-9]|1[0-2])/\d{4}\s*(?:-|–|—|to)\s*(?:(?:0?[1-9]|1[0-2])/\d{4}|"
    r"present|current|now)", re.IGNORECASE)


_EXP_START_RE = re.compile(
    r"^\s*(?:PROFESSIONAL\s+EXPERIENCE|WORK\s+EXPERIENCE|EMPLOYMENT(?:\s+HISTORY)?"
    r"|EXPERIENCE)\s*:?\s*$", re.IGNORECASE)
_EXP_END_RE = re.compile(
    r"^\s*(?:EDUCATION|CERTIFICATIONS?|LICEN[SC]ES?|SKILLS|PROJECTS|SUMMARY"
    r"|AWARDS|PUBLICATIONS|TRAINING)\s*:?\s*$", re.IGNORECASE)


def _experience_block(text: str) -> str:
    """The text between the experience heading and the next section heading.

    Without this, education and certification lines were counted as bullets,
    which pushed in-band compliance to 0% for models that had in fact written
    correctly-sized bullets. Only experience bullets are measured.
    """
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if _EXP_START_RE.match(ln.strip()):
            start = i + 1
            break
    if start is None:
        return text
    end = len(lines)
    for j in range(start, len(lines)):
        if _EXP_END_RE.match(lines[j].strip()):
            end = j
            break
    return "\n".join(lines[start:end])


def _extract_bullets_plain(text: str, exps=None) -> tuple[list[str], str, bool]:
    """Extract bullet lines from a plain-text resume.

    Returns (bullets, how, one_per_line).

    Three shapes appear in practice and all must be handled, because returning
    an empty list makes a good resume look like a total format failure:

      1. marked     "- Built ..."          -> bullet char present
      2. unmarked   "Built ..."            -> no marker, but clearly a line each
      3. paragraph  "... . ... . ..."      -> several sentences on one line

    `one_per_line` is False for shape 3, which IS a real prompt-compliance
    failure (the contract says one thought per bullet) but must be reported as
    that, not as "zero bullets".
    """
    exps = exps or FIXTURE_EXPERIENCES
    companies = {e["company"].lower() for e in exps}
    text = _experience_block(text)
    lines = [ln.rstrip() for ln in text.splitlines()]

    marked = [ln.strip().lstrip("-•*·").strip() for ln in lines
              if ln.strip().startswith(("-", "•", "*", "·"))]
    if marked:
        return marked, "marked", True

    bullets: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if _HEADING_RE.match(s):
            continue
        if _DATE_RANGE_RE.search(s):
            continue
        low = s.lower()
        # company / role lines carry no verb and are short
        if any(c in low for c in companies) and len(s.split()) <= 6:
            continue
        if len(s.split()) < 4:
            continue
        bullets.append(s)

    if not bullets:
        return [], "none", False

    # shape 3: one long line holding many sentences
    one_per_line = not any(len(b.split()) > 45 for b in bullets)
    expanded: list[str] = []
    for b in bullets:
        if len(b.split()) > 45:                       # paragraph-shaped
            parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", b)
            expanded.extend(p.strip() for p in parts if len(p.split()) >= 4)
        else:
            expanded.append(b)
    return expanded, "unmarked", one_per_line


def score_response(text: str, experiences=None, verified_metrics=None,
                   plain_text: bool = False) -> dict:
    """Score faithfulness.

    `plain_text=True` is for the FULL-RESUME variant, where the model emits a
    resume document rather than JSON. Without this flag every such response
    failed `schema_ok` and scored `company_coverage 0/2`, so `clean` was always
    False — a scorer bug that would have looked like 43 models fabricating.
    In plain-text mode JSON is not required and companies are found by search.
    """
    exps = experiences or FIXTURE_EXPERIENCES
    vmetrics = verified_metrics or VERIFIED_METRICS
    allowed_nums = {m["value"] for m in vmetrics}

    parsed = None if plain_text else extract_json(text)
    bullets: list[str] = []
    companies_out: list[str] = []
    schema_ok = False
    how, one_per_line = "json", True
    if parsed and isinstance(parsed.get("rewritten_experiences"), list):
        schema_ok = True
        for e in parsed["rewritten_experiences"]:
            if isinstance(e, dict):
                if e.get("company"):
                    companies_out.append(str(e["company"]))
                for b in (e.get("bullets") or []):
                    bullets.append(str(b))
    elif plain_text:
        # JSON is not part of this contract; bullets are the "- " lines.
        schema_ok = True
        bullets, how, one_per_line = _extract_bullets_plain(text, exps)
        for e in exps:
            if re.search(re.escape(e["company"]), text, re.IGNORECASE):
                companies_out.append(e["company"])
    else:
        bullets = [ln.strip("-•* ").strip()
                   for ln in text.splitlines() if ln.strip().startswith(("-", "•", "*"))]
        how, one_per_line = "marked", True

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
        "bullet_style": how,
        "one_thought_per_line": one_per_line,
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


# ── Full-resume test (structure + faithfulness together) ───────────────────
def build_resume_prompts(experiences=None, education=None, certifications=None,
                         job_ad: str = JOB_AD,
                         verified_metrics=None) -> tuple[str, str]:
    """System + user prompt for the FULL-RESUME variant of Test B.

    Difference from `build_prompts`: that one asks for JSON bullets only. This
    one asks for a complete plain-text resume and makes the structural contract
    explicit, so a failure is a prompt-compliance failure rather than an
    unstated expectation.
    """
    exps = experiences or FIXTURE_EXPERIENCES
    edu = education or FIXTURE_EDUCATION
    certs = certifications or FIXTURE_CERTIFICATIONS
    vm = verified_metrics or VERIFIED_METRICS

    system = """You are an expert ATS-optimized resume writer producing a complete,
plain-text resume for a technical role.

### OUTPUT FORMAT (MANDATORY)
- Plain text ONLY. No markdown, no tables, no pipe characters, no code fences,
  no commentary before or after the resume.
- Use these three section headings, spelled exactly:
    PROFESSIONAL EXPERIENCE
    EDUCATION
    CERTIFICATIONS

### STRUCTURE (MANDATORY)
1. EXPERIENCE: every job from the input, in REVERSE-CHRONOLOGICAL order (most
   recent first). Do not reorder, merge, or drop a job.
2. DATES: copy the employment dates EXACTLY from the input Duration field,
   including month and year ("04/2024 - Present"). Do not reformat, round, or
   omit the month.
3. EDUCATION: one line per credential, copied exactly from the input, including
   the school and the year range exactly as given ("2015 - 2019"). Do NOT invent
   or adjust a graduation year.
4. CERTIFICATIONS: one line per certificate with the exact issue date from the
   input ("03/2023"). Do not invent a date.
5. Each job gets 2-4 bullets.

### TRUTH CONSTRAINTS (VIOLATION = FAILURE)
1. COMPANIES: use ONLY these companies, spelled exactly:
   """ + json.dumps([e["company"] for e in exps]) + """
2. JOB TITLES: keep the real role hierarchy; do not promote.
3. TECHNOLOGY - EVIDENCE ONLY: name only technologies present in the input.
   A technology that appears only in the job description is NOT evidence.
4. METRICS - EVIDENCE ONLY: use a number only when it is in the verified metrics
   list, and keep its unit attached. A bullet without a metric is not a failure.
5. No invented employers, schools, credentials, clearance, or awards.

### STYLE (MANDATORY)
- Each bullet 15-25 words, starting with a strong action verb ("Built",
  "Engineered", "Reduced", "Refactored"). Not "Worked on" or "Responsible for".
"""

    metrics_block = "\n".join(
        f"- {m['value']} {m['unit']} ({m['kind']})" for m in vm)

    user = f"""SOURCE OF TRUTH — the candidate's real history. Use NOTHING outside this.

EXPERIENCE:
{json.dumps(exps, indent=2)}

EDUCATION (copy these years exactly):
{json.dumps(edu, indent=2)}

CERTIFICATIONS (copy these dates exactly):
{json.dumps(certs, indent=2)}

VERIFIED METRICS (the ONLY numbers you may use):
{metrics_block}

TARGET JOB DESCRIPTION — context only, never an evidence source:
{job_ad[:2000]}

Write the complete resume now, with the three required section headings and
every date copied exactly from the source above.
"""
    return system, user
