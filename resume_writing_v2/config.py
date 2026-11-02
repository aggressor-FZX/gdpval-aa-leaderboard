"""Configuration for the v2 resume-writing competition harness.

Every number here is a deliberate choice with a stated reason. Weights are
validated at import: v4 declared 100 but summed to 110 and clipped with
min(total, 100), which silently compressed every model's score.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# ── Scoring weights ────────────────────────────────────────────────────────
# These MUST sum to 100. The assertion below is not decorative: v4's docstring
# claimed 35+20+10+10+10+5+5+5 = 100 while the code actually weighted nine
# categories totalling 110.
WEIGHTS = {
    "fidelity":        30,  # no invented facts — the non-negotiable property
    "alignment":       20,  # JD vocabulary actually present
    "bullets":         12,  # action verb + quantified impact
    "metrics":         10,  # verified numbers only
    "targeting":       10,  # ordering / emphasis toward the target role
    "ats_structure":    8,  # machine-parseable sections
    "skills":           5,  # required stack coverage
    "brevity":          5,  # word band
}
assert sum(WEIGHTS.values()) == 100, f"weights must sum to 100, got {sum(WEIGHTS.values())}"

# GSI (grounded skill inference) is scored separately as a BONUS, capped at 0,
# because v4 gave it 10 points that made the total 110. Bonus points cannot
# push a run past 100 once the gate clamp is applied.
GSI_BONUS_CAP = 0.0

# ── Gate severity ──────────────────────────────────────────────────────────
CRITICAL_GATES = ("G1", "G2", "G3", "G4")      # disqualifying
NON_CRITICAL_GATES = ("G5", "G6", "G7", "G8", "G9", "G10")

# A run failing any gate cannot exceed this score. This is the fix for v4's
# 13 runs that scored >=90 while failing a gate.
CRITICAL_FAIL_SCORE_CAP = 69.0
NON_CRITICAL_FAIL_SCORE_CAP = 89.0

# ── Word band ──────────────────────────────────────────────────────────────
WORD_MIN, WORD_MAX = 320, 700
WORD_TARGET_MIN, WORD_TARGET_MAX = 400, 600

# ── Runner ─────────────────────────────────────────────────────────────────
RUNS_PER_MODEL = 3
MAX_SPEND_USD = 5.00          # hard ceiling; the runner stops submitting at it
MAX_CONCURRENCY = 4
REQUEST_TIMEOUT_S = 240
RETRIES = 2

# Reasoning models spend completion tokens on hidden reasoning BEFORE emitting
# any answer. In the first live run a 4096 cap was fully consumed by reasoning
# (GLM-5.3-Flash: 4772 reasoning tokens / 0 answer; Hy3: 4096 / 0), so both
# returned an empty completion and could not be scored. The cap must cover
# reasoning PLUS the ~600 words of resume, so it is set well above both.
REASONING_HEADROOM = 16384

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CATALOG_URL = "https://openrouter.ai/api/v1/models"


def _load_env() -> None:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def api_key() -> str:
    """OpenRouter inference key. Never hardcoded."""
    _load_env()
    key = os.getenv("OPENROUTER_API_KEY_1")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY_1 not set (add it to .env)")
    return key


def aa_key() -> str:
    """Artificial Analysis key — a DIFFERENT service from OpenRouter.

    Kept separate because passing the OpenRouter key to the AA endpoint returns
    401, and silently falling back would produce an empty shortlist that looks
    like 'no models qualify' rather than 'wrong credential'.
    """
    _load_env()
    key = os.getenv("ARTIFICIAL_ANALYSIS_KEY")
    if not key:
        raise RuntimeError("ARTIFICIAL_ANALYSIS_KEY not set (add it to .env)")
    return key


@dataclass
class ModelEntry:
    """One competitor: an OpenRouter id at a specific reasoning effort.

    Reasoning variants are distinct models. AA measures them separately and
    they differ materially (e.g. the same family at Max vs Non-reasoning), so
    a result must always name the variant that produced it.
    """
    model_id: str
    label: str
    effort: str | None = None      # 'max'|'high'|'medium'|'low'|None
    group: str = "shortlist"
    max_tokens: int = REASONING_HEADROOM
    extra: dict = field(default_factory=dict)

    def request_body(self, prompt: str, system: str) -> dict:
        from .config import WORD_MAX
        body = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": 0.2,
            "usage": {"include": True},   # makes usage.cost available
        }
        if self.effort:
            body["reasoning_effort"] = self.effort
        if self.extra:
            body.update(self.extra)
        return body
