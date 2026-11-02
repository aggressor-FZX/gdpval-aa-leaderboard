"""AA-PersonalityBench — the missing writing benchmark, extracted from AA's site.

CORRECTION TO AN EARLIER CLAIM IN THIS REPO
-------------------------------------------
I previously wrote that "Artificial Analysis publishes no writing benchmark",
based on the free v2 API exposing 18 evaluation fields with none writing-related.
That was WRONG. AA-PersonalityBench exists and measures exactly what a resume
writer needs. It is simply not in the v2 API.

WHERE THE DATA LIVES
--------------------
  * data.artificialanalysis.ai/api/v1/models (documented in AA's docs)
      -> 404 DEPLOYMENT_NOT_FOUND. The host does not resolve. Verified.
  * artificialanalysis.ai/api/v2/data/llms/models (the key we have)
      -> 200, 723 records, ZERO personality fields. Verified.
  * artificialanalysis.ai/models/<slug> (the website)
      -> the full leaderboard, embedded in the Next.js RSC flight payload.

So the website is the only reachable source. That is why this module scrapes.

WHAT THE SCORES MEAN
--------------------
8 index scores, all percentile ranks 1-100 (AA's own page text: "AA-PersonalityBench
scores are percentile ranks from 1 to 100"):

  expressiveness    how expressive / varied the prose is
  organization      how well-structured and scannable the writing is
  informativeness   information density
  transparency      self-explanation / candour
  warmth, conviction, imagination
  slop              filler avoidance — HIGHER IS BETTER

`slop` is exposed here as `slop_avoidance` because the direction is easy to get
backwards. Verified by cross-checking: DeepSeek V4.1 Flash = organization 100,
slop 40.6; Kimi K3.1 Pro = organization 87.625, slop 20.8. The two move with, not
against, each other, and AA's UI describes a LOWER slop number as cleaner output
while storing a HIGHER percentile as better. Treat the field as "slop avoidance
percentile" and state the direction wherever it is displayed.

EXTRACTION — WHY THE FIRST ATTEMPT WAS WRONG
--------------------------------------------
Every model page embeds the WHOLE leaderboard: ~41 `personalityBench` blocks.
Taking the first block gave a degenerate placeholder for every model
(`expressiveness/organization/... = 1`, `slop = 90.1`), which is why an earlier
run produced 200 identical rows all reading 1.0 / 90.1.

The owner of each block is the NEAREST PRECEDING `"name"` field. Verified: a
single page yields 40 models, and the values for Kimi K3.1 Pro
(organization 87.625, expressiveness 62.875, slop 20.8) match what that model's
own page reports.
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests

UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120 Safari/537.36")}
BASE = "https://artificialanalysis.ai/models"

INDEX_KEYS = ("expressiveness", "organization", "informativeness",
              "transparency", "warmth", "conviction", "imagination", "slop")

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "results", "personalitybench_cache.json")

# A degenerate placeholder block seen at the head of every payload.
# All-six-1.0 with slop 90.1 is a chart default, not a measurement.
_PLACEHOLDER_ORG = 1.0
_PLACEHOLDER_SLOP = 90.1


def _payload(html: str) -> str:
    """Concatenate and unescape the Next.js RSC flight chunks."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    return "".join(chunks).replace('\\\\"', '"').replace('\\"', '"')


def parse_leaderboard(s: str) -> dict[str, dict]:
    """Every model on the embedded leaderboard: name -> index scores.

    Each `personalityBench` block belongs to the nearest preceding `"name"`.
    Blocks whose `indexScores` block is missing or unparseable are skipped.
    """
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
        # drop the degenerate placeholder if it ever survives the name pairing
        if (rec["organization"] == _PLACEHOLDER_ORG
                and rec["slop"] == _PLACEHOLDER_SLOP):
            continue
        out.setdefault(name, rec)
    return out


def normalise(rows: dict[str, dict]) -> list[dict]:
    """Flatten to a list with slop renamed to slop_avoidance."""
    out = []
    for name, v in rows.items():
        out.append({
            "model": name,
            "expressiveness": v["expressiveness"],
            "organization": v["organization"],
            "informativeness": v["informativeness"],
            "transparency": v["transparency"],
            "warmth": v["warmth"],
            "conviction": v["conviction"],
            "imagination": v["imagination"],
            "slop_avoidance": v["slop"],
        })
    return out


def fetch_from_page(slug: str = "deepseek-v4-1-flash-non-reasoning",
                    timeout: int = 60) -> list[dict]:
    """One page carries the whole leaderboard, so a single fetch is enough."""
    r = requests.get(f"{BASE}/{slug}", headers=UA, timeout=timeout)
    r.raise_for_status()
    return normalise(parse_leaderboard(_payload(r.text)))


def fetch_merged(slugs: list[str] | None = None, timeout: int = 60,
                 verbose: bool = True) -> list[dict]:
    """Union of several pages, in case any page's payload is stale/partial."""
    slugs = slugs or ["deepseek-v4-1-flash-non-reasoning",
                      "kimi-k3-1-pro", "minimax-m3-1-flash"]
    merged: dict[str, dict] = {}
    for sl in slugs:
        try:
            rows = {r["model"]: r for r in fetch_from_page(sl, timeout)}
        except requests.RequestException as e:
            if verbose:
                print(f"  {sl}: {type(e).__name__}")
            continue
        added = 0
        for k, v in rows.items():
            if k not in merged:
                merged[k] = v
                added += 1
        if verbose:
            print(f"  {sl:38} page rows={len(rows):3} new={added:3} total={len(merged):3}")
    return sorted(merged.values(), key=lambda r: -(r["organization"] or 0))


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


if __name__ == "__main__":
    rows = fetch_merged()
    path = save(rows)
    print(f"\n{len(rows)} models with AA-PersonalityBench -> {path}\n")
    hdr = ("model", "organization", "expressiveness", "slop_avoidance",
           "informativeness", "transparency")
    print(f"{'model':<44}" + "".join(f"{h[:11]:>13}" for h in hdr[1:]))
    print("-" * 112)
    for r in rows:
        print(f"{r['model'][:42]:<44}" +
              "".join(f"{(r[h] if r[h] is not None else float('nan')):>13.1f}"
                      for h in hdr[1:]))
