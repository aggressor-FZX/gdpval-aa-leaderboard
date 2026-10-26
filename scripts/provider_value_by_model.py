"""
Provider value engine — "which provider is the better VALUE for this model?"

WHY THIS EXISTS
---------------
The notebook's efficiency metrics use AA's published `median_output_tokens_per_second`
as speed and AA's listed blended price as cost. But on OpenRouter a model is served by
dozens of endpoints with very different measured throughput and price. AA's number is
one lab measurement; what you actually get is whichever endpoint the router picks.

This script answers, per model:
  1. What does the provider ladder look like? (price, measured tok/s, quant, ctx, uptime)
  2. Which provider is the best VALUE?  ->  value = sqrt(tps) / blended_price
     (sqrt because the notebook's multiplicative metric uses sqrt(throughput))
  3. How does that compare to the DEFAULT (cheapest) provider the router would pick?

QUALITY GATES (a provider is only eligible if it clears all of them)
--------------------------------------------------------------------
  - measured throughput > 0            (no speed data => cannot rank on speed)
  - uptime_last_30m >= 95              (unreliable endpoints are not "value")
  - context_length >= 100_000          (must handle real prompts)
  - quantization not in {fp4, mxfp4}   (lossy quant is what failed the long-context
                                        probes in the stealth test; fp8/unknown pass)

If no endpoint clears the gates, we fall back to the best raw value and flag it.

OUTPUT
------
provider_value_by_model.json  ->  {model: {aa: {...}, ladder: [...], chosen: {...},
                                           default: {...}, next_up: {...}}}
"""

import os, json, re, time
import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv()

AA_KEY = os.getenv("ARTIFICIAL_ANALYSIS_KEY")
OR_KEY = os.getenv("OPENROUTER_API_KEY_1")
if not AA_KEY or not OR_KEY:
    raise SystemExit("Need ARTIFICIAL_ANALYSIS_KEY and OPENROUTER_API_KEY_1 in .env")

AA_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"
OR_H = {"Authorization": f"Bearer {OR_KEY}"}

TOKEN_RE = re.compile(r"[a-z]+|\d+(?:\.\d+)*")
STOP = {"the", "a", "of", "in", "on", "z", "ai", "preview", "beta", "latest",
        "max", "high", "xhigh", "medium", "low", "default", "fallback",
        "reasoning", "effort", "adaptive", "non"}

LOSSY_QUANT = {"fp4", "mxfp4"}
MIN_UPTIME = 95.0
MIN_CTX = 100_000
ABOVE44_INTEL = 44.0
TOP_N_ORIGINAL = 20


# ------------------------------------------------------------ AA data ----
def load_aa():
    r = requests.get(AA_URL, headers={"x-api-key": AA_KEY}, timeout=90)
    r.raise_for_status()
    raw = r.json()
    recs = raw["data"] if isinstance(raw, dict) and "data" in raw else raw
    rows = []
    for m in recs:
        ev = m.get("evaluations") or {}
        pr = m.get("pricing") or {}
        rows.append({
            "Model": m.get("name"),
            "intel": ev.get("artificial_analysis_intelligence_index"),
            "ifbench": ev.get("ifbench"),
            "hle": ev.get("hle"),
            "tps_aa": m.get("median_output_tokens_per_second"),
            "price_blend": pr.get("price_1m_blended_3_to_1"),
            "price_in": pr.get("price_1m_input_tokens"),
            "price_out": pr.get("price_1m_output_tokens"),
        })
    df = pd.DataFrame(rows)
    for c in ["intel", "ifbench", "hle", "tps_aa", "price_blend", "price_in", "price_out"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["tps_aa"] = df["tps_aa"].where(df["tps_aa"] > 0, np.nan)
    # IMPORTANT: match the notebook's price derivation exactly.
    # The notebook computes blended from in/out first, then falls back to the
    # API's own blended column. Using the API column alone gives different
    # prices and therefore a different top-20, so mirror the notebook here.
    _derived = (df["price_in"].fillna(0) * 3 + df["price_out"].fillna(0)) / 4
    _api = df["price_blend"].fillna(0)
    df["price_blend"] = _derived.where(_derived > 0, _api)
    df["price_blend"] = df["price_blend"].where(df["price_blend"] > 0, np.nan)
    # IMPORTANT: match the notebook's reliability convention exactly.
    # The notebook sets AA_Hallucination_Rate = 1 - IFBench, then
    # Reliability_Factor = 1 - AA_Hallucination_Rate = IFBench.
    # So reliability IS the IFBench score (fallback HLE), not 1 - IFBench.
    df["reliab"] = df["ifbench"].fillna(df["hle"])
    return df


# ------------------------------------------------------- OR matching ----
def tokens(s):
    s = re.sub(r"\([^)]*\)", " ", str(s or "").lower())
    return set(TOKEN_RE.findall(s)) - STOP


def jaccard(a, b):
    return len(a & b) / len(a | b) if (a | b) else 0.0


def load_or_catalog():
    r = requests.get("https://openrouter.ai/api/v1/models", headers=OR_H, timeout=90)
    r.raise_for_status()
    return [m for m in r.json().get("data", [])
            if not any(x in m.get("id", "") for x in (":free", ":batch", ":nitro"))
            and not m.get("id", "").startswith("~")]


def match_slug(aa_name, catalog, min_j=0.8):
    q = tokens(aa_name)
    best, best_j = None, 0.0
    for m in catalog:
        mid = m.get("id", "")
        j = max(jaccard(q, tokens(mid.split("/")[-1])), jaccard(q, tokens(m.get("name"))))
        if j > best_j:
            best, best_j = mid, j
    return (best, best_j) if best_j >= min_j else (None, best_j)


# --------------------------------------------------------- endpoints ----
def fetch_endpoints(slug):
    r = requests.get(f"https://openrouter.ai/api/v1/models/{slug}/endpoints",
                     headers=OR_H, timeout=60)
    if r.status_code != 200:
        return []
    eps = r.json().get("data", {}).get("endpoints", [])
    out = []
    for e in eps:
        p = e.get("pricing", {}) or {}
        try:
            pi = float(p.get("prompt", 0) or 0)
            po = float(p.get("completion", 0) or 0)
        except (TypeError, ValueError):
            pi = po = 0.0
        t = e.get("throughput_last_30m")
        tps = t.get("p50") if isinstance(t, dict) else None
        try:
            tps = float(tps) if tps else np.nan
        except (TypeError, ValueError):
            tps = np.nan
        out.append({
            "provider": e.get("provider_name") or e.get("name") or "unknown",
            "price_in": pi * 1_000_000,
            "price_out": po * 1_000_000,
            "price_blend": (pi * 3 + po) / 4 * 1_000_000,
            "tps": tps,
            "quant": e.get("quantization"),
            "ctx": e.get("context_length"),
            "uptime": e.get("uptime_last_30m"),
            "max_completion": e.get("max_completion_tokens"),
        })
    return out


def gate_reasons(e):
    """Return list of reasons this endpoint fails the quality gates."""
    why = []
    tps = e.get("tps")
    if tps is None or (isinstance(tps, float) and np.isnan(tps)) or tps <= 0:
        why.append("no speed data")
    up = e.get("uptime")
    if up is not None and up < MIN_UPTIME:
        why.append(f"uptime {up:.0f}%")
    ctx = e.get("ctx")
    if ctx is not None and ctx < MIN_CTX:
        why.append(f"ctx {ctx:,}")
    q = str(e.get("quant") or "").lower()
    if q in LOSSY_QUANT:
        why.append(f"lossy quant {q}")
    return why


def score_endpoint(e):
    """value = sqrt(tps) / blended_price  (matches the notebook's sqrt(throughput))."""
    tps = e.get("tps")
    price = e.get("price_blend")
    if not tps or not price or price <= 0 or np.isnan(tps):
        return np.nan
    return float(np.sqrt(tps) / price)


def analyse_model(name, aa_row, catalog):
    slug, j = match_slug(name, catalog)
    if not slug:
        return {"aa": aa_row, "slug": None, "jaccard": round(j, 2),
                "ladder": [], "chosen": None, "default": None, "next_up": None,
                "note": "no OpenRouter match"}

    eps = fetch_endpoints(slug)
    if not eps:
        return {"aa": aa_row, "slug": slug, "jaccard": round(j, 2),
                "ladder": [], "chosen": None, "default": None, "next_up": None,
                "note": "no endpoints returned"}

    for e in eps:
        e["value"] = score_endpoint(e)
        e["gates_failed"] = gate_reasons(e)
        e["eligible"] = len(e["gates_failed"]) == 0

    priced = [e for e in eps if e.get("price_blend") and e["price_blend"] > 0]
    priced.sort(key=lambda e: e["price_blend"])

    # DEFAULT = what the router picks when optimising on price.
    # The stealth test showed the router optimises on PROMPT price, not blended:
    # for deepseek-v4.1-flash it picked OpenInference at $0.02/M input even
    # though its blended price ($0.265) was 12th cheapest. So default = cheapest
    # prompt price, with cheapest blended kept as a reference column.
    by_prompt = sorted([e for e in priced if e.get("price_in", 0) > 0],
                       key=lambda e: e["price_in"])
    default = by_prompt[0] if by_prompt else (priced[0] if priced else None)
    default_by_blend = priced[0] if priced else None

    # NEXT UP = next distinct provider above the default in prompt-price order.
    next_up = None
    if default is not None:
        for e in by_prompt[1:]:
            if e["provider"] != default["provider"]:
                next_up = e
                break

    # BEST VALUE = highest sqrt(tps)/price among gate-passing endpoints.
    eligible = [e for e in eps if e["eligible"] and not np.isnan(e["value"])]
    if eligible:
        chosen = max(eligible, key=lambda e: e["value"])
        chosen_note = "best value (passed all gates)"
    else:
        scored = [e for e in eps if not np.isnan(e["value"])]
        chosen = max(scored, key=lambda e: e["value"]) if scored else None
        chosen_note = "best raw value (NO endpoint passed all gates)"

    return {
        "aa": aa_row,
        "slug": slug,
        "jaccard": round(j, 2),
        "ladder": eps,
        "chosen": chosen,
        "chosen_note": chosen_note,
        "default": default,
        "default_by_blend": default_by_blend,
        "next_up": next_up,
        "note": "",
    }


def main():
    print("Loading AA published data ...", flush=True)
    aa = load_aa()

    # Original analysis composite: ((T + I^2) * R) / C  — Section 3.3/3.4 basis
    # Mask zero/negative throughput and price to NaN first: dividing by 0 yields
    # inf, which would hijack nlargest() and return the wrong top-20.
    _t = aa["tps_aa"].where(aa["tps_aa"] > 0, np.nan)
    _c = aa["price_blend"].where(aa["price_blend"] > 0, np.nan)
    _r = aa["reliab"].clip(lower=0.0)
    aa["composite_aa"] = ((_t + aa["intel"] ** 2) * _r) / _c
    aa["composite_aa"] = aa["composite_aa"].replace([np.inf, -np.inf], np.nan)
    top20 = aa.dropna(subset=["composite_aa"]).nlargest(TOP_N_ORIGINAL, "composite_aa")
    above44 = aa[(aa["intel"] >= ABOVE44_INTEL) & aa["price_blend"].notna()].copy()

    targets = pd.concat([top20.assign(_bucket="top20"),
                         above44.assign(_bucket="above44")])
    targets = targets.drop_duplicates(subset=["Model"])
    print(f"  top-20 original performers : {len(top20)}")
    print(f"  Above-44 models            : {len(above44)}")
    print(f"  unique targets to resolve  : {len(targets)}")

    print("Loading OpenRouter catalog ...", flush=True)
    catalog = load_or_catalog()
    print(f"  OpenRouter models: {len(catalog)}")

    out = {}
    for i, (_, row) in enumerate(targets.iterrows(), 1):
        name = row["Model"]
        aa_row = {k: (None if pd.isna(v) else (float(v) if isinstance(v, (int, float, np.floating)) else v))
                  for k, v in row.items()}
        try:
            res = analyse_model(name, aa_row, catalog)
        except Exception as exc:
            res = {"aa": aa_row, "slug": None, "ladder": [], "chosen": None,
                   "default": None, "next_up": None, "note": f"error: {exc}"}
        res["bucket"] = row.get("_bucket")
        out[name] = res
        status = "ok" if res.get("chosen") else "MISS"
        print(f"  [{i:>2}/{len(targets)}] {status:<4} {str(name)[:46]:<48} "
              f"eps={len(res.get('ladder', []))}", flush=True)
        time.sleep(0.12)

    with open("provider_value_by_model.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("\nWrote provider_value_by_model.json")

    # quick summary
    ok = [k for k, v in out.items() if v.get("chosen")]
    print(f"Resolved: {len(ok)}/{len(out)}")
    for k in out:
        if not out[k].get("chosen"):
            print(f"  unresolved: {k} ({out[k].get('note')})")


if __name__ == "__main__":
    main()
