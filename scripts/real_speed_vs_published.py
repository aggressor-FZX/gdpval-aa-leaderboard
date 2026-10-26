"""
Real provider speed vs AA's published speed — and which providers are cheap AND fast.

WHY THIS EXISTS
---------------
The notebook's efficiency metrics (3.3, 3.4, 3.6, 3.10) all use AA's published
`median_output_tokens_per_second` as "speed". But on OpenRouter a model is served by
dozens of endpoints with wildly different throughput. AA's number is one lab
measurement; the number you experience is whichever endpoint the router picks.

This script:
  1. Pulls AA's published speed per model.
  2. Pulls OpenRouter's measured per-endpoint speed (throughput_last_30m.p50).
  3. Compares them -> "are the published speeds real?"
  4. Builds a per-model Pareto frontier on (cost to emit 1M output tokens, time to
     emit them) -> "which providers are cheap AND fast?"
  5. Recomputes the notebook's multiplicative efficiency using REAL speed instead of
     AA speed, and measures how much the ranking moves.

Outputs: real_speed_vs_published.json + printed tables.
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

MAX_MODELS = 15          # endpoints calls to make (1 request each)
INTEL_MIN = 30.0
TOKEN_RE = re.compile(r"[a-z]+|\d+(?:\.\d+)*")
STOP = {"the", "a", "of", "in", "on", "z", "ai", "preview", "beta", "latest"}


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
    # AA returns literal 0 for models it never speed-benchmarked -> missing
    df["tps_aa"] = df["tps_aa"].where(df["tps_aa"] > 0, np.nan)
    df["price_blend"] = df["price_blend"].where(df["price_blend"] > 0, np.nan)
    # reliability proxy: 1 - IFBench, falling back to 1 - HLE
    df["reliab"] = (1 - df["ifbench"]).fillna(1 - df["hle"])
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
        })
    return out


# ------------------------------------------------------------- main ----
def main():
    print("Loading AA published data ...", flush=True)
    aa = load_aa()
    cand = aa[(aa["intel"] > INTEL_MIN) & aa["price_blend"].notna()].copy()
    cand = cand.sort_values("intel", ascending=False)
    print(f"  AA models with Intel>{INTEL_MIN:.0f} and a price: {len(cand)}")

    print("Loading OpenRouter catalog ...", flush=True)
    catalog = load_or_catalog()
    print(f"  OpenRouter models: {len(catalog)}")

    # ---- match and collect ----
    matched = []
    for _, row in cand.iterrows():
        if len(matched) >= MAX_MODELS:
            break
        slug, j = match_slug(row["Model"], catalog)
        if slug:
            matched.append((row, slug, j))
        time.sleep(0.05)

    print(f"  Confident matches: {len(matched)}")
    print()

    endpoint_rows = []
    model_rows = []
    for row, slug, j in matched:
        eps = fetch_endpoints(slug)
        time.sleep(0.12)
        if not eps:
            continue
        speeds = [e["tps"] for e in eps if not np.isnan(e["tps"])]
        prices = [e["price_blend"] for e in eps if e["price_blend"] > 0]
        model_rows.append({
            "Model": row["Model"],
            "slug": slug,
            "jaccard": round(j, 2),
            "intel": row["intel"],
            "reliab": row["reliab"],
            "tps_aa": row["tps_aa"],
            "price_aa": row["price_blend"],
            "n_eps": len(eps),
            "n_speed": len(speeds),
            "tps_med": float(np.median(speeds)) if speeds else np.nan,
            "tps_min": float(np.min(speeds)) if speeds else np.nan,
            "tps_max": float(np.max(speeds)) if speeds else np.nan,
            "price_min": float(np.min(prices)) if prices else np.nan,
            "price_max": float(np.max(prices)) if prices else np.nan,
        })
        for e in eps:
            endpoint_rows.append({"Model": row["Model"], "slug": slug,
                                  "intel": row["intel"], "reliab": row["reliab"], **e})

    mdf = pd.DataFrame(model_rows)
    edf = pd.DataFrame(endpoint_rows)

    # ================================================ TABLE 1: real vs published
    print("=" * 118)
    print("TABLE 1 — AA PUBLISHED SPEED vs OPENROUTER MEASURED SPEED (per model)")
    print("=" * 118)
    print(f"{'Model':<34}{'AA tok/s':>9}{'OR med':>8}{'OR min':>8}{'OR max':>8}"
          f"{'med/AA':>8}{'max/AA':>8}{'eps':>5}{'$/M AA':>9}{'$/M OR':>9}")
    print("-" * 118)
    for _, r in mdf.sort_values("intel", ascending=False).iterrows():
        ratio_med = r["tps_med"] / r["tps_aa"] if r["tps_aa"] and r["tps_aa"] > 0 else np.nan
        ratio_max = r["tps_max"] / r["tps_aa"] if r["tps_aa"] and r["tps_aa"] > 0 else np.nan
        f = lambda v, d=1: f"{v:.{d}f}" if pd.notna(v) else "n/a"
        print(f"{str(r['Model'])[:33]:<34}{f(r['tps_aa']):>9}{f(r['tps_med']):>8}"
              f"{f(r['tps_min']):>8}{f(r['tps_max']):>8}"
              f"{f(ratio_med,2):>8}{f(ratio_max,2):>8}{int(r['n_eps']):>5}"
              f"{f(r['price_aa'],3):>9}{f(r['price_min'],3):>9}")

    # headline accuracy verdict
    both = mdf.dropna(subset=["tps_aa", "tps_med"])
    if len(both):
        ratios = both["tps_med"] / both["tps_aa"]
        print(f"\n  Models with both numbers: {len(both)}")
        print(f"  measured/AA ratio — median {ratios.median():.2f}x, "
              f"mean {ratios.mean():.2f}x, range {ratios.min():.2f}x–{ratios.max():.2f}x")
        over = int((ratios < 0.9).sum()); under = int((ratios > 1.1).sum())
        print(f"  AA overstates speed (measured <90% of AA): {over}/{len(both)}")
        print(f"  AA understates speed (measured >110% of AA): {under}/{len(both)}")
        print(f"  Within ±10%: {len(both) - over - under}/{len(both)}")

    # ================================================ TABLE 2: Pareto per model
    print("\n" + "=" * 118)
    print("TABLE 2 — PARETO FRONTIER PER MODEL: cheap AND fast endpoints")
    print("  cost = $ to emit 1M output tokens | time = minutes to emit 1M output tokens")
    print("=" * 118)
    pareto_counts = {}
    for model, g in edf.groupby("Model"):
        g = g.dropna(subset=["tps"]).copy()
        g = g[g["tps"] > 0]
        if g.empty:
            continue
        g["minutes"] = 1_000_000 / g["tps"] / 60
        g = g.sort_values("price_out")
        # non-dominated: no other endpoint is both cheaper-or-equal AND faster-or-equal
        keep = []
        best_time = float("inf")
        for _, e in g.iterrows():
            if e["minutes"] < best_time - 1e-9:
                keep.append(e)
                best_time = e["minutes"]
        if not keep:
            continue
        print(f"\n  {model}  ({len(g)} endpoints with speed data)")
        print(f"    {'provider':<22}{'$/1M out':>10}{'min/1M':>9}{'tok/s':>8}"
              f"{'quant':>10}{'uptime':>8}")
        for e in keep:
            print(f"    {str(e['provider'])[:21]:<22}{e['price_out']:>10.3f}"
                  f"{e['minutes']:>9.1f}{e['tps']:>8.0f}"
                  f"{str(e['quant'])[:9]:>10}{str(e['uptime'])[:7]:>8}")
            pareto_counts[e["provider"]] = pareto_counts.get(e["provider"], 0) + 1

    # ================================================ TABLE 3: provider scoreboard
    print("\n" + "=" * 118)
    print("TABLE 3 — PROVIDER SCOREBOARD (across all models)")
    print("  value = tok/s per $/1M blended  (higher = more speed per dollar)")
    print("=" * 118)
    edf["value"] = edf["tps"] / edf["price_blend"].replace(0, np.nan)
    agg = edf.dropna(subset=["tps"]).groupby("provider").agg(
        n=("tps", "size"),
        tps_med=("tps", "median"),
        price_med=("price_blend", "median"),
        value_med=("value", "median"),
        uptime_med=("uptime", "median"),
    ).sort_values("value_med", ascending=False)
    print(f"{'provider':<24}{'n':>4}{'tok/s med':>11}{'$/M med':>10}{'tok/s per $':>13}"
          f"{'uptime':>9}{'pareto':>8}")
    print("-" * 118)
    for name, r in agg.head(20).iterrows():
        print(f"{str(name)[:23]:<24}{int(r['n']):>4}{r['tps_med']:>11.0f}"
              f"{r['price_med']:>10.3f}{r['value_med']:>13.1f}"
              f"{r['uptime_med']:>9.1f}{pareto_counts.get(name, 0):>8}")

    # ================================================ TABLE 4: ranking shift
    print("\n" + "=" * 118)
    print("TABLE 4 — DOES THE EFFICIENCY RANKING SURVIVE REAL SPEED?")
    print("  eff = sqrt(tps) * intel * reliab / price   (notebook's 3.4 formula)")
    print("=" * 118)
    eff = mdf.dropna(subset=["tps_aa", "tps_med", "intel", "price_aa"]).copy()
    if len(eff) >= 3:
        eff["eff_aa"] = (np.sqrt(eff["tps_aa"]) * eff["intel"] * eff["reliab"].fillna(0.9)) / eff["price_aa"]
        eff["eff_real"] = (np.sqrt(eff["tps_med"]) * eff["intel"] * eff["reliab"].fillna(0.9)) / eff["price_aa"]
        eff["rank_aa"] = eff["eff_aa"].rank(ascending=False)
        eff["rank_real"] = eff["eff_real"].rank(ascending=False)
        eff["shift"] = eff["rank_aa"] - eff["rank_real"]
        eff = eff.sort_values("rank_real")
        print(f"{'Model':<34}{'rank AA':>9}{'rank real':>11}{'shift':>8}"
              f"{'eff AA':>10}{'eff real':>10}")
        print("-" * 118)
        for _, r in eff.iterrows():
            print(f"{str(r['Model'])[:33]:<34}{int(r['rank_aa']):>9}{int(r['rank_real']):>11}"
                  f"{r['shift']:>+8.0f}{r['eff_aa']:>10.2f}{r['eff_real']:>10.2f}")
        try:
            from scipy.stats import spearmanr
            rho, p = spearmanr(eff["eff_aa"], eff["eff_real"])
            print(f"\n  Spearman rank correlation (AA speed vs real speed): rho={rho:.3f} (p={p:.4f})")
            if rho < 0.7:
                print("  => WEAK. The notebook's efficiency ranking does NOT hold up on real speed.")
            elif rho < 0.9:
                print("  => MODERATE. Ranking broadly holds but individual positions move.")
            else:
                print("  => STRONG. AA speed is a usable proxy for real speed here.")
        except ImportError:
            print("\n  (scipy unavailable — skipping rank correlation)")
        big = eff[eff["shift"].abs() >= 3]
        if len(big):
            print(f"\n  Models that move >=3 ranks when speed is measured instead of published:")
            for _, r in big.iterrows():
                d = "up" if r["shift"] > 0 else "down"
                print(f"    {str(r['Model'])[:40]:<42} {d} {abs(r['shift']):.0f} places")
    else:
        print("  Not enough overlapping models for a ranking comparison.")

    # ================================================ save
    out = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "models": mdf.to_dict("records"),
        "endpoints": edf.replace({np.nan: None}).to_dict("records"),
        "pareto_counts": pareto_counts,
    }
    with open("real_speed_vs_published.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("\nRaw data -> real_speed_vs_published.json")


if __name__ == "__main__":
    main()
