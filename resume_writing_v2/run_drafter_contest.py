#!/usr/bin/env python3
"""Drafter faithfulness contest: incumbent qwen3-coder vs heavyweight candidates.

Candidates named by the user: Claude Haiku, MiniMax 3.1 Flash, GLM 5.3,
Kimi K3.1. Each is a "heavy but not SOTA" option, which is exactly the right
place to look for a drafter: the drafter needs instruction-following and
restraint, not maximum intelligence.

Scored on the DRAFTER's actual constraints, not prose quality:
  fabrication (tech/company invented), metric fidelity (numbers + units),
  JSON schema, bullet length band, strong-verb starts, company coverage.

A model that writes beautiful bullets and invents "reduced latency 65%" FAILS.
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from resume_writing_v2 import drafter_faithfulness as dfn
from resume_writing_v2.config import ModelEntry, api_key

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "results", "drafter_faithfulness.json")

MODELS = [
    ("qwen/qwen3-coder", "Qwen3 Coder (INCUMBENT)", "incumbent"),
    ("anthropic/claude-haiku-5.5", "Claude Haiku 5.5", "candidate"),
    ("minimax/minimax-m3.1-flash", "MiniMax M3.1 Flash", "candidate"),
    ("z-ai/glm-5.3", "GLM 5.3", "candidate"),
    ("moonshotai/kimi-k3.1-pro", "Kimi K3.1 Pro", "candidate"),
]
RUNS = 4
URL = "https://openrouter.ai/api/v1/chat/completions"


def prices() -> dict:
    r = requests.get("https://openrouter.ai/api/v1/models", timeout=90)
    out = {}
    for m in r.json()["data"]:
        p = m.get("pricing") or {}
        try:
            out[m["id"]] = (float(p.get("prompt") or 0) * 1e6,
                            float(p.get("completion") or 0) * 1e6)
        except (TypeError, ValueError):
            pass
    return out


def main() -> int:
    key = api_key()
    price = prices()
    system, user = dfn.build_prompts()
    results = []

    for mid, label, group in MODELS:
        pin, pout = price.get(mid, (None, None))
        print(f"\n=== {label} ===")
        for i in range(1, RUNS + 1):
            body = {
                "model": mid,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                # drafter sends max_tokens=6000; give reasoning room on top
                "max_tokens": 16384,
                "temperature": 0.3,      # TEMPERATURES["drafter"]
                "usage": {"include": True},
            }
            try:
                r = requests.post(URL, json=body, timeout=240,
                                  headers={"Authorization": f"Bearer {key}",
                                           "Content-Type": "application/json"})
                if r.status_code != 200:
                    print(f"  run{i} HTTP {r.status_code}: {r.text[:110]}")
                    results.append({"model": mid, "label": label, "group": group,
                                    "run": i, "ok": False,
                                    "error": f"HTTP {r.status_code}"})
                    continue
                d = r.json()
                txt = d["choices"][0]["message"].get("content") or ""
                u = d.get("usage") or {}
                sc = dfn.score_response(txt)
                sc.update({"model": mid, "label": label, "group": group,
                           "run": i, "ok": True, "provider": d.get("provider"),
                           "cost_usd": float(u.get("cost") or 0.0),
                           "completion_tokens": u.get("completion_tokens"),
                           "reasoning_tokens": (u.get("completion_tokens_details")
                                                or {}).get("reasoning_tokens"),
                           "text": txt})
                results.append(sc)
                print(f"  run{i} clean={sc['clean']!s:<5} bullets={sc['n_bullets']:<3}"
                      f" fab={len(sc['fabricated_tech'])} badnum={len(sc['bad_numbers'])}"
                      f" band={sc['in_band_pct']:.0f}% strong={sc['strong_start_pct']:.0f}%"
                      f" cov={sc['company_coverage']} ${sc['cost_usd']:.5f}")
            except Exception as e:                       # noqa: BLE001
                print(f"  run{i} ERROR {type(e).__name__}: {e}")
                results.append({"model": mid, "label": label, "group": group,
                                "run": i, "ok": False, "error": str(e)[:120]})

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"results": results}, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")

    # ── summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 110)
    print("DRAFTER FAITHFULNESS SUMMARY")
    print("=" * 110)
    by: dict[str, list[dict]] = {}
    for r in results:
        by.setdefault(r["label"], []).append(r)
    print(f"{'model':<26}{'runs':>5}{'clean':>7}{'fab':>6}{'badnum':>8}"
          f"{'schema':>8}{'band%':>7}{'strong%':>9}{'cov':>6}{'$/run':>10}")
    print("-" * 110)
    for lab, rs in by.items():
        ok = [r for r in rs if r.get("ok")]
        if not ok:
            print(f"{lab:<26}{len(rs):>5}{'0':>7}  all runs failed")
            continue
        clean = sum(1 for r in ok if r["clean"])
        fab = sum(len(r["fabricated_tech"]) + len(r["fabricated_company"]) for r in ok)
        bad = sum(len(r["bad_numbers"]) + len(r["unit_stripped"]) for r in ok)
        schema = sum(1 for r in ok if r["schema_ok"])
        band = st.mean([r["in_band_pct"] for r in ok])
        strong = st.mean([r["strong_start_pct"] for r in ok])
        covs = [r["company_coverage"] for r in ok]
        cost = st.mean([r["cost_usd"] for r in ok])
        print(f"{lab:<26}{len(ok):>5}{f'{clean}/{len(ok)}':>7}{fab:>6}{bad:>8}"
              f"{f'{schema}/{len(ok)}':>8}{band:>7.0f}{strong:>9.0f}"
              f"{covs[0]:>6}{cost:>10.5f}")

    print("\nVerdict rule: a drafter is only viable if fabrication == 0 across all")
    print("clean runs AND metrics stay attached to units. Prose quality is not scored:")
    print("the drafter's job is fidelity, and a fluent fabricator is worse than a")
    print("plain faithful one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
