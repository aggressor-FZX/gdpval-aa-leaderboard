#!/usr/bin/env python3
"""Test B (full-resume) across every measured model.

Two questions, scored separately and never merged:

  1. FAITHFULNESS  — the original contract. No invented technology, no invented
     company, numbers only from the verified list, unit attached.
  2. STRUCTURE     — the contract a full resume needs and bullets alone cannot
     express: required sections, reverse-chronological order, employment dates
     copied exactly, education years exact, certification dates exact, and
     ATS-parseable plain text.

The overall `pass` requires BOTH. A beautifully formatted resume with an invented
graduation year fails, and so does a factually clean one that reorders jobs.

Variants: the unit is `(model_id, reasoning_effort)`, and the effort is the SAME
one Test A measured, so a row here and a row in `RESULTS.md` §2 describe the same
configuration. Excluded deliberately: the five variants Test A found significantly
worse than the incumbent at a high price (Claude Haiku 5.5 high, Kimi K3.1 Pro,
Grok 4.7 xhigh, Grok 4.6 xhigh, GPT-6 Luna xhigh) — no point spending on them.

Cost is small: this emits ~500 tokens, not ~3000, so 3 runs each is a few cents.
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
from resume_writing_v2.config import (CATALOG_URL, OPENROUTER_URL,
                                      REQUEST_TIMEOUT_S, api_key)

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
CONSOLIDATED = os.path.join(RES, "consolidated.json")
OUT = os.path.join(RES, "drafter_fullresume.json")

RUNS = int(os.environ.get("RUNS", "3"))
BUDGET = float(os.environ.get("BUDGET", "2.00"))
MAX_WORKERS = 4
DRY = os.environ.get("DRY", "0") == "1"
RESCORE = os.environ.get("RESCORE", "0") == "1"

# Variants Test A found significantly worse than the incumbent at a premium.
EXCLUDE_LABELS = {
    "Claude Haiku 5.5 (max)",
    "Kimi K3.1 Pro",
    "Grok 4.7 (xhigh)",
    "Grok 4.6 (xhigh)",
    "GPT-6 Luna (max)",
}

# Small-context models cannot hold the full prompt plus 1600 output tokens.
JD_CAP = {"openai/gpt-3.5-turbo-0613": 700}
MAX_TOK_CAP = {"openai/gpt-3.5-turbo-0613": 1200}


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


def variants() -> list[dict]:
    """One entry per (model_id, effort), effort as Test A measured it."""
    rows = json.load(open(CONSOLIDATED))["rows"]
    seen: dict[tuple, dict] = {}
    for r in rows:
        if r["mean"] is None:
            continue
        if r["label"] in EXCLUDE_LABELS:
            continue
        key = (r["model_id"], r["effort"])
        if key in seen:
            continue
        seen[key] = {"model_id": r["model_id"], "label": r["label"],
                     "effort": r["effort"], "test_a": r["mean"],
                     "test_a_cost": r["cost_per_run"]}
    return sorted(seen.values(), key=lambda v: v["label"])


def call(v: dict, system: str, user: str, key: str) -> dict:
    body = {
        "model": v["model_id"],
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "max_tokens": MAX_TOK_CAP.get(v["model_id"], 8192),
        "temperature": 0.3,                  # the drafter's own temperature
        "usage": {"include": True},
    }
    if v["effort"]:
        body["reasoning_effort"] = v["effort"]
    last = None
    for attempt in range(2):
        try:
            r = requests.post(OPENROUTER_URL, json=body, timeout=REQUEST_TIMEOUT_S,
                              headers={"Authorization": f"Bearer {key}",
                                       "Content-Type": "application/json"})
            if r.status_code == 200:
                d = r.json()
                msg = d["choices"][0]["message"]
                u = d.get("usage") or {}
                return {"ok": True, "text": msg.get("content") or "",
                        "provider": d.get("provider"),
                        "cost_usd": float(u.get("cost") or 0.0),
                        "completion_tokens": u.get("completion_tokens"),
                        "reasoning_tokens": ((u.get("completion_tokens_details")
                                              or {}).get("reasoning_tokens"))}
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code in (400, 401, 403, 404):
                break
        except Exception as e:                      # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
    return {"ok": False, "error": last, "text": "", "cost_usd": 0.0}


def rescore() -> int:
    """Re-score every saved response with the CURRENT scorer, no API calls.

    Needed because a run can finish under a scorer that is later corrected:
    one such run stored `structural_clean: false` for 45 responses that the
    fixed scorer accepts. Responses are immutable evidence; only the scoring
    should be refreshed.
    """
    d = json.load(open(OUT))
    changed = 0
    for r in d["results"]:
        if not (r.get("ok") and r.get("text")):
            continue
        old = (r.get("faith", {}).get("clean"),
               r.get("struct", {}).get("structural_clean"))
        r["faith"] = dfn.score_response(r["text"], plain_text=True)
        r["struct"] = dfn.score_structure(r["text"])
        r["pass"] = bool(r["faith"]["clean"] and r["struct"]["structural_clean"])
        if (r["faith"]["clean"], r["struct"]["structural_clean"]) != old:
            changed += 1
    d["meta"]["rescored_at"] = "explicit rescore pass"
    d["meta"]["rescored_changed"] = changed
    with open(OUT, "w") as f:
        json.dump(d, f, indent=1)
    print(f"rescored {len(d['results'])} rows; {changed} verdicts changed")
    return 0


def main() -> int:
    if RESCORE:
        return rescore()
    vs = variants()
    print(f"{len(vs)} variants x {RUNS} runs; "
          f"excluded {len(EXCLUDE_LABELS)} bad-value variants")
    if DRY:
        for v in vs:
            print(f"  {v['model_id']:44s} effort={str(v['effort']):6s} "
                  f"test_a={v['test_a']}")
        return 0

    key = api_key()
    price = prices()
    system, user = dfn.build_resume_prompts()

    # per-model prompt, so small-context models get a trimmed JD
    prompts = {}
    for v in vs:
        cap = JD_CAP.get(v["model_id"])
        prompts[v["model_id"]] = dfn.build_resume_prompts(
            job_ad=dfn.JOB_AD[:cap] if cap else dfn.JOB_AD)

    plan = [(v, i) for v in vs for i in range(1, RUNS + 1)]
    print(f"running {len(plan)} requests | budget ${BUDGET:.2f}")

    spent = [0.0]
    lock = threading.Lock()
    results = []

    def work(v, run_i):
        sysmsg, usrmsg = prompts[v["model_id"]]
        res = call(v, sysmsg, usrmsg, key)
        row = {"model_id": v["model_id"], "label": v["label"],
               "effort": v["effort"], "run": run_i,
               "test_a_mean": v["test_a"],
               "price_in_1m": price.get(v["model_id"], (None, None))[0],
               "price_out_1m": price.get(v["model_id"], (None, None))[1]}
        row.update({k: res.get(k) for k in
                    ("ok", "error", "provider", "cost_usd",
                     "completion_tokens", "reasoning_tokens")})
        if res["ok"] and res["text"].strip():
            # plain_text=True: this variant emits a resume document, not JSON.
            # Without the flag every response failed schema_ok and looked like
            # a fabrication failure by all 43 variants.
            row["faith"] = dfn.score_response(res["text"], plain_text=True)
            row["struct"] = dfn.score_structure(res["text"])
            row["pass"] = bool(row["faith"]["clean"]
                               and row["struct"]["structural_clean"])
            row["text"] = res["text"]
        else:
            row["ok"] = False
            row["pass"] = False
            row["error"] = row.get("error") or "empty completion"
        return row

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {}
        for v, i in plan:
            with lock:
                if spent[0] >= BUDGET:
                    print(f"  budget ceiling reached, skipping {v['label']}")
                    continue
            futs[pool.submit(work, v, i)] = (v, i)
        for fut in as_completed(futs):
            v, i = futs[fut]
            row = fut.result()
            with lock:
                spent[0] += row.get("cost_usd") or 0.0
                results.append(row)
                n = len(results)
            print(f"  [{n:>3}/{len(plan)}] {row['label'][:30]:<32}"
                  f"{str(v['effort'] or '-'):<7}"
                  f"{'OK ' if row['ok'] else 'ERR'} "
                  f"faith={'clean' if row.get('faith', {}).get('clean') else 'no ':<5}"
                  f"struct={'clean' if row.get('struct', {}).get('structural_clean') else 'no ':<5}"
                  f"${row.get('cost_usd') or 0:.5f}", flush=True)

    payload = {"meta": {"runs": RUNS, "variants": len(vs),
                        "requests": len(plan), "completed": len(results),
                        "spent_usd": round(spent[0], 5),
                        "budget_ceiling_usd": BUDGET,
                        "excluded": sorted(EXCLUDE_LABELS),
                        "excluded_reason": "Test A: significantly worse than the "
                                           "incumbent at a higher price per run"},
               "results": results}
    os.makedirs(RES, exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=1)
    print(f"\nwrote {OUT}\nspent ${spent[0]:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
