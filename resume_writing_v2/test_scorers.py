#!/usr/bin/env python3
"""Self-tests for the deterministic scorers.

Two bugs of this exact class were found in earlier revisions (`rag` matching
inside `storage`; `quantification_score: 0.33` read as a fabricated metric).
Both were silent, and both would have been caught by a fixture that asserts the
scorer FIRES on a known-bad input and STAYS QUIET on a known-good one.

Run: python resume_writing_v2/test_scorers.py
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_writing_v2 import drafter_faithfulness as dfn

FAILS: list[str] = []


def check(cond: bool, label: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILS.append(label)


# ── fixtures ───────────────────────────────────────────────────────────────
GOOD_RESUME = """JEFF CALDERON
Marysville, WA | U.S. Citizen

PROFESSIONAL EXPERIENCE

Cogito Metric - Data Engineer    04/2024 - Present
- Built the resume parsing pipeline that processes incoming candidate resumes at scale.
- Reduced parsing step duration by 40% by refactoring the extraction and validation logic.

NOAA - Data Analyst    06/2021 - 03/2024
- Made weekly charts and reports for weather data used by the research team.
- Cleaned messy oceanographic datasets before analysis and delivered findings.

EDUCATION

B.S. Data Analytics, Washington State University    2015 - 2019
B.S. Physics, Washington State University    2013 - 2017
A.A.S. Computer Science, Bates Technical College    2011 - 2013

CERTIFICATIONS

CompTIA Security+ - CompTIA    03/2023
Cybersecurity Analyst - ECC    07/2022
Data Analytics Certificate - Coursera    11/2021
"""

# structure broken in several ways at once
BAD_STRUCTURE = """JEFF CALDERON

PROFESSIONAL EXPERIENCE

NOAA - Data Analyst    2021 - 2024
- Made charts for weather data.

Cogito Metric - Data Engineer    2024 - Present
- Built the parsing pipeline.

EDUCATION

B.S. Data Analytics, Washington State University    2018 - 2021

CERTIFICATIONS

CompTIA Security+    03/2023
"""

MARKDOWN_TABLE = """PROFESSIONAL EXPERIENCE
| Role | Company | Dates |
|---|---|---|
| Data Engineer | Cogito Metric | 04/2024 - Present |
| Data Analyst | NOAA | 06/2021 - 03/2024 |

EDUCATION
B.S. Data Analytics, Washington State University 2015 - 2019

CERTIFICATIONS
CompTIA Security+ 03/2023
"""


def _invariants() -> None:
    """Cross-module invariants: the allowlists must describe the real profile."""
    from resume_writing_v2 import gates, task

    print("\nInvariant: every 'verified' metric appears in the candidate profile")
    profile = task.CANDIDATE_PROFILE.lower()
    phantom = [m for m in gates.VERIFIED_METRICS if m not in profile]
    check(not phantom,
          f"no phantom verified metrics (found {phantom})" if phantom
          else "no phantom verified metrics")

    print("\nInvariant: the profile carries NO education or certification years")
    # An employment start year ("Cogito Metric (2024 - present)") is a real,
    # verified fact. What the profile must NOT contain is a graduation year or a
    # certificate issue date, because Test A has no gate that could detect a
    # model inventing one. Check the education and certification blocks only.
    edu = task.CANDIDATE_PROFILE.split("EDUCATION")[1].split("EXPERIENCE")[0]
    cert = task.CANDIDATE_PROFILE.split("CERTIFICATIONS")[1].split("EXPERIENCE")[0]
    edu_years = re.findall(r"\b(?:19|20)\d{2}\b", edu)
    cert_years = re.findall(r"\b(?:19|20)\d{2}\b", cert)
    check(not edu_years and not cert_years,
          "no graduation/cert years in the profile"
          if not (edu_years or cert_years)
          else f"profile leaks years: education={edu_years} certs={cert_years}")

    print("\nInvariant: Test B fixture years are flagged synthetic")
    import inspect
    from resume_writing_v2 import drafter_faithfulness as d
    src = inspect.getsource(d)
    check("SYNTHETIC TEST FIXTURE" in src,
          "FIXTURE_EDUCATION block carries a SYNTHETIC warning")


def main() -> int:
    print("date parsing")
    check(dfn.parse_date("04/2024") == (2024, 4), "04/2024 -> (2024, 4)")
    check(dfn.parse_date("Present") == "present", "Present -> 'present'")
    check(dfn.parse_date("Apr 2024") == (2024, 4), "Apr 2024 -> (2024, 4)")
    check(dfn.parse_date("2024") == (2024, None), "2024 -> (2024, None)")
    check(dfn.parse_date("garbage") is None, "garbage -> None")
    check(dfn.parse_range("04/2024 - Present") == ((2024, 4), "present"),
          "range with Present")
    check(dfn.parse_range("06/2021 - 03/2024") == ((2021, 6), (2024, 3)),
          "range both ends")

    print("\ndate equality")
    check(dfn._date_eq((2024, 4), (2024, 4)), "identical")
    check(not dfn._date_eq((2024, 4), (2024, 5)), "different month fails")
    check(not dfn._date_eq((2024, None), (2024, 4)),
          "dropped month is a FAILURE (prompt requires exact copy)")
    check(not dfn._date_eq((2023, 4), (2024, 4)), "different year fails")

    print("\nstructure: known-good resume")
    s = dfn.score_structure(GOOD_RESUME)
    check(not s["missing_sections"], "all three sections found")
    check(s["order_ok"] is True, "reverse-chronological order detected")
    check(s["dates_ok"], "experience dates exact")
    check(s["education_ok"], "education years exact")
    check(s["certs_ok"], "cert dates exact")
    check(s["formatting_ok"], "no markdown table / fence")
    check(s["structural_clean"], "overall structural_clean")

    print("\nstructure: known-bad resume must FAIL")
    b = dfn.score_structure(BAD_STRUCTURE)
    check(b["order_ok"] is False, "chronology inversion caught")
    check(not b["dates_ok"], "missing months / wrong years caught")
    check(not b["education_ok"], "invented graduation year caught")
    check(any(r["invented_years"] for r in b["education_detail"]),
          "invented year recorded explicitly")
    check(not b["certs_ok"], "missing cert row caught")
    check(not b["structural_clean"], "overall clean is False")

    print("\nstructure: markdown table must FAIL formatting")
    m = dfn.score_structure(MARKDOWN_TABLE)
    check(m["has_markdown_table"], "table structure detected")
    check(not m["formatting_ok"], "formatting_ok is False")

    print("\nfabrication: technology")
    fab = dfn.score_response(
        '{"rewritten_experiences":[{"company":"Cogito Metric","bullets":'
        '["Deployed Docker and Kubernetes clusters for the parsing pipeline."]}]}')
    check("docker" in fab["fabricated_tech"], "Docker flagged")
    check("kubernetes" in fab["fabricated_tech"], "Kubernetes flagged")

    print("\nfabrication: word-boundary regression (the 'storage' bug)")
    ok = dfn.score_response(
        '{"rewritten_experiences":[{"company":"Cogito Metric","bullets":'
        '["Worked with Postgres and Python for the storage layer of the platform."]}]}')
    check("rag" not in ok["fabricated_tech"],
          "'rag' inside 'storage' is NOT flagged")

    print("\nmetric fidelity")
    bad = dfn.score_response(
        '{"rewritten_experiences":[{"company":"Cogito Metric","bullets":'
        '["Reduced latency by 65% across the pipeline."]}]}')
    check("65" in bad["bad_numbers"], "unverified 65 flagged")
    strip = dfn.score_response(
        '{"rewritten_experiences":[{"company":"Cogito Metric","bullets":'
        '["Automated the weekly report over 30 consecutive cycles without error."]}]}')
    check("30" in strip["unit_stripped"], "bare 30 without 'hours' flagged")

    print("\nplain-text mode (full-resume variant)")
    pt = dfn.score_response(GOOD_RESUME, plain_text=True)
    check(pt["schema_ok"], "plain text does not require JSON")
    check(pt["company_coverage"] == "2/2", "companies found by search")
    check(pt["clean"], "good plain-text resume is faithfulness-clean")
    ptb = dfn.score_response(BAD_STRUCTURE, plain_text=True)
    check(ptb["clean"],
          "bad-STRUCTURE resume is still factually clean (failure is structural)")
    ptf = dfn.score_response(
        GOOD_RESUME.replace("candidate resumes", "candidate resumes on Kubernetes"),
        plain_text=True)
    check("kubernetes" in ptf["fabricated_tech"],
          "plain-text mode still catches fabricated tech")
    jsonmode = dfn.score_response(GOOD_RESUME)
    check(not jsonmode["schema_ok"],
          "JSON mode rejects a plain resume (guard against silent pass)")

    print("\nlayout variants must all pass (dates above / below, unmarked bullets)")
    ABOVE = """PROFESSIONAL EXPERIENCE
04/2024 - Present
Data Engineer
Cogito Metric
Built the resume parsing pipeline that processes incoming candidate resumes daily
Reduced how long the parsing step takes by about 40% after reworking it completely

06/2021 - 03/2024
Data Analyst
NOAA
Made charts and reports for weather data on a weekly cadence for the team
Cleaned messy oceanographic datasets before analysis and verified the results

EDUCATION
2015 - 2019
B.S. Data Analytics
Washington State University
2013 - 2017
B.S. Physics
Washington State University
2011 - 2013
A.A.S. Computer Science
Bates Technical College

CERTIFICATIONS
03/2023
CompTIA Security+
07/2022
Cybersecurity Analyst
11/2021
Data Analytics Certificate
"""
    ab = dfn.score_structure(ABOVE)
    check(ab["dates_ok"], "dates ABOVE the company line are found")
    check(ab["education_ok"], "years ABOVE the credential line are found")
    check(ab["certs_ok"], "cert dates ABOVE the name are found")
    check(ab["structural_clean"], "date-above layout is structurally clean")

    pt_above = dfn.score_response(ABOVE, plain_text=True)
    check(pt_above["n_bullets"] >= 4,
          "unmarked bullets are extracted (not 0)")
    check(pt_above["clean"], "date-above layout is faithfulness-clean")

    print("\neducation rows must not borrow each other's years")
    two_rows = ("PROFESSIONAL EXPERIENCE\nCogito Metric 04/2024 - Present\n"
                "Built the resume parsing pipeline that processes candidate "
                "resumes at scale today now.\n\nEDUCATION\n"
                "B.S. Data Analytics, Washington State University 2015 - 2019\n"
                "B.S. Physics, Washington State University 2013 - 2017\n"
                "A.A.S. Computer Science, Bates Technical College 2011 - 2013\n"
                "\nCERTIFICATIONS\nCompTIA Security+ 03/2023\n")
    tr = dfn.score_structure(two_rows)
    check(tr["education_ok"],
          "adjacent credential rows keep their own year ranges")
    check(not any(r["invented_years"] for r in tr["education_detail"]),
          "no invented years from a neighbouring row")

    print("\nmetadata must not be read as a metric (the 0.33 bug)")
    meta = dfn.score_response(
        '{"rewritten_experiences":[{"company":"Cogito Metric","bullets":'
        '["Built the parsing pipeline."],"metrics_used":[],'
        '"style_transfer_rationale":"strong verb"}},"quantification_score":0.33}')
    check("0.33" not in meta["bad_numbers"],
          "quantification_score 0.33 not counted as a metric")

    print("\ndates must not be read as fabricated metrics")
    dates_only = ("PROFESSIONAL EXPERIENCE\nCogito Metric\n04/2024 - Present\n"
                  "- Built the resume parsing pipeline that processes incoming "
                  "candidate resumes today.\n\nEDUCATION\nB.S. Data Analytics, "
                  "Washington State University 2015 - 2019\n\nCERTIFICATIONS\n"
                  "CompTIA Security+ 03/2023\n")
    dd = dfn.score_response(dates_only, plain_text=True)
    check(dd["bad_numbers"] == [],
          "04/2024, 2015, 03/2023 are not fabricated metrics")
    check(dd["unit_stripped"] == [],
          "dates do not trigger the unit-stripped check")

    _invariants()

    print("\n" + "=" * 60)
    if FAILS:
        print(f"{len(FAILS)} FAILURE(S):")
        for f in FAILS:
            print("  -", f)
        return 1
    print("all scorer self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
