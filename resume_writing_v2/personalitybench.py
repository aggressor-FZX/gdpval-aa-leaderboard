"""AA-PersonalityBench — the writing benchmark AA does not expose via its API.

CORRECTION LOG (kept because both errors were mine and both were consequential)
------------------------------------------------------------------------------
1. I first claimed "AA publishes no writing benchmark" based on the v2 API's 18
   evaluation fields. WRONG: AA-PersonalityBench exists on the website.
2. I then named the field `slop_avoidance` and treated a higher value as better.
   That was INVERTED. Corrected below.

WHERE THE DATA LIVES (all verified live 2026-11-02)
---------------------------------------------------
  data.artificialanalysis.ai/api/v1/models       -> 404 DEPLOYMENT_NOT_FOUND
  artificialanalysis.ai/api/v2/data/llms/models  -> 200, 723 records,
                                                    0 personality fields
  artificialanalysis.ai/models/<slug>            -> works; the whole leaderboard
                                                    is embedded in the RSC payload

TWO SEPARATE SCALES - DO NOT MIX THEM
-------------------------------------
AA-PersonalityBench publishes BOTH:

  * 8 INDEX scores  - percentile ranks 1-100 (AA's own page text).
                      e.g. organization 87.6, slop 20.8
  * 30 TRAIT scores - Elo-scale ratings, one per named trait. Measured range
                      across the 40 scored models is -611 to 2178, and 19 of
                      them carry negative values, so never assume 0 is a floor:
      lexicallyVaried, eloquent, literate, naturalSounding, metaphorical,
      structured, scannable, summarizesBottomLine, answerFirst,
      informationDense, evidenceBased, resourceSpecific,
      providesActionableGuidance, pragmatic, truthful, admitsUncertainty,
      disclaimsWithAssumptions, flagsNuances, sycophantic, friendly, humorous,
      sincere, emotionallyIntelligent, direct, confident, opinionated,
      constructivelyPushesBack, creative, openEnded, slop

The two are different units. Averaging an Elo with a percentile is meaningless.
The indexes are used for ranking; the traits are used to inspect WHY a model
scores as it does.

THE 8 INDEXES (percentile ranks 1-100, per AA's own page text)
--------------------------------------------------------------
  organization     structure / scannability / answer-first ordering
  slop             AMOUNT of filler and AI buzzwords -- LOWER IS BETTER
  expressiveness   prose variety
  informativeness  information density
  transparency     candour / self-explanation
  warmth, conviction, imagination

SLOP DIRECTION — THE TRAP, MEASURED
-----------------------------------
`indexScores["slop"]` is the amount of slop. HIGHER = MORE filler = WORSE.

Evidence, computed over all 40 scored models:
  corr(organization, slop) = -0.196      NEGATIVE

A negative correlation disproves the "avoidance" reading: if the field meant
avoidance, good structure and high values would agree (positive correlation).
The worst-structured models carry the highest slop values:

  Llama 4 Maverick      organization  3.5  slop 100.0
  GPT-4o (Nov '24)      organization  6.0  slop  97.5
  GPT-3.5 Turbo         organization  1.0  slop  90.1
  DeepSeek V4.1 Flash   organization 100.0  slop  40.6

So the field is exposed as `slop` (amount, lower is better) and any caller that
combines it with `organization` must INVERT it:
    writing = (organization + (100 - slop)) / 2

EXTRACTION — SECOND BUG, ALSO MINE
----------------------------------
Every model page embeds the WHOLE leaderboard (~41 `personalityBench` blocks).
The first attempt took block[0] for every model, which is a degenerate
placeholder (organization=1, slop=90.1). That produced ~200 identical rows all
reading 1.0/90.1 that looked like data and were meaningless.

The owner of a block is the NEAREST PRECEDING `"name"`. Validated against Kimi
K3.1 Pro's own page: organization 87.625, expressiveness 62.875, slop 20.8.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120 Safari/537.36")}
BASE = "https://artificialanalysis.ai/models"

INDEX_KEYS = ("expressiveness", "organization", "informativeness",
              "transparency", "warmth", "conviction", "imagination", "slop")

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "results", "personalitybench_cache.json")

# The degenerate placeholder block seen at the head of every payload.
_PLACEHOLDER = {"organization": 1.0, "slop": 90.1}


def _payload(html: str) -> str:
    """Concatenate and unescape the Next.js RSC flight chunks."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    return "".join(chunks).replace('\\\\"', '"').replace('\\"', '"')


def parse_leaderboard(s: str) -> dict[str, dict]:
    """name -> raw index scores, from the leaderboard embedded in any page."""
    out: dict[str, dict] = {}
    for m in re.finditer(r'"personalityBench":\{"scores":', s):
        i = m.start()
        seg = s[max(0, i - 6000):i]
        names = re.findall(r'"name":"([^"]{2,70})"', seg)
        if not names:
            continue
        name = names[-1]
        isc = s.find('"indexScores":{', i)
        if isc < 0 or isc - i > 6000:
            continue
        end = s.find("}", isc)
        vals = {k: float(v) for k, v in
                re.findall(r'"([a-zA-Z]+)":(-?[0-9.]+)', s[isc:end])}
        if len(vals) < len(INDEX_KEYS):
            continue
        rec = {k: vals.get(k) for k in INDEX_KEYS}
        if (rec["organization"] == _PLACEHOLDER["organization"]
                and rec["slop"] == _PLACEHOLDER["slop"]):
            continue
        # Trait-level Elos live in the sibling "scores" dict, NOT in indexScores.
        # They are on an unbounded Elo scale (-611 to 2178 across our 40
        # models, with 19 negatives), NOT percentiles - never compare them to
        # the indexes and never average the two together.
        scores_m = re.search(r'"personalityBench":\{"scores":\{([^}]*)\}', s[max(0, i - 200):i + 4000])
        traits = {}
        if scores_m:
            traits = {k: float(v) for k, v in
                      re.findall(r'"(\w+)":(-?[0-9.]+)', scores_m.group(1))}
        if traits:
            rec["traits"] = traits
        out.setdefault(name, rec)
    return out


def normalise(raw: dict[str, dict]) -> list[dict]:
    """Flatten to rows. `slop` is the AMOUNT of slop: lower is better."""
    rows = []
    for name, v in raw.items():
        rows.append({
            "model": name,
            "expressiveness": v["expressiveness"],
            "organization": v["organization"],
            "informativeness": v["informativeness"],
            "transparency": v["transparency"],
            "warmth": v["warmth"],
            "conviction": v["conviction"],
            "imagination": v["imagination"],
            "slop": v["slop"],
            # combined and correctly oriented, so no caller has to remember the
            # inversion: organization good, slop bad
            "writing_score": round((v["organization"] + (100.0 - v["slop"])) / 2, 2),
            # 30 trait Elos, kept separate from the percentile indexes
            "traits": v.get("traits") or {},
        })
    return rows


def fetch_from_page(slug: str = "deepseek-v4-1-flash-non-reasoning",
                    timeout: int = 60) -> list[dict]:
    """Any model page carries the whole leaderboard, so one fetch is enough."""
    r = requests.get(f"{BASE}/{slug}", headers=UA, timeout=timeout)
    r.raise_for_status()
    return normalise(parse_leaderboard(_payload(r.text)))


def save(rows: list[dict], path: str = CACHE) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "count": len(rows), "models": rows}, f, indent=1)
    return path


def load(path: str = CACHE) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f).get("models", [])
# ── Trait selection ────────────────────────────────────────────────────────
# The traits AA publishes, camelCase exactly as stored in their payload.
TRAITS = (
    "lexicallyVaried", "eloquent", "literate", "naturalSounding",
    "metaphorical", "structured", "scannable", "summarizesBottomLine",
    "answerFirst", "informationDense", "evidenceBased", "resourceSpecific",
    "providesActionableGuidance", "pragmatic", "truthful", "admitsUncertainty",
    "disclaimsWithAssumptions", "flagsNuances", "sycophantic", "friendly",
    "humorous", "sincere", "emotionallyIntelligent", "direct", "confident",
    "opinionated", "constructivelyPushesBack", "creative", "openEnded", "slop",
)

# A model may carry either a trait Elo or an index percentile; these names
# collide with an index but are stored at index level, not trait level.
_INDEX_OVERLAP = {"slop"}


def trait_table(rows: list[dict] | None = None,
                traits: tuple[str, ...] | None = None,
                sort_by: str | None = None) -> list[dict]:
    """Pull specific traits (Eloquent, Slop, Expressiveness, ...) per model.

    Two sources are checked because AA stores the two scales in different
    places and only ONE of them is an Elo:

      trait Elos      -> row["traits"][name]        (unbounded, higher better
                                                     except `slop`)
      index percentiles -> row[name] for the 8 indexes (1-100)

    `expressiveness` is an INDEX (percentile), not a trait, so it is read from
    the top level. `eloquent` and `lexicallyVaried` are TRAITS (Elo) and are
    read from row["traits"]. Mixing them up would compare a percentile to an
    Elo, so each record records where the number came from.

    Unknown trait names raise, rather than silently returning None, so a typo
    cannot look like missing data.
    """
    rows = rows if rows is not None else load()
    wanted = traits or TRAITS
    valid = set(TRAITS) | set(INDEX_KEYS)
    bad = [t for t in wanted if t not in valid]
    if bad:
        raise KeyError(f"unknown trait(s) {bad}; valid = {sorted(valid)}")

    out = []
    for r in rows:
        rec = {"model": r["model"],
               "organization": r.get("organization"),
               "slop": r.get("slop"),
               "writing_score": r.get("writing_score")}
        for t in wanted:
            if t in _INDEX_OVERLAP:
                rec[t] = r.get(t)
                rec[f"_{t}_scale"] = "index percentile"
            elif t in (r.get("traits") or {}):
                rec[t] = r["traits"][t]
                rec[f"_{t}_scale"] = "trait Elo"
            else:
                rec[t] = r.get(t)          # index percentile fallback
                rec[f"_{t}_scale"] = "index percentile" if r.get(t) is not None else None
        out.append(rec)

    if sort_by:
        if sort_by not in out[0]:
            raise KeyError(f"cannot sort by {sort_by}; not in the selected traits")
        out.sort(key=lambda x: (x[sort_by] is None,
                                -(x[sort_by] if x[sort_by] is not None else 0)))
    return out


def print_traits(traits: tuple[str, ...], limit: int | None = None,
                 sort_by: str | None = None) -> None:
    rows = trait_table(traits=traits, sort_by=sort_by or traits[0])
    if limit:
        rows = rows[:limit]
    scales = {t: rows[0].get(f"_{t}_scale") for t in traits}
    print(f"{'model':<30}" + "".join(f"{t[:11]:>12}" for t in traits))
    print(f"{'scale':<30}" + "".join(f"{str(scales[t] or '-')[:11]:>12}" for t in traits))
    print("-" * (30 + 12 * len(traits)))
    for r in rows:
        print(f"{r['model'][:28]:<30}" +
              "".join(f"{(r[t] if r[t] is not None else float('nan')):>12.1f}"
                      for t in traits))


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1 and _sys.argv[1] == "traits":
        # usage: python -m resume_writing_v2.personalitybench traits eloquent slop
        want = tuple(_sys.argv[2:]) or ("eloquent", "lexicallyVaried", "scannable")
        print_traits(want, limit=15)
        raise SystemExit(0)
    rows = sorted(fetch_from_page(), key=lambda r: -r["writing_score"])
    path = save(rows)
    print(f"{len(rows)} models -> {path}\n")
    print("writing_score = (organization + (100 - slop)) / 2    [slop lower is better]")
    print(f"{'model':<40}{'writing':>9}{'org':>7}{'slop':>7}")
    print("-" * 64)
    for r in rows:
        print(f"{r['model'][:38]:<40}{r['writing_score']:>9.1f}"
              f"{r['organization']:>7.1f}{r['slop']:>7.1f}")
