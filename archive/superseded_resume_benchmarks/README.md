# Superseded resume-writing benchmarks

Moved here on 2026-11-02 because they are **not** the current harness and were
still sitting in the tree where they could be mistaken for it.

## Why they were superseded

Each generation had a defect that made its numbers untrustworthy. The current
harness (`../../resume_writing_v2/`) exists specifically to fix them:

| generation | defect |
|---|---|
| v2 / v3 | ad-hoc scoring, no gate clamp, no significance test, no trust check |
| v4 | declared weights summing to 100 that actually totalled **110**, then `min(total, 100)` silently compressed every score; 13 of 27 runs scored ≥90 while failing a gate |
| v4 | `G10` counted `|` characters, so prose pipes were flagged as markdown tables (16 of 17 gate failures) |
| v4 | `G7` compiled uppercase `I` against lowercased text without `IGNORECASE`, so it could never match |

`../../WRITING_PIPELINE_AUDIT.md` documents these in detail.

## What is still usable here

- `resume_parsing_*.py`, `resume_parse_compare.py`, `resume_quality_compare.py`
  are **parsing** benchmarks, a different question from writing, and were left in
  `LLM_comparisons/resume_writing/`.
- The v2/v3/v4 result JSONs are raw historical data. They are not comparable to
  `resume_writing_v2/results/` and must not be pooled with it: different scorer,
  different weights, no gate clamp.

## Do not use

Do not quote a score from any file in this folder as a current result. Current
results are in `../../resume_writing_v2/RESULTS.md`.
