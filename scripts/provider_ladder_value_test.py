"""
Provider ladder value test — is the NEXT provider up from the default better VALUE?

Default routing on OpenRouter optimizes on price. The question is whether stepping
one rung up the price ladder buys enough quality to be worth more than the extra cost.

Arms tested (same model, same probes, same workload):
  1. default      — no provider pin, whatever the router picks
  2. cheapest     — lowest blended price in the ladder
  3. next_up      — first provider priced above the default pick
  4. quality_tier — a high-throughput mid-price provider for the value curve

Value = probes passed / measured USD. Also reports cost per successful
long-context retrieval, which is the probe that actually separates providers.

Usage:  python3 provider_ladder_value_test.py
"""

import os, json, time, collections
import requests
from dotenv import load_dotenv

load_dotenv()

URL = "https://openrouter.ai/api/v1/chat/completions"
KEY = os.getenv("OPENROUTER_API_KEY_1")
MODEL = os.getenv("PROBE_MODEL", "deepseek/deepseek-v4.1-flash")

if not KEY:
    raise SystemExit("OPENROUTER_API_KEY_1 not set in .env")

H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

# Probe sizing — kept small so the whole sweep stays cheap and fast.
CENSUS_N = 8
TOOL_N = 3
NEEDLE = "PINEAPPLE-7731"


# ---------------------------------------------------------------- ladder ----
def fetch_ladder():
    """Return endpoints sorted by 3:1 blended price per 1M tokens."""
    r = requests.get(f"https://openrouter.ai/api/v1/models/{MODEL}/endpoints",
                     headers={"Authorization": f"Bearer {KEY}"}, timeout=60)
    r.raise_for_status()
    eps = r.json().get("data", {}).get("endpoints", [])
    out = []
    for e in eps:
        p = e.get("pricing", {}) or {}
        try:
            pi = float(p.get("prompt", 0) or 0)
            po = float(p.get("completion", 0) or 0)
        except (TypeError, ValueError):
            pi = po = 0.0
        tput = e.get("throughput_last_30m")
        out.append({
            "name": e.get("provider_name") or e.get("name") or "unknown",
            "blend": (pi * 3 + po) / 4 * 1_000_000,
            "in": pi * 1_000_000,
            "out": po * 1_000_000,
            "ctx": e.get("context_length"),
            "quant": e.get("quantization"),
            "tps": tput.get("p50") if isinstance(tput, dict) else None,
            "uptime": e.get("uptime_last_30m"),
        })
    out.sort(key=lambda x: x["blend"])
    return out


# ------------------------------------------------------------------ call ----
def call(messages, provider=None, max_tokens=2048, tools=None, tool_choice=None):
    """One chat completion. Returns (json, latency_s)."""
    body = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
        "usage": {"include": True},
    }
    if provider:
        # allow_fallbacks=False so we hit exactly this provider or fail loudly.
        # require_parameters is left off here: the goal is to REACH the rung,
        # not to filter the pool before routing.
        body["provider"] = {"order": [provider], "allow_fallbacks": False}
    if tools:
        body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice
    t0 = time.time()
    r = requests.post(URL, headers=H, json=body, timeout=240)
    dt = time.time() - t0
    r.raise_for_status()
    return r.json(), dt


def provider_of(d):
    return d.get("provider") or d.get("provider_name") or "unknown"


def cost_of(d):
    try:
        return float(d.get("usage", {}).get("cost") or 0.0)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------- probes ----
def run_arm(label, provider=None):
    """Run probes A-D for one arm. Returns a result dict."""
    res = {"label": label, "pin": provider, "census": collections.Counter(),
           "latencies": [], "errors": [], "cost": 0.0}

    # A — provider census on trivial calls
    for _ in range(CENSUS_N):
        try:
            d, dt = call([{"role": "user", "content": "reply OK"}],
                         provider=provider, max_tokens=8)
            res["census"][provider_of(d)] += 1
            res["latencies"].append(dt)
            res["cost"] += cost_of(d)
        except Exception as e:
            res["errors"].append(f"A:{type(e).__name__}")

    # B — truncation / output cap
    try:
        d, dt = call([{"role": "user",
                       "content": "List the integers 1..500, one per line, no commentary."}],
                     provider=provider, max_tokens=4096)
        txt = d["choices"][0]["message"].get("content") or ""
        nums = [ln.strip() for ln in txt.splitlines() if ln.strip().isdigit()]
        res["B"] = {
            "finish": d["choices"][0].get("finish_reason"),
            "items": len(nums),
            "max_item": max((int(n) for n in nums), default=0),
            "latency": dt,
            "provider": provider_of(d),
        }
        res["cost"] += cost_of(d)
    except Exception as e:
        res["B"] = {"error": f"{type(e).__name__}: {e}"}

    # C — needle in haystack at 32k and 64k
    filler = "The quick brown fox jumps over the lazy dog. " * 40  # ~400 tokens
    res["C"] = {}
    for target in (32000, 64000):
        reps = max(1, target // 400)
        chunks = [filler] * reps
        chunks.insert(len(chunks) // 2, f" The secret code word is {NEEDLE}. ")
        prompt = ("".join(chunks) +
                  "\n\nQuestion: what is the secret code word in the text above? "
                  "Answer with just the code word.")
        try:
            d, dt = call([{"role": "user", "content": prompt}],
                         provider=provider, max_tokens=32)
            txt = (d["choices"][0]["message"].get("content") or "").upper()
            res["C"][target] = {
                "found": NEEDLE in txt,
                "finish": d["choices"][0].get("finish_reason"),
                "prompt_tokens": d.get("usage", {}).get("prompt_tokens"),
                "latency": dt,
                "provider": provider_of(d),
            }
            res["cost"] += cost_of(d)
        except Exception as e:
            res["C"][target] = {"error": f"{type(e).__name__}: {e}"}

    # D — forced tool call against a strict schema
    tool = {"type": "function", "function": {
        "name": "record_weather",
        "description": "Record a weather observation.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "temp_c": {"type": "number"},
                "conditions": {"type": "string",
                               "enum": ["clear", "cloudy", "rain", "snow"]},
            },
            "required": ["city", "temp_c", "conditions"],
            "additionalProperties": False,
        },
    }}
    ok_n = 0
    for _ in range(TOOL_N):
        try:
            d, dt = call([{"role": "user",
                           "content": "Record that it is 21.5 C and cloudy in Lisbon."}],
                         provider=provider, max_tokens=256, tools=[tool],
                         tool_choice={"type": "function",
                                      "function": {"name": "record_weather"}})
            tcs = d["choices"][0]["message"].get("tool_calls") or []
            ok = False
            if tcs:
                try:
                    a = json.loads(tcs[0]["function"]["arguments"])
                    ok = (isinstance(a.get("city"), str)
                          and isinstance(a.get("temp_c"), (int, float))
                          and a.get("conditions") in {"clear", "cloudy", "rain", "snow"}
                          and set(a) <= {"city", "temp_c", "conditions"})
                except Exception:
                    ok = False
            ok_n += int(ok)
            res["cost"] += cost_of(d)
        except Exception as e:
            res["errors"].append(f"D:{type(e).__name__}")
    res["D"] = {"valid": ok_n, "of": TOOL_N}

    # ---- score the arm ----
    b = res.get("B", {})
    c = res.get("C", {})
    d = res.get("D", {})
    checks = {
        "B_trunc": bool(b.get("finish") == "stop" and b.get("max_item", 0) >= 500),
        "C_32k": bool(c.get(32000, {}).get("found")),
        "C_64k": bool(c.get(64000, {}).get("found")),
        "D_tool": bool(d.get("valid", 0) == TOOL_N),
    }
    res["checks"] = checks
    res["passed"] = sum(checks.values())
    res["long_ctx_ok"] = checks["C_32k"] and checks["C_64k"]
    res["mean_latency"] = (sum(res["latencies"]) / len(res["latencies"])
                           if res["latencies"] else float("nan"))
    return res


# ------------------------------------------------------------------ main ----
def main():
    lad = fetch_ladder()
    print(f"Model: {MODEL}")
    print(f"Endpoints in ladder: {len(lad)}")
    print()
    print(f"{'#':<4}{'provider':<26}{'blend/M':>9}{'in/M':>8}{'out/M':>8}"
          f"{'ctx':>9}{'quant':>10}{'tok/s':>8}{'uptime':>8}")
    print("-" * 92)
    for i, e in enumerate(lad, 1):
        print(f"{i:<4}{str(e['name'])[:25]:<26}{e['blend']:>9.4f}{e['in']:>8.3f}"
              f"{e['out']:>8.3f}{str(e['ctx']):>9}{str(e['quant'])[:9]:>10}"
              f"{str(e['tps'])[:7]:>8}{str(e['uptime'])[:7]:>8}")

    # --- identify the default pick with one cheap call ---
    print("\nDetecting default routing pick...")
    d, _ = call([{"role": "user", "content": "reply OK"}], max_tokens=8)
    default_name = provider_of(d)
    default_blend = next((e["blend"] for e in lad if e["name"] == default_name), None)
    print(f"  default -> {default_name}  (blended ${default_blend:.4f}/M)"
          if default_blend is not None else f"  default -> {default_name} (not in ladder)")

    # --- build the arms ---
    cheapest = lad[0]
    # next rung up from the default's price position
    next_up = None
    if default_blend is not None:
        for e in lad:
            if e["blend"] > default_blend and e["name"] != default_name:
                next_up = e
                break
    if next_up is None:
        next_up = lad[min(1, len(lad) - 1)]

    # quality tier: highest throughput among providers priced <= 2x the default
    cap = (default_blend or lad[0]["blend"]) * 2.0
    cands = [e for e in lad if e["blend"] <= cap and e["tps"]]
    quality = max(cands, key=lambda e: e["tps"]) if cands else lad[-1]

    arms = [
        ("default", None),
        (f"cheapest:{cheapest['name']}", cheapest["name"]),
        (f"next_up:{next_up['name']}", next_up["name"]),
        (f"quality:{quality['name']}", quality["name"]),
    ]

    print("\nArms:")
    for lbl, pin in arms:
        e = next((x for x in lad if x["name"] == pin), None) if pin else None
        spec = (f"${e['blend']:.4f}/M  {e['quant']}  {e['tps']} tok/s  ctx {e['ctx']}"
                if e else "router's choice")
        print(f"  {lbl:<28} {spec}")

    # --- run ---
    results = []
    for lbl, pin in arms:
        print(f"\nRunning {lbl} ...", flush=True)
        try:
            results.append(run_arm(lbl, pin))
        except Exception as e:
            print(f"  ARM FAILED: {type(e).__name__}: {e}")
            results.append({"label": lbl, "pin": pin, "census": collections.Counter(),
                            "errors": [str(e)], "cost": 0.0, "checks": {},
                            "passed": 0, "long_ctx_ok": False,
                            "mean_latency": float("nan"), "B": {}, "C": {}, "D": {}})

    # --- summary ---
    print("\n" + "=" * 104)
    print("PROVIDER LADDER — VALUE SUMMARY")
    print("=" * 104)
    hdr = (f"{'arm':<28}{'served':<16}{'B':>4}{'32k':>5}{'64k':>5}{'tool':>6}"
           f"{'pass':>6}{'cost$':>10}{'val':>9}{'lat_s':>8}")
    print(hdr)
    print("-" * 104)
    for r in results:
        served = ",".join(f"{k}x{v}" for k, v in r["census"].most_common(2)) or "-"
        ck = r.get("checks", {})
        val = (r["passed"] / r["cost"] * 1000) if r["cost"] > 0 else float("nan")
        print(f"{r['label']:<28}{served[:15]:<16}"
              f"{'P' if ck.get('B_trunc') else 'F':>4}"
              f"{'P' if ck.get('C_32k') else 'F':>5}"
              f"{'P' if ck.get('C_64k') else 'F':>5}"
              f"{'P' if ck.get('D_tool') else 'F':>6}"
              f"{r['passed']:>4}/4"
              f"{r['cost']:>10.5f}{val:>9.1f}{r['mean_latency']:>8.2f}")

    # --- the actual answer ---
    by = {r["label"].split(":")[0]: r for r in results}
    dflt = by.get("default")
    nxt = by.get("next_up")
    print("\n" + "=" * 104)
    print("VERDICT — is the next rung up better VALUE than the default?")
    print("=" * 104)
    if dflt and nxt:
        dq, nq = dflt["passed"], nxt["passed"]
        dc, nc = dflt["cost"], nxt["cost"]
        print(f"  default  ({dflt['label'].split(':')[-1] if ':' in dflt['label'] else 'router'}): "
              f"{dq}/4 probes, ${dc:.5f}, long-context {'OK' if dflt['long_ctx_ok'] else 'FAIL'}")
        print(f"  next_up  ({nxt['label'].split(':')[-1]}): "
              f"{nq}/4 probes, ${nc:.5f}, long-context {'OK' if nxt['long_ctx_ok'] else 'FAIL'}")
        if nc > 0 and dc > 0:
            print(f"  cost ratio next_up/default: {nc/dc:.2f}x")
        if dq > 0 and nq > 0:
            print(f"  quality ratio next_up/default: {nq/dq:.2f}x")
        if nq > dq and nxt["long_ctx_ok"] and not dflt["long_ctx_ok"]:
            print("  => YES. The next rung up is better value: it buys working "
                  "long-context retrieval for a small price step.")
        elif nq == dq and nc <= dc:
            print("  => No quality gain for the extra spend. Stay on default.")
        elif nq == dq and nc > dc:
            print("  => Same quality, higher cost. Default is the better value.")
        else:
            print("  => Mixed. Compare the per-probe table above before switching.")
    print("\n  Note: 'val' = probes passed per 1000 USD. Higher is better value.")
    print("  Note: provider names repeat in the ladder (multiple endpoints per vendor);")
    print("        a name pin may land on any of that vendor's endpoints.")

    # --- raw dump ---
    dump = []
    for r in results:
        dump.append({
            "label": r["label"], "pin": r["pin"],
            "census": dict(r["census"]), "checks": r.get("checks", {}),
            "passed": r["passed"], "cost": round(r["cost"], 6),
            "mean_latency": round(r["mean_latency"], 3) if r["mean_latency"] == r["mean_latency"] else None,
            "B": r.get("B", {}), "C": {str(k): v for k, v in r.get("C", {}).items()},
            "D": r.get("D", {}), "errors": r["errors"],
        })
    with open("provider_ladder_value_results.json", "w") as f:
        json.dump({"model": MODEL, "ladder": lad, "arms": dump}, f, indent=2)
    print("\nRaw results -> provider_ladder_value_results.json")


if __name__ == "__main__":
    main()
