#!/usr/bin/env python3
"""Grounding checks learned from `Render_Dockers/resume_bench`.

Four additions, each closing a demonstrated gap rather than a hypothetical one:

  1. CONTENT GATE (S-1..S-7) — run BEFORE any truth check.
     A truth check on a vacuous document trivially succeeds: a document with no
     claims cannot contain a false claim. Measured on our own harness, a 59-word
     skeleton with zero bullets scored `faith clean=True, struct clean=True` —
     a PASS. `resume_bench` hit the same bug on their first live run (4 of 8
     "passes" were headers-only or the model asking for more information).

  2. TYPED CLAIMS — (value, unit, subject, owner) instead of a flat whitelist.
     A flat list is simultaneously too permissive and too brittle:
       `30%` vs `30 percent`      -> same fact, different surface (false miss)
       `30% diagnostic time` vs
       `30% revenue`              -> same number, one is a false claim
     We previously matched bare substrings, so `40%` was legal under ANY
     employer.

  3. OWNERSHIP (T-2) — a real number re-attached to the wrong employer is still
     a false claim. Attribution uses the nearest-preceding employer heading,
     which is a heuristic; the violation names both companies so a human can
     judge rather than trusting a bare verdict.

  4. PRESERVATION (P-2) — required facts must SURVIVE into the output. We
     measured invention but never loss.

Plus TIER DISCIPLINE: a verdict is never a bare `PASS`. Deterministic checks
cover tier A only; anything requiring semantics is surfaced as review, and the
verdict string says so.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── normalization ─────────────────────────────────────────────────────────
_UNIT_ALIASES = {
    "%": "percent", "percent": "percent", "pct": "percent",
    "k": "thousand", "thousand": "thousand",
    "m": "million", "mm": "million", "million": "million",
    "b": "billion", "billion": "billion",
    "hr": "hours", "hrs": "hours", "hour": "hours", "hours": "hours",
    "day": "days", "days": "days",
    "week": "weeks", "weeks": "weeks",
    "month": "months", "months": "months",
    "year": "years", "yrs": "years", "years": "years",
    "tb": "tb", "gb": "gb", "mb": "mb", "kb": "kb",
    "x": "multiplier",
}

# NOTE: bare `m` and `b` are deliberately NOT unit tokens, and word units carry
# a trailing `\b`. "4200 monthly appointment requests" must NOT parse as
# "4200 months' worth": without the boundary, `months?` matches the prefix of
# "monthly" and invents an owner that disagrees with the allowlist.
_UNIT_TOKEN = (
    r"%|percent\b|pct\b|\$|usd\b|thousand\b|million\b|billion\b|"
    r"hours?\b|hrs?\b|days?\b|weeks?\b|months?\b|years?\b|yrs?\b|"
    r"minutes?\b|mins?\b|seconds?\b|"
    r"vessels?\b|patients?\b|staff\b|requests?\b|records?\b|clients?\b|"
    r"students?\b|users?\b|tb\b|gb\b|mb\b|kb\b|x\b"
)


def normalize_unit(raw: str) -> str:
    u = (raw or "").strip().lower().replace(".", "")
    if u in ("$", "usd"):
        return "usd"
    return _UNIT_ALIASES.get(u, u or "count")


def normalize_number(raw: str) -> str:
    s = (raw or "").replace(",", "").strip()
    try:
        f = float(s)
    except ValueError:
        return s
    return str(int(f)) if f == int(f) else f"{f:g}"


# ── ledger ────────────────────────────────────────────────────────────────
@dataclass
class Claim:
    fact_id: str
    experience_id: str = ""
    kind: str = "achievement_metric"      # | date | credential | other_number
    value: str = ""
    unit: str = "count"
    subject: str = ""
    source_text: str = ""
    required: bool = False

    def pair(self) -> tuple[str, str]:
        return (normalize_number(self.value), normalize_unit(self.unit))


@dataclass
class Ledger:
    profile_id: str
    claims: list[Claim] = field(default_factory=list)
    companies: list[str] = field(default_factory=list)

    def metric_claims(self) -> list[Claim]:
        return [c for c in self.claims if c.kind == "achievement_metric"]

    def required_claims(self) -> list[Claim]:
        return [c for c in self.claims if c.required]

    def owned_pairs(self) -> dict[tuple, str]:
        """(value, unit) -> owning company. Denominator for T-2."""
        out: dict[tuple, str] = {}
        for c in self.metric_claims():
            if c.experience_id:
                out[c.pair()] = c.experience_id.lower()
        return out

    def supports(self, value: str, unit: str) -> bool:
        v = normalize_number(value)
        u = normalize_unit(unit)
        for c in self.metric_claims():
            cv, cu = c.pair()
            if cv == v and cu == u:
                return True
            # A value quoted without a unit is a weaker match, accepted only
            # when the ledger has exactly one claim with that value.
            if cv == v and u in ("count", ""):
                if sum(1 for x in self.metric_claims()
                       if x.pair()[0] == v) == 1:
                    return True
        return False


# ── claim extraction from generated prose ─────────────────────────────────
# Up to two non-stopword tokens may sit between the number and its unit, so
# "4200 monthly appointment requests" and "12 front-desk staff" are captured.
# Prepositions and articles are excluded from that gap: "42% of staff" must not
# attach `staff` to 42. The holdout fixture found this gap; the tuning fixture
# never exercised it.
_CLAIM_RE = re.compile(
    rf"(?<![\d.])(\d+(?:[.,]\d+)?)\s*\+?"
    rf"(?:\s+(?!(?:the|a|an|of|in|on|for|to|and|or|at|by|per)\b)[\w'-]+){{0,2}}"
    rf"\s*({_UNIT_TOKEN})",
    re.IGNORECASE)


def extract_output_claims(text: str) -> list[dict]:
    out = []
    for m in _CLAIM_RE.finditer(text or ""):
        start = max(0, m.start() - 70)
        ctx = (text[start:m.end() + 70] or "").replace("\n", " ")
        out.append({"surface": m.group(0).strip(),
                    "value": normalize_number(m.group(1)),
                    "unit": normalize_unit(m.group(2)),
                    "context": ctx.strip()})
    return out


_CONTENT_STOP = {
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with",
    "by", "from", "that", "this", "was", "were", "is", "are", "be", "been",
    "at", "as", "it", "its", "about", "approximately", "roughly", "over",
}


def _content_words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", (s or "").lower())
            if w not in _CONTENT_STOP}


def subject_overlap(claim_ctx: str, source_subject: str) -> float:
    """Jaccard of content words. Diagnostic only — never a hard failure.

    Exact subject matching would require a semantic checker, which this harness
    deliberately does not have (no LLM-as-judge). Overlap is therefore reported
    as a review signal, matching the two-tier model.
    """
    a = _content_words(claim_ctx)
    b = _content_words(source_subject)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ── T-2 ownership ─────────────────────────────────────────────────────────
def check_ownership(text: str, ledger: Ledger) -> list[dict]:
    """Is each supported metric attached to the employer that owns it?"""
    owned = ledger.owned_pairs()
    if not owned:
        return []
    violations = []
    current = None
    names = sorted({c.lower() for c in ledger.companies if c},
                   key=len, reverse=True)
    for line in (text or "").splitlines():
        low = line.lower()
        for co in names:
            if co in low:
                current = co
                break
        for m in _CLAIM_RE.finditer(line):
            key = (normalize_number(m.group(1)), normalize_unit(m.group(2)))
            owner = owned.get(key)
            if owner and current and owner != current:
                violations.append({
                    "text": m.group(0).strip(),
                    "reason": "metric_owned_by_other_employer",
                    "expected_employer": owner,
                    "found_under": current,
                })
    return violations


# ── content gate (S-1..S-7) ───────────────────────────────────────────────
_META_MARKERS = (
    "i'm ready to", "i am ready to", "please provide", "i need the details",
    "could you provide", "i'd be happy to", "here is", "here's the",
    "as an ai", "i cannot", "i'm unable", "let me know", "would you like",
    "sure,", "certainly,", "of course",
)

_SECTION_PATTERNS = {
    "experience": re.compile(
        r"^\s*(?:#{0,6}\s*)?(?:professional|work|employment|relevant|career)?"
        r"\s*experience\b", re.IGNORECASE | re.MULTILINE),
    "education": re.compile(
        r"^\s*(?:#{0,6}\s*)?(?:education|academic)\b",
        re.IGNORECASE | re.MULTILINE),
    "certifications": re.compile(
        r"^\s*(?:#{0,6}\s*)?(?:certificat|licen[sc])",
        re.IGNORECASE | re.MULTILINE),
}


def content_gate(text: str, min_words: int = 90,
                 min_bullets: int = 4) -> dict:
    """S-1..S-7. Reject a non-resume BEFORE any truth check runs.

    Ordering is load-bearing, not stylistic: a document with no claims cannot
    contain a false claim, so truth checks on an empty document always pass.
    """
    t = (text or "").strip()
    problems: list[str] = []
    low = t.lower()

    # S-1 conversational / meta output — the model declined to write
    head = low[:240]
    for m in _META_MARKERS:
        if low.startswith(m) or m in head:
            problems.append("meta_or_conversational_output")
            break

    # S-2 length
    wc = len(t.split())
    if wc < min_words:
        problems.append(f"below_min_words:{wc}<{min_words}")

    # S-3/S-4 sections present AND non-empty.
    #
    # The body of a section is everything up to the NEXT KNOWN section heading,
    # not up to the next title-case line: company names ("Cogito Metric") and
    # role lines are title case and were terminating the block immediately,
    # making every correct resume report `empty_section`.
    known_heads = sorted(
        [(m.start(), m.end(), name)
         for name, pat in _SECTION_PATTERNS.items()
         for m in pat.finditer(t)], key=lambda x: x[0])
    for sec, pat in _SECTION_PATTERNS.items():
        m = pat.search(t)
        if not m:
            problems.append(f"missing_section:{sec}")
            continue
        nxt = next((s for s, _e, name in known_heads
                    if s > m.end() and name != sec), len(t))
        body = t[m.end():nxt]
        # A certifications block can legitimately be a short list; require
        # content, not length.
        if len(body.split()) < 2:
            problems.append(f"empty_section:{sec}")

    # S-5 placeholders
    if re.search(r"\[[A-Za-z ]{3,}\]", t):
        problems.append("bracket_placeholder")
    if re.search(r"\{[A-Za-z ]{3,}\}", t):
        problems.append("brace_placeholder")

    # S-6 no bullets at all — a resume without achievements is a skeleton
    n_bul = sum(1 for ln in t.splitlines()
                if ln.strip().startswith(("-", "•", "*", "·")))
    if n_bul == 0:
        n_bul = max(0, len(re.findall(r"(?m)^\S.{30,}$", t)) - 3)
    if n_bul < min_bullets:
        problems.append(f"below_min_bullets:{n_bul}<{min_bullets}")

    # S-7 degenerate repetition. One variant emitted ~25k chars of
    # "In addition. In addition." and would otherwise score as a long resume.
    words = re.findall(r"[a-z']+", low)
    if len(words) >= 50:
        ratio = len(set(words)) / len(words)
        if ratio < 0.25:
            problems.append(f"degenerate_repetition:unique_ratio={ratio:.2f}")

    return {"ok": not problems, "problems": problems, "words": wc,
            "bullets": n_bul}


# ── P-2 preservation ──────────────────────────────────────────────────────
def check_preservation(ledger: Ledger, text: str) -> list[dict]:
    """Every `required` fact must survive into the final output."""
    nums = {normalize_number(c["value"])
            for c in extract_output_claims(text)}
    nums |= {normalize_number(n)
             for n in re.findall(r"\d+(?:[.,]\d+)?", text or "")}
    lost = []
    for c in ledger.required_claims():
        if normalize_number(c.value) not in nums:
            lost.append({"text": f"{c.value} {c.unit}".strip(),
                         "reason": "required_fact_lost",
                         "source_text": c.source_text[:120]})
    return lost


# ── tiered verdict ────────────────────────────────────────────────────────
@dataclass
class TruthResult:
    tier_a: list[dict] = field(default_factory=list)     # hard failures
    tier_b: list[dict] = field(default_factory=list)     # needs review
    claims_found: int = 0
    claims_supported: int = 0
    tier_b_checked: bool = False

    @property
    def passed(self) -> bool:
        return not self.tier_a

    @property
    def verdict(self) -> str:
        """Never a bare PASS. Deterministic checks cover tier A only."""
        if self.tier_a:
            return "FAIL"
        return "PASS (tier A only)"

    def to_dict(self) -> dict:
        return {"verdict": self.verdict,
                "tier_a_violations": self.tier_a,
                "tier_b_review_required": self.tier_b,
                "tier_b_checked": self.tier_b_checked,
                "claims_found": self.claims_found,
                "claims_supported": self.claims_supported}


def check_truth(text: str, ledger: Ledger,
                entities_ok: bool = True) -> TruthResult:
    """T-1..T-4 + T-2 ownership, with tier-B subject overlap surfaced."""
    res = TruthResult(tier_b_checked=False)
    found = extract_output_claims(text)
    res.claims_found = len(found)

    by_pair = {c.pair(): c for c in ledger.metric_claims()}
    by_value: dict[str, list[Claim]] = {}
    for c in ledger.metric_claims():
        by_value.setdefault(c.pair()[0], []).append(c)

    for claim in found:
        pair = (claim["value"], claim["unit"])
        owner_claim = by_pair.get(pair)
        if owner_claim is None:
            cands = by_value.get(claim["value"], [])
            owner_claim = cands[0] if len(cands) == 1 else None
        if owner_claim is None:
            res.tier_a.append({"text": claim["surface"],
                               "context": claim["context"],
                               "reason": "no_candidate_evidence"})
            continue
        res.claims_supported += 1
        if owner_claim.subject:
            ov = subject_overlap(claim["context"], owner_claim.subject)
            if ov < 0.15:
                res.tier_b.append({
                    "text": claim["surface"],
                    "context": claim["context"],
                    "reason": "subject_mismatch_review",
                    "expected_subject": owner_claim.subject,
                    "overlap": round(ov, 2),
                })

    res.tier_a.extend(check_ownership(text, ledger))
    return res


# ── ledger construction from our fixtures ─────────────────────────────────
def build_ledger(experiences, verified_metrics=None,
                 extra_required=None) -> Ledger:
    """Derive a typed ledger from the source experiences.

    Each metric is attributed to the company whose bullet states it, which is
    what makes the ownership check possible at all.
    """
    claims: list[Claim] = []
    companies: list[str] = []
    vm = verified_metrics or []

    # The allowlist is authoritative on UNITS when the numbers agree. A source
    # bullet may describe the same fact with looser wording ("4200 monthly
    # requests" vs allowlist "4200 requests"); without reconciliation the owned
    # pair and the legal pair disagree and a correct resume fails.
    vm_by_value: dict[str, list[dict]] = {}
    for m in vm:
        vm_by_value.setdefault(normalize_number(m["value"]), []).append(m)

    for exp in experiences:
        co = exp.get("company", "")
        companies.append(co)
        for i, bullet in enumerate(exp.get("bullets") or []):
            for m in _CLAIM_RE.finditer(bullet):
                val = normalize_number(m.group(1))
                unit = normalize_unit(m.group(2))
                cands = vm_by_value.get(val, [])
                if len(cands) == 1:
                    unit = normalize_unit(cands[0]["unit"])
                st = max(0, m.start() - 45)
                ctx = bullet[st:m.end() + 45].strip()
                claims.append(Claim(
                    fact_id=f"{co}_m{i}",
                    experience_id=co,
                    kind="achievement_metric",
                    value=m.group(1),
                    unit=unit,
                    subject=ctx,
                    source_text=bullet,
                    required=True,
                ))
    # Verified metrics that are not in the bullets are still legal claims,
    # but they have no owner, so ownership cannot be enforced for them.
    seen = {(normalize_number(c.value), normalize_unit(c.unit)) for c in claims}
    for m in vm:
        pair = (normalize_number(m["value"]), normalize_unit(m["unit"]))
        if pair in seen:
            continue
        claims.append(Claim(fact_id=f"vm_{m['value']}{m['unit']}",
                            kind="achievement_metric",
                            value=str(m["value"]), unit=m["unit"]))
    return Ledger(profile_id="fixture", claims=claims, companies=companies)
