"""Shortlist builder — AA writing-adjacent proxy.

Artificial Analysis publishes NO writing benchmark. Verified against the live
v2 API: 18 evaluation fields, none of them writing/essay/prose/style/summarisation.

So this module builds an explicitly-labelled PROXY from measures that are
adjacent to resume writing, and reports the proxy as a proxy:

  IFBench  0.35  instruction following  -> ATS format compliance, section order,
                                           word bands, "no tables" constraints
  LCR      0.25  long-context reasoning -> hold a full JD + profile across a
                                           long output without losing detail
  HLE      0.25  factual rigor          -> the anti-hallucination dimension, the
                                           single most important resume property
  GPQA     0.15  reasoning under distr. -> deciding what to include and omit

Code/math benchmarks (livecodebench, scicode, terminalbench*, aime*, math_500)
are deliberately EXCLUDED: they do not transfer to prose authoring and would
reward the wrong models.

A model must have >= 3 of the 4 components to be scored; the weighted mean is
taken over the components present, so a missing measure never becomes a zero.
"""
from __future__ import annotations

import re

import requests

PROXY_WEIGHTS = {"ifbench": 0.35, "lcr": 0.25, "hle": 0.25, "gpqa": 0.15}
MIN_COMPONENTS = 3

_TOKEN = re.compile(r"[a-z]+|\d+(?:\.\d+)*")
_STOP = {"the", "a", "of", "in", "on", "and"}


def _tokens(s: str) -> set[str]:
    s = re.sub(r"\s*\([^)]*\)\s*$", "", str(s or "")).lower()
    return set(_TOKEN.findall(s)) - _STOP


def fetch_aa(api_key: str) -> list[dict]:
    """AA models. `api_key` must be the ARTIFICIAL_ANALYSIS_KEY, not a
    OpenRouter key — the two services do not share credentials and AA answers
    401 for an OpenRouter key."""
    r = requests.get("https://artificialanalysis.ai/api/v2/data/llms/models",
                     headers={"x-api-key": api_key}, timeout=60)
    if r.status_code == 401:
        raise RuntimeError(
            "Artificial Analysis returned 401 — ARTIFICIAL_ANALYSIS_KEY is missing "
            "or wrong. This is a different credential from OPENROUTER_API_KEY_1.")
    r.raise_for_status()
    return r.json()["data"]


def fetch_or_catalog() -> list[dict]:
    r = requests.get("https://openrouter.ai/api/v1/models", timeout=90)
    r.raise_for_status()
    return r.json()["data"]


def proxy_score(ev: dict) -> tuple[float | None, int]:
    """Weighted mean over available components. Returns (score, n_components)."""
    num = den = 0.0
    n = 0
    for k, w in PROXY_WEIGHTS.items():
        v = ev.get(k)
        if v is not None:
            num += w * float(v)
            den += w
            n += 1
    return (num / den if den else None), n


def build(api_key: str, min_jaccard: float = 0.80) -> list[dict]:
    """Return scored models that exist on OpenRouter with a price and a speed."""
    aa = fetch_aa(api_key)
    catalog = fetch_or_catalog()

    or_idx = []
    for m in catalog:
        oid = m["id"]
        if any(x in oid for x in (":free", ":batch", ":nitro")) or oid.startswith("~"):
            continue
        or_idx.append((oid, _tokens(oid.split("/")[-1]),
                       _tokens((m.get("name") or "").split(":")[0])))

    def match(name: str):
        q = _tokens(name)
        if not q:
            return None, 0.0
        best, bj = None, 0.0
        for oid, tail, nm in or_idx:
            for cand in (tail, nm):
                if not cand:
                    continue
                j = len(q & cand) / len(q | cand)
                if j > bj:
                    best, bj = oid, j
        return (best, bj) if bj >= min_jaccard else (None, bj)

    out = []
    for m in aa:
        ev = m.get("evaluations") or {}
        pr = m.get("pricing") or {}
        price = pr.get("price_1m_blended_3_to_1")
        tput = m.get("median_output_tokens_per_second")
        score, ncomp = proxy_score(ev)
        if score is None or ncomp < MIN_COMPONENTS:
            continue
        if not price or float(price) <= 0 or not tput or float(tput) <= 0:
            continue
        oid, j = match(m["name"])
        if oid is None:
            continue
        out.append({
            "aa_name": m["name"],
            "or_id": oid,
            "jaccard": round(j, 2),
            "writing_proxy": round(score, 4),
            "components": ncomp,
            "ifbench": ev.get("ifbench"),
            "lcr": ev.get("lcr"),
            "hle": ev.get("hle"),
            "gpqa": ev.get("gpqa"),
            "price_blend_1m": float(price),
            "tput": float(tput),
            "value": round(score / float(price), 3),
        })

    # ranks over the surviving set
    for key, name in (("writing_proxy", "rank_writing"), ("value", "rank_value")):
        ordered = sorted(out, key=lambda r: r[key], reverse=True)
        for i, r in enumerate(ordered, 1):
            r[name] = i
    for r in out:
        r["rank_combined"] = round((r["rank_writing"] + r["rank_value"]) / 2, 1)
    out.sort(key=lambda r: r["rank_combined"])
    return out


def print_shortlist(rows: list[dict], limit: int = 25) -> None:
    print("=" * 116)
    print("WRITING-ADJACENT SHORTLIST — a PROXY, not an AA writing benchmark")
    print("  Artificial Analysis publishes no writing measure (18 eval fields, none writing).")
    print("  proxy = IFBench .35 + LCR .25 + HLE .25 + GPQA .15")
    print("  value = proxy / blended $/1M      rank_c = mean(writing rank, value rank)")
    print("=" * 116)
    print(f"{'#':<3}{'model':<46}{'or_id':<40}{'proxy':>7}{'$/1M':>8}"
          f"{'value':>8}{'tok/s':>7}{'rW':>4}{'rV':>4}")
    print("-" * 116)
    for i, r in enumerate(rows[:limit], 1):
        print(f"{i:<3}{r['aa_name'][:44]:<46}{r['or_id'][:38]:<40}"
              f"{r['writing_proxy']:>7.3f}{r['price_blend_1m']:>8.2f}"
              f"{r['value']:>8.2f}{r['tput']:>7.0f}"
              f"{r['rank_writing']:>4}{r['rank_value']:>4}")
