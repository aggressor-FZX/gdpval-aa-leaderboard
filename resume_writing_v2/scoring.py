"""Weighted scoring for the v2 harness — gate-clamped, sums to exactly 100.

The two structural fixes over v4:

1. WEIGHTS sum to 100 (v4 summed to 110 then clipped, compressing all scores).
2. The gate verdict CLAMPS the score. In v4, 13 of 27 runs scored >=90 while
   failing a gate, because the gate layer and the score layer were independent.
   Here a critical failure caps at 69 and a non-critical failure caps at 89, so
   a high score and a failed gate can no longer coexist.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config import (WEIGHTS, CRITICAL_FAIL_SCORE_CAP, NON_CRITICAL_FAIL_SCORE_CAP,
                     WORD_TARGET_MIN, WORD_TARGET_MAX)
from .gates import (check_gates, VERIFIED_EMPLOYERS, VERIFIED_CERTS,
                    VERIFIED_METRICS, FORBIDDEN_DEGREES, FORBIDDEN_EMPLOYERS,
                    FORBIDDEN_CLEARANCE)

_ACTION_VERBS = (
    "developed", "built", "designed", "deployed", "implemented", "architected",
    "led", "managed", "created", "applied", "trained", "fine-tuned", "reduced",
    "improved", "optimized", "automated", "secured", "delivered", "collaborated",
    "spearheaded", "integrated", "engineered", "analyzed", "processed",
    "orchestrated", "directed", "established", "migrated", "scaled",
)

_JD_THEMES = {
    "genai":      ["genai", "generative ai", "llm", "large language model",
                   "fine-tun", "prompt engineering", "rag"],
    "data":       ["python", "sql", "etl", "pipeline", "data engineering"],
    "eval":       ["evaluation", "benchmark", "bias", "fairness", "model performance"],
    "compute":    ["distributed training", "gpu", "h100", "a100", "multi-gpu", "cuda"],
    "containers": ["docker", "kubernetes", "container"],
    "governance": ["governance", "regulated", "compliance", "ethics", "audit"],
    "mlops":      ["mlops", "ci/cd", "monitoring", "experiment tracking"],
}

_SKILLS = ["python", "pytorch", "tensorflow", "sql", "docker", "kubernetes",
           "aws", "langchain", "pinecone", "hadoop", "spark", "airflow"]


@dataclass
class ScoreDetail:
    category: str
    raw_fraction: float     # 0..1
    points: float           # points earned
    max_points: float
    note: str


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _band(value: float, table: list[tuple[float, float]]) -> float:
    """Map a fraction to the highest band whose threshold it meets."""
    for threshold, score in table:
        if value >= threshold:
            return score
    return 0.0


def score(resume_text: str) -> dict:
    """Score a resume. Returns total, per-category detail and the gate verdict."""
    text = resume_text or ""
    lower = text.lower()
    gates = check_gates(text)
    details: list[ScoreDetail] = []

    # ── fidelity ───────────────────────────────────────────────────────────
    forbidden = sum(1 for w in (FORBIDDEN_DEGREES + FORBIDDEN_EMPLOYERS +
                                FORBIDDEN_CLEARANCE) if w in lower)
    emp_hits = sum(1 for e in VERIFIED_EMPLOYERS if e in lower)
    cert_hits = sum(1 for c in VERIFIED_CERTS if c in lower)
    if forbidden >= 2:
        f = 0.0
    elif forbidden == 1:
        f = 0.25
    else:
        # require BOTH employers and certs to be present before rewarding
        f = 0.5 + 0.3 * _clamp01(emp_hits / 4) + 0.2 * (1.0 if cert_hits >= 3 else 0.0)
    f = _clamp01(f)
    details.append(ScoreDetail("fidelity", f, round(f * WEIGHTS["fidelity"], 1),
                               WEIGHTS["fidelity"],
                               f"forbidden={forbidden} employers={emp_hits} certs={cert_hits}"))

    # ── alignment ──────────────────────────────────────────────────────────
    theme_hits = {t: int(any(k in lower for k in kws)) for t, kws in _JD_THEMES.items()}
    a_frac = sum(theme_hits.values()) / len(_JD_THEMES)
    details.append(ScoreDetail("alignment", a_frac, round(a_frac * WEIGHTS["alignment"], 1),
                               WEIGHTS["alignment"],
                               f"themes={sum(theme_hits.values())}/{len(_JD_THEMES)}"))

    # ── bullets ────────────────────────────────────────────────────────────
    bullets = [l.strip() for l in text.splitlines()
               if l.strip()[:1] in ("-", "•", "*", "▪", "◦")]
    verb_ratio = (sum(1 for b in bullets
                      if b.lower().lstrip("-•*▪◦ ").startswith(_ACTION_VERBS))
                  / len(bullets)) if bullets else 0.0
    avg_len = (sum(len(b.split()) for b in bullets) / len(bullets)) if bullets else 0.0
    b_frac = _band(verb_ratio, [(0.85, 1.0), (0.65, 0.8), (0.45, 0.55), (0.25, 0.3)])
    if not (7 <= avg_len <= 28):
        b_frac *= 0.75          # length outside the readable band costs 25%
    details.append(ScoreDetail("bullets", b_frac, round(b_frac * WEIGHTS["bullets"], 1),
                               WEIGHTS["bullets"],
                               f"n={len(bullets)} verb_ratio={verb_ratio:.2f} avg_len={avg_len:.0f}"))

    # ── metrics (verified numbers only) ────────────────────────────────────
    verified = sum(1 for m in VERIFIED_METRICS if m in lower)
    m_frac = _band(verified, [(5, 1.0), (4, 0.85), (3, 0.65), (2, 0.4), (1, 0.2)])
    details.append(ScoreDetail("metrics", m_frac, round(m_frac * WEIGHTS["metrics"], 1),
                               WEIGHTS["metrics"], f"verified_metrics={verified}"))

    # ── targeting ──────────────────────────────────────────────────────────
    head = lower[:600]
    t = 0.0
    if "boeing" in head or "defense" in head:
        t += 0.5
    if "cogito metric" in lower:
        t += 0.3
    if "noaa" in lower and "naval research" in lower:
        t += 0.2
    elif "noaa" in lower or "naval research" in lower:
        t += 0.1
    t_frac = _clamp01(t)
    details.append(ScoreDetail("targeting", t_frac, round(t_frac * WEIGHTS["targeting"], 1),
                               WEIGHTS["targeting"],
                               f"role_first={'boeing' in head or 'defense' in head}"))

    # ── ats_structure ──────────────────────────────────────────────────────
    sections = sum(x in lower for x in
                   ("professional experience", "education", "project", "skills"))
    s_frac = _clamp01(sections / 4)
    details.append(ScoreDetail("ats_structure", s_frac,
                               round(s_frac * WEIGHTS["ats_structure"], 1),
                               WEIGHTS["ats_structure"], f"sections={sections}/4"))

    # ── skills ─────────────────────────────────────────────────────────────
    sk = sum(1 for k in _SKILLS if k in lower)
    sk_frac = _band(sk, [(9, 1.0), (7, 0.85), (5, 0.6), (3, 0.35), (1, 0.15)])
    details.append(ScoreDetail("skills", sk_frac, round(sk_frac * WEIGHTS["skills"], 1),
                               WEIGHTS["skills"], f"skill_hits={sk}"))

    # ── brevity ────────────────────────────────────────────────────────────
    wc = len(text.split())
    if WORD_TARGET_MIN <= wc <= WORD_TARGET_MAX:
        br = 1.0
    elif 320 <= wc <= 700:
        br = 0.8
    elif 250 <= wc <= 800:
        br = 0.5
    else:
        br = 0.2
    details.append(ScoreDetail("brevity", br, round(br * WEIGHTS["brevity"], 1),
                               WEIGHTS["brevity"], f"words={wc}"))

    raw_total = round(sum(d.points for d in details), 1)

    # ── gate clamp: the fix for v4's score/gate contradiction ──────────────
    if gates["critical_fails"]:
        cap = CRITICAL_FAIL_SCORE_CAP
        reason = f"capped at {cap} by critical gate(s) {gates['critical_fails']}"
    elif gates["non_critical_fails"]:
        cap = NON_CRITICAL_FAIL_SCORE_CAP
        reason = f"capped at {cap} by gate(s) {gates['non_critical_fails']}"
    else:
        cap = 100.0
        reason = "no gate failures"

    total = round(min(raw_total, cap), 1)

    if total >= 90:
        band = "production-ready"
    elif total >= 80:
        band = "strong"
    elif total >= 70:
        band = "usable-with-edits"
    elif total >= 60:
        band = "weak"
    else:
        band = "not-deployable"

    return {
        "total": total,
        "raw_total": raw_total,
        "clamped": bool(raw_total > cap),
        "clamp_reason": reason,
        "band": band,
        "categories": {d.category: {"points": d.points, "max": d.max_points,
                                    "fraction": round(d.raw_fraction, 3),
                                    "note": d.note} for d in details},
        "gates": gates,
        # expose the denominator so a reader can verify it is 100
        "weights_total": sum(WEIGHTS.values()),
    }
