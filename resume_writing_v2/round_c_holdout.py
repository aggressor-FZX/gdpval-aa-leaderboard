#!/usr/bin/env python3
"""Validate the new gates on 5 good models, on BOTH fixtures.

Two purposes:

  1. Confirm the four new checks (content gate, typed claims, ownership,
     preservation) do not break models that were already passing.

  2. Run the HOLDOUT fixture — a different domain and different metric shapes
     that no scorer was tuned against. A model that passes the tuning fixture
     but fails the holdout is a model we over-fitted to. That is the finding,
     not a bug to patch.

Reports both fixtures side by side so a gap is visible rather than averaged
away.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_writing_v2 import drafter_faithfulness as dfn
from resume_writing_v2 import grounding
from resume_writing_v2.config import (CATALOG_URL, OPENROUTER_URL,
                                      REQUEST_TIMEOUT_S, api_key)

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
OUT = os.path.join(RES, "holdout_validation.json")

RUNS = int(os.environ.get("RUNS", "3"))
BUDGET = float(os.environ.get("BUDGET", "0.60"))
DRY = os.environ.get("DRY", "0") == "1"

# The five that looked good in Test A AND passed every Test B run at 100%,
# chosen to span the price range rather than to flatter the cheapest.
MODELS = [
    ("qwen/qwen3.7-plus", "Qwen3.7 Plus", None),
    ("minimax/minimax-m3", "MiniMax-M3", None),
    ("xiaomi/mimo-v2.6-pro", "MiMo-V2.6-Pro", None),
    ("qwen/qwen3.6-35b-a3b", "Qwen3.6 35B A3B", None),
    ("z-ai/glm-5.3-flash", "GLM-5.3-Flash", None),
]

FIXTURES = {
    "tuning": {
        "experiences": dfn.FIXTURE_EXPERIENCES,
        "education": dfn.FIXTURE_EDUCATION,
        "certifications": dfn.FIXTURE_CERTIFICATIONS,
        "metrics": dfn.VERIFIED_METRICS,
        "job_ad": dfn.JOB_AD,
    },
    "holdout": {
        "experiences": dfn.HOLDOUT_EXPERIENCES,
        "education": dfn.HOLDOUT_EDUCATION,
        "certifications": dfn.HOLDOUT_CERTIFICATIONS,
        "metrics": dfn.HOLDOUT_VERIFIED_METRICS,
        "job_ad": dfn.HOLDOUT_JOB_AD,
    },
}


def prices() -> dict:
    r = requests.get(CATALOG_URL, timeout=90)
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


def call(mid: str, effort, system: str, user: str, key: str) -> dict:
    body = {
        "model": mid,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": 8192,
        "temperature": 0.3,
        "usage": {"include": True},
    }
    if effort:
        body["reasoning_effort"] = effort
    last = None
    for _ in range(2):
        try:
            r = requests.post(OPENROUTER_URL, json=body,
                              timeout=REQUEST_TIMEOUT_S,
                              headers={"Authorization": f"Bearer {key}",
                                       "Content-Type": "application/json"})
            if r.status_code == 200:
                d = r.json()
                u = d.get("usage") or {}
                return {"ok": True,
                        "text": d["choices"][0]["message"].get("content") or "",
                        "cost_usd": float(u.get("cost") or 0.0),
                        "completion_tokens": u.get("completion_tokens")}
            last = f"HTTP {r.status_code}: {r.text[:160]}"
            if r.status_code in (400, 401, 403, 404):
                break
        except Exception as e:                       # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
    return {"ok": False, "error": last, "text": "", "cost_usd": 0.0}


def score_all(text: str, fx: dict) -> dict:
    ledger = grounding.build_ledger(fx["experiences"], fx["metrics"])
    content = grounding.content_gate(text)
    truth = grounding.check_truth(text, ledger)
    faith = dfn.score_response(text, experiences=fx["experiences"],
                               verified_metrics=fx["metrics"],
                               plain_text=True)
    struct = dfn.score_structure(text, experiences=fx["experiences"],
                                 education=fx["education"],
                                 certifications=fx["certifications"])
    lost = grounding.check_preservation(ledger, text)
    passed = bool(content["ok"] and faith["clean"] and struct["structural_clean"]
                  and not lost and truth.passed)
    return {
        "words": content["words"],
        "content_ok": content["ok"],
        "content_problems": content["problems"],
        "faith_clean": faith["clean"],
        "struct_clean": struct["structural_clean"],
        "truth_verdict": truth.verdict,
        "tier_a": truth.tier_a[:5],
        "tier_b": truth.tier_b[:5],
        "lost_facts": lost,
        "pass": passed,
    }


def main() -> int:
    key = api_key()
    price = prices()

    # build prompts per fixture once
    prompts = {name: dfn.build_resume_prompts(
        experiences=fx["experiences"], education=fx["education"],
        certifications=fx["certifications"], job_ad=fx["job_ad"],
        verified_metrics=fx["metrics"])
        for name, fx in FIXTURES.items()}

    plan = [(mid, lab, eff, fname)
            for mid, lab, eff in MODELS
            for fname in FIXTURES
            for _ in range(RUNS)]
    print(f"{len(MODELS)} models x {len(FIXTURES)} fixtures x {RUNS} runs "
          f"= {len(plan)} requests | budget ${BUDGET:.2f}")
    if DRY:
        for mid, lab, eff, fname in plan[:6]:
            print(f"  {lab:22s} {fname:8s} effort={eff}")
        return 0

    spent = [0.0]
    lock = threading.Lock()
    results = []

    def work(mid, lab, eff, fname):
        system, user = prompts[fname]
        res = call(mid, eff, system, user, key)
        row = {"model_id": mid, "label": lab, "effort": eff,
               "fixture": fname, "ok": res["ok"],
               "cost_usd": res["cost_usd"],
               "completion_tokens": res.get("completion_tokens"),
               "price_in_1m": price.get(mid, (None, None))[0],
               "price_out_1m": price.get(mid, (None, None))[1]}
        if res["ok"] and res["text"].strip():
            row.update(score_all(res["text"], FIXTURES[fname]))
            row["text"] = res["text"]
        else:
            row["pass"] = False
            row["error"] = res.get("error") or "empty completion"
        return row

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {}
        for mid, lab, eff, fname in plan:
            if spent[0] >= BUDGET:
                continue
            futs[pool.submit(work, mid, lab, eff, fname)] = (lab, fname)
        for fut in as_completed(futs):
            lab, fname = futs[fut]
            row = fut.result()
            with lock:
                spent[0] += row.get("cost_usd") or 0.0
                results.append(row)
                n = len(results)
            mark = "PASS" if row["pass"] else "FAIL"
            why = ""
            if not row["pass"]:
                if not row.get("content_ok", True):
                    why = ",".join(row["content_problems"][:2])
                elif row.get("lost_facts"):
                    why = "lost:" + row["lost_facts"][0]["text"]
                elif row.get("tier_a"):
                    why = row["tier_a"][0]["reason"]
                else:
                    why = "faith/struct"
            print(f"  [{n:>2}/{len(plan)}] {lab[:20]:22s}{fname:8s}"
                  f"{mark} {why[:46]} ${row.get('cost_usd') or 0:.5f}",
                  flush=True)

    payload = {"meta": {"runs": RUNS, "models": len(MODELS),
                        "fixtures": list(FIXTURES),
                        "requests": len(results),
                        "spent_usd": round(spent[0], 5),
                        "budget_ceiling_usd": BUDGET,
                        "holdout_note": "holdout fixture was never used to "
                                        "tune any scorer"},
               "results": results}
    os.makedirs(RES, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=1)
    print(f"\nwrote {OUT}\nspent ${spent[0]:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
