"""OpenRouter runner: bounded concurrency, hard spend ceiling, full logging.

Improvements over v4:
  * real pricing read from the live catalog at run time (v4 hardcoded prices)
  * `usage.cost` recorded from every response (v4 estimated)
  * bounded concurrency via ThreadPoolExecutor (v4 was sequential)
  * a hard MAX_SPEND_USD ceiling — the runner refuses to submit more work once
    the accumulated cost would cross it, instead of discovering the overrun in
    the results file
  * every failure is captured with its exception text, never silently dropped
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .config import (OPENROUTER_URL, CATALOG_URL, RUNS_PER_MODEL, MAX_SPEND_USD,
                     MAX_CONCURRENCY, REQUEST_TIMEOUT_S, RETRIES, api_key)
from .scoring import score


def _price_index() -> dict:
    """OpenRouter id -> (prompt $/1M, completion $/1M). Live, not hardcoded."""
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


def _call(entry, prompt: str, system: str, key: str) -> dict:
    """One completion. Always returns a dict; failure is a field, not an exception."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = entry.request_body(prompt, system)
    last_err = None
    for attempt in range(RETRIES + 1):
        t0 = time.time()
        try:
            r = requests.post(OPENROUTER_URL, headers=headers, json=body,
                              timeout=REQUEST_TIMEOUT_S)
            dt = time.time() - t0
            if r.status_code == 200:
                d = r.json()
                msg = d["choices"][0]["message"]
                usage = d.get("usage") or {}
                return {
                    "ok": True,
                    "text": msg.get("content") or "",
                    "provider": d.get("provider"),
                    "latency_s": round(dt, 2),
                    "usage": usage,
                    "cost_usd": float(usage.get("cost") or 0.0),
                    "attempt": attempt,
                }
            last_err = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code in (400, 401, 403, 404):
                break                      # not retryable
        except Exception as e:              # noqa: BLE001 - recorded, not swallowed
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * (attempt + 1))
    return {"ok": False, "error": last_err, "text": "", "cost_usd": 0.0,
            "latency_s": None, "usage": {}, "provider": None}


def run(entries, prompt: str, system: str, runs: int = RUNS_PER_MODEL,
        budget_usd: float = MAX_SPEND_USD, out_path: str | None = None,
        dry_run: bool = False) -> dict:
    """Run the competition. Returns the full results structure."""
    key = api_key()
    prices = _price_index()

    plan = []
    for e in entries:
        pin, pout = prices.get(e.model_id, (None, None))
        for i in range(runs):
            plan.append((e, i + 1, pin, pout))

    if dry_run:
        print(f"DRY RUN — {len(entries)} models × {runs} runs = {len(plan)} requests")
        print(f"{'model':<46}{'effort':<8}{'in $/M':>9}{'out $/M':>9}  available")
        print("-" * 84)
        for e in entries:
            pin, pout = prices.get(e.model_id, (None, None))
            avail = "yes" if pin is not None else "NOT IN CATALOG"
            print(f"{e.model_id[:44]:<46}{str(e.effort or '-'):<8}"
                  f"{(f'{pin:.2f}' if pin is not None else '-'):>9}"
                  f"{(f'{pout:.2f}' if pout is not None else '-'):>9}  {avail}")
        print(f"\nBudget ceiling: ${budget_usd:.2f} | concurrency {MAX_CONCURRENCY}")
        print("No API calls made.")
        return {"dry_run": True, "plan": len(plan)}

    print(f"Running {len(plan)} requests | budget ceiling ${budget_usd:.2f} "
          f"| concurrency {MAX_CONCURRENCY}")
    spent = 0.0
    results = []
    skipped = 0
    lock_free_total = [0.0]      # single-thread accumulation is safe enough for a ceiling

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {}
        for e, run_i, pin, pout in plan:
            if lock_free_total[0] >= budget_usd:
                skipped += 1
                continue
            futures[pool.submit(_call, e, prompt, system, key)] = (e, run_i, pin, pout)

        for fut in as_completed(futures):
            e, run_i, pin, pout = futures[fut]
            res = fut.result()
            spent += res["cost_usd"]
            lock_free_total[0] = spent
            row = {
                "model_id": e.model_id, "label": e.label, "effort": e.effort,
                "group": e.group, "run": run_i,
                "price_in_1m": pin, "price_out_1m": pout,
                "ok": res["ok"], "error": res.get("error"),
                "provider": res.get("provider"),
                "latency_s": res.get("latency_s"),
                "cost_usd": res["cost_usd"],
                "tokens": (res.get("usage") or {}).get("total_tokens"),
                "prompt_tokens": (res.get("usage") or {}).get("prompt_tokens"),
                "completion_tokens": (res.get("usage") or {}).get("completion_tokens"),
                "reasoning_tokens": ((res.get("usage") or {})
                                     .get("completion_tokens_details") or {}
                                     ).get("reasoning_tokens"),
            }
            if res["ok"] and res["text"].strip():
                sc = score(res["text"])
                row["score"] = sc["total"]
                row["raw_total"] = sc["raw_total"]
                row["clamped"] = sc["clamped"]
                row["band"] = sc["band"]
                row["categories"] = sc["categories"]
                row["gates"] = {
                    "critical_fails": sc["gates"]["critical_fails"],
                    "non_critical_fails": sc["gates"]["non_critical_fails"],
                    "detail": sc["gates"]["detail"],
                    "all_passed": sc["gates"]["all_passed"],
                }
                row["text"] = res["text"]
            else:
                # Distinguish "reasoning consumed the whole budget" from a real
                # transport failure. Both are unscorable, but they need
                # different fixes: more headroom vs retry/investigate.
                rt = row.get("reasoning_tokens") or 0
                ct_ = row.get("completion_tokens") or 0
                if res["ok"] and rt and ct_ and rt >= ct_ * 0.95:
                    row["error"] = (f"reasoning_exhausted_budget: {rt} reasoning of "
                                    f"{ct_} completion tokens, no answer emitted. "
                                    f"Raise max_tokens (now {e.max_tokens}).")
                    row["unscorable_reason"] = "reasoning_exhausted"
                elif res["ok"]:
                    row["error"] = "empty completion"
                    row["unscorable_reason"] = "empty_completion"
                row["ok"] = False
            results.append(row)
            print(f"  [{len(results):>2}/{len(plan)}] {e.label[:34]:<36} "
                  f"run{run_i} {'OK ' if row['ok'] else 'ERR'} "
                  f"score={row.get('score', '-')} ${row['cost_usd']:.5f}")

    payload = {
        "meta": {
            "runs_per_model": runs,
            "models": len(entries),
            "requests_planned": len(plan),
            "requests_skipped_budget": skipped,
            "spent_usd": round(spent, 5),
            "budget_ceiling_usd": budget_usd,
        },
        "results": results,
    }
    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(payload, f, indent=1)
        print(f"\nwrote {out_path}")
    if skipped:
        print(f"BUDGET CEILING HIT — {skipped} request(s) were not submitted.")
    return payload
