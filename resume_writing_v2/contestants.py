#!/usr/bin/env python3
"""Build the competitor set for the cheap-model writing contest.

Scope decision: the question is "do cheap models beat DeepSeek V4.1 Flash at
resume writing, and is the gap worth the price?" So the set is:

  * every model with OUTPUT price <= $2/M that has a reachable OpenRouter id
  * DeepSeek V4.1 Flash as the explicit benchmark target (it is the incumbent
    in the Cogito Metric pipeline)

Prices are read live from the OpenRouter catalog, not hardcoded, because v4
hardcoded them and four of its nine models no longer existed at those prices.
"""
from __future__ import annotations

import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_writing_v2 import shortlist
from resume_writing_v2.config import ModelEntry, aa_key

MAX_OUTPUT_PER_1M = 2.00
TARGET = "deepseek/deepseek-v4.1-flash"

# Reasoning variants of one model are the SAME writing model; including all four
# effort levels of Qwen3.8 27B would burn budget re-measuring one model. Keep the
# best-effort variant per family.
_FAMILY_PREFIX = ("qwen3.8 27b", "qwen3.6 35b", "gemma 4 26b", "qwen3.5 9b",
                  "gpt-oss-120b", "gpt-oss-20b")


def live_output_prices() -> dict[str, tuple[float, float]]:
    r = requests.get("https://openrouter.ai/api/v1/models", timeout=90)
    r.raise_for_status()
    out = {}
    for m in r.json().get("data", []):
        p = m.get("pricing") or {}
        try:
            out[m["id"]] = (float(p.get("prompt") or 0) * 1e6,
                            float(p.get("completion") or 0) * 1e6)
        except (TypeError, ValueError):
            pass
    return out


def build(max_out: float = MAX_OUTPUT_PER_1M, verbose: bool = True) -> list[ModelEntry]:
    rows = shortlist.attach_personality(shortlist.build(aa_key()))
    prices = live_output_prices()

    chosen: list[ModelEntry] = []
    seen_family: set[str] = set()

    for r in rows:
        oid = r["or_id"]
        pin, pout = prices.get(oid, (None, None))
        if pout is None or pout <= 0 or pout > max_out:
            continue
        # one effort variant per family
        base = r["aa_name"].split("(")[0].strip().lower()
        if any(base.startswith(p) for p in _FAMILY_PREFIX):
            if base in seen_family:
                continue
            seen_family.add(base)
        chosen.append(ModelEntry(
            model_id=oid, label=r["aa_name"], effort=None,
            group="cheap<=$2/M", max_tokens=16384))

    # always include the incumbent target
    if not any(e.model_id == TARGET for e in chosen):
        pin, pout = prices.get(TARGET, (None, None))
        chosen.append(ModelEntry(model_id=TARGET,
                                 label="DeepSeek V4.1 Flash (incumbent)",
                                 effort=None, group="incumbent", max_tokens=16384))

    if verbose:
        print(f"{'model':<40}{'out $/M':>9}{'writing':>9}{'source':<22}")
        print("-" * 84)
        for e in chosen:
            row = next((r for r in rows if r["or_id"] == e.model_id), {})
            pout = prices.get(e.model_id, (None, None))[1]
            print(f"{e.label[:38]:<40}{(f'{pout:.2f}' if pout else '-'):>9}"
                  f"{row.get('writing_score', float('nan')):>9.1f}"
                  f"{str(row.get('writing_source', ''))[:20]:<22}")
        print(f"\n{len(chosen)} competitors (output <= ${max_out:.2f}/M + incumbent)")
    return chosen


if __name__ == "__main__":
    build()   # prints the competitor set; consumers call build() directly
