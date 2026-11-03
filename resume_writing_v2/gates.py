"""Hard gates for the v2 harness.

Rebuilt rather than copied. Two v4 gates were provably wrong:

  G10 (ATS readability) fired on 16 of the 17 gate-failing runs, mostly for the
  presence of pipe characters. v4's test was `resume_text.count("|") > 5`,
  which flags any markdown table AND any prose containing pipes. v2 tests for
  actual table STRUCTURE: a header row of 3+ pipe-delimited cells immediately
  followed by a separator line (`|---|---|`). Isolated pipes are ignored.

  G7 (first person) used the pattern `\\b(I|my|me|we)\\s+(built|...)` with no
  IGNORECASE flag against already-lowercased text, so the uppercase `I`
  alternative could never match and a whole class of violations was invisible.
  v2 matches on word boundaries with a case-insensitive, position-anchored
  check.

Every gate returns a record with an id, severity, pass flag and a message that
names the offending text — so a failure is always explainable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

# ── Verified candidate facts (the only things a resume may claim) ──────────
VERIFIED_EMPLOYERS = ["noaa", "naval research laboratory", "nrl", "washington state",
                      "cogito metric", "capstone"]
VERIFIED_DEGREES = ["b.s. data analytics", "b.s. physics", "a.a.s. computer science",
                    "bachelor"]
VERIFIED_CERTS = ["network security+", "security+", "comptia", "cybersecurity analyst",
                  "ecc", "data analytics"]
# Every entry MUST appear verbatim in task.CANDIDATE_PROFILE. `1000`, `4.0` and
# `2016` used to sit here and appear nowhere in the profile, so a model could
# invent that graduation year and be CREDITED for it by the metrics score.
# test_scorers.py::test_verified_metrics_are_real now enforces the invariant.
VERIFIED_METRICS = ["263", "500k", "40%", "10+ tb", "13"]

FORBIDDEN_DEGREES = ["master", "phd", "ph.d", "doctorate", "m.s.", "mba", "m.eng", "m.sc"]
FORBIDDEN_EMPLOYERS = ["google", "microsoft", "amazon", "facebook", "meta",
                       "apple", "netflix", "openai", "anthropic"]
FORBIDDEN_CLEARANCE = ["top secret", "ts/sci", "secret clearance", "ts sci", "sci eligible"]

# ── Table STRUCTURE detection (replaces v4's naive pipe count) ─────────────
_SEP_ROW = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)+\|?\s*$")
_CELL_ROW = re.compile(r"^\s*\|?.*\|.*\|.*$")


@dataclass
class GateResult:
    id: str
    severity: str        # 'critical' | 'non_critical'
    passed: bool
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def _has_table_structure(text: str) -> bool:
    """True only for a real markdown table: header + separator row.

    A single pipe in prose, or a bullet containing 'a | b', is not a table.
    v4 counted raw '|' characters and called that a table.
    """
    lines = text.splitlines()
    for i in range(len(lines) - 1):
        head, sep = lines[i], lines[i + 1]
        if not _CELL_ROW.match(head):
            continue
        if not _SEP_ROW.match(sep):
            continue
        cells = [c for c in re.split(r"\|", head.strip().strip("|")) if c.strip()]
        if len(cells) >= 3:
            return True
    return False


def check_gates(resume_text: str) -> dict:
    """Run every gate. Returns a dict with per-gate results and a verdict."""
    text = resume_text or ""
    lower = text.lower()
    results: list[GateResult] = []

    def add(gid, ok, msg, critical=True):
        results.append(GateResult(
            gid, "critical" if critical else "non_critical", bool(ok), msg))

    # G1 — no invented facts
    bad_deg = [d for d in FORBIDDEN_DEGREES if d in lower]
    bad_emp = [e for e in FORBIDDEN_EMPLOYERS if e in lower]
    bad_clr = [c for c in FORBIDDEN_CLEARANCE if c in lower]
    invented = bad_deg + bad_emp + bad_clr
    add("G1", not invented,
        "no invented credentials" if not invented
        else f"invented: degrees={bad_deg} employers={bad_emp} clearance={bad_clr}")

    # G2 — degree integrity: FABRICATION is critical, OMISSION is not.
    # Caught in the first live run: GLM-5.3-Flash was disqualified for
    # `claimed=[]` — it simply left education out of the resume. A missing
    # section is a quality problem (see G5), not a fabrication. Only an
    # unverified degree claim may disqualify.
    claimed = [d for d in VERIFIED_DEGREES if d in lower]
    add("G2", not bad_deg,
        f"degrees claimed={claimed}" if not bad_deg and claimed
        else ("no degree claimed (not disqualifying)" if not bad_deg
              else f"unverified degrees={bad_deg}"),
        critical=bool(bad_deg))

    # G3 — identity integrity
    has_name = "jeff calderon" in lower
    has_entity = "cogito metric" in lower or "c2c" in lower
    has_citizen = "u.s. citizen" in lower or "us citizen" in lower
    add("G3", has_name and (has_entity or has_citizen),
        "identity intact" if (has_name and (has_entity or has_citizen))
        else f"missing name={not has_name} entity={not has_entity} citizen={not has_citizen}")

    # G4 — output is the resume only
    has_fence = "```" in text
    preamble = any(x in lower[:200] for x in
                   ("here is", "i've written", "below is", "certainly", "sure!"))
    add("G4", not has_fence and not preamble,
        "clean output" if not (has_fence or preamble)
        else f"non-resume output: fence={has_fence} preamble={preamble}")

    # G5 — required sections
    has_exp = any(x in lower for x in ("professional experience", "work experience"))
    has_proj = "project" in lower
    has_edu = "education" in lower
    add("G5", has_exp and has_proj and has_edu,
        "sections present" if (has_exp and has_proj and has_edu)
        else f"missing experience={not has_exp} projects={not has_proj} education={not has_edu}",
        critical=False)

    # G6 — word band
    wc = len(text.split())
    from .config import WORD_MIN, WORD_MAX
    add("G6", WORD_MIN <= wc <= WORD_MAX,
        f"{wc} words" if WORD_MIN <= wc <= WORD_MAX
        else f"{wc} words outside {WORD_MIN}-{WORD_MAX}", critical=False)

    # G7 — no first-person in bullets (case-insensitive, position anchored)
    # v4 compiled the uppercase `I` into a pattern applied to lowercased text,
    # so it could never fire.
    first_person = []
    for line in text.splitlines():
        s = line.strip().lstrip("-•*▪◦ \t")
        if not s:
            continue
        if re.match(r"^(I|I'm|I've|My|We|Our)\b", s, re.IGNORECASE) and \
           re.match(r"^[A-Z]", s):
            first_person.append(s[:60])
    add("G7", not first_person,
        "no first-person bullets" if not first_person
        else f"first-person: {first_person[:3]}", critical=False)

    # G8 — contractor signal
    has_c2c = "c2c" in lower or "cogito metric" in lower
    add("G8", has_c2c, "C2C present" if has_c2c else "missing C2C/Cogito Metric signal",
        critical=False)

    # G9 — target-role relevance
    relevant = any(x in lower for x in
                   ("boeing", "defense", "h100", "gpu cluster", "genai", "llm"))
    add("G9", relevant,
        "target relevance present" if relevant else "no Boeing/defense/GenAI relevance",
        critical=False)

    # G10 — ATS readability, table STRUCTURE aware
    table = _has_table_structure(text)
    deco = text.count("─") + text.count("═") + text.count("━")
    deco_bad = deco > 40          # sized to the document, not an absolute 20
    add("G10", not table and not deco_bad,
        "ATS-clean" if not (table or deco_bad)
        else f"table_structure={table} decorative_chars={deco}", critical=False)

    crit = [r for r in results if r.severity == "critical" and not r.passed]
    non = [r for r in results if r.severity == "non_critical" and not r.passed]
    return {
        "results": [r.to_dict() for r in results],
        "critical_fails": [r.id for r in crit],
        "non_critical_fails": [r.id for r in non],
        "disqualified": bool(crit),
        "all_passed": not crit and not non,
        "gates_passed": len(results) - len(crit) - len(non),
        "detail": {r.id: r.message for r in results if not r.passed},
    }
