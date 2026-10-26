"""
CORRECTED provider value test — real speed, real quality, real cost.

WHAT WAS WRONG BEFORE
---------------------
The earlier stealth test used max_tokens=32 for the needle-in-haystack probes.
deepseek-v4.1-flash is a REASONING model: it spends tokens on reasoning before
emitting content. With a 32-token cap it burned all 32 on reasoning and returned
an empty string, so "found=False" was a BUDGET artifact, not a context-window
failure. Re-running with max_tokens=1024 makes every provider pass.

So the earlier "default routing served a degraded endpoint" conclusion was wrong.
This script measures the real question:

  Which providers are cheap AND actually fast AND actually correct?

Method per provider:
  * SPEED  — time a fixed generation task, compute real output tok/s from usage.
  * QUALITY — needle-in-haystack at 32k and 64k with an adequate token budget,
              plus truncation and tool-call probes.
  * COST   — OpenRouter's reported usage.cost for the same calls.
  * VALUE  — quality per dollar, and tok/s per dollar.

Usage: python3 provider_value_corrected.py
"""

import os, json, time, collections
import requests
import numpy as np
from dotenv import load_dotenv

load_dotenv()

URL = "https://openrouter.ai/api/v1/chat/completions"
KEY = os.getenv("OPENROUTER_API_KEY_1")
MODEL = os.getenv("PROBE_MODEL", "deepseek/deepseek-v4.1-flash")
if not KEY:
    raise SystemExit("OPENROUTER_API_KEY_1 not set")

H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
NEEDLE = "PINEAPPLE-7731"
CENSUS_N = 5
TOOL_N = 3
# Reasoning models need headroom. 32 tokens guarantees an empty answer.
NEEDLE_MAX_TOKENS = 1024


def call(messages, provider=None, max_tokens=2048, tools=None, tool_choice=None):
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens,
            "temperature": 0, "usage": {"include": True}}
    if provider:
        body["provider"] = {"order": [provider], "allow_fallbacks": False}
    if tools:
        body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice
    t0 = time.time()
    r = requests.post(URL, headers=H, json=body, timeout=300)
    dt = time.time() - t0
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {str(r.text)[:200]}")
    return r.json(), dt


def provider_of(d):
    return d.get("provider") or d.get("provider_name") or "unknown"


def usage_of(d):
    u = d.get("usage", {}) or {}
    det = u.get("completion_tokens_details") or {}
    try:
        cost = float(u.get("cost") or 0.0)
    except (TypeError, ValueError):
        cost = 0.0
    return {
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "reasoning_tokens": det.get("reasoning_tokens"),
        "cost": cost,
    }


def run_arm(label, provider):
    """Speed + quality + cost for one provider."""
    res = {"label": label, "pin": provider, "census": collections.Counter(),
           "errors": [], "cost": 0.0, "speed_samples": []}

    # ---- A: census + speed on a fixed generation task ----
    # "Count to 200" gives a predictable output length so tok/s is comparable.
    speed_prompt = [{"role": "user",
                     "content": "Count from 1 to 200, one number per line, no commentary."}]
    for _ in range(CENSUS_N):
        try:
            d, dt = call(speed_prompt, provider=provider, max_tokens=2048)
            u = usage_of(d)
            res["census"][provider_of(d)] += 1
            res["cost"] += u["cost"]
            ct = u["completion_tokens"] or 0
            if ct > 0 and dt > 0:
                res["speed_samples"].append({
                    "tps": ct / dt, "latency": dt, "completion_tokens": ct,
                    "reasoning_tokens": u["reasoning_tokens"],
                })
        except Exception as e:
            res["errors"].append(f"A:{type(e).__name__}:{str(e)[:60]}")

    # ---- B: truncation / output cap ----
    try:
        d, dt = call([{"role": "user",
                       "content": "List the integers 1..500, one per line, no commentary."}],
                     provider=provider, max_tokens=4096)
        txt = d["choices"][0]["message"].get("content") or ""
        nums = [ln.strip() for ln in txt.splitlines() if ln.strip().isdigit()]
        u = usage_of(d)
        res["B"] = {"finish": d["choices"][0].get("finish_reason"),
                    "items": len(nums),
                    "max_item": max((int(n) for n in nums), default=0),
                    "latency": dt, "provider": provider_of(d),
                    "completion_tokens": u["completion_tokens"],
                    "reasoning_tokens": u["reasoning_tokens"]}
        res["cost"] += u["cost"]
    except Exception as e:
        res["B"] = {"error": f"{type(e).__name__}: {str(e)[:80]}"}

    # ---- C: needle in haystack, ADEQUATE budget ----
    filler = "The quick brown fox jumps over the lazy dog. " * 40
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
                         provider=provider, max_tokens=NEEDLE_MAX_TOKENS)
            txt = (d["choices"][0]["message"].get("content") or "").upper()
            u = usage_of(d)
            res["C"][target] = {
                "found": NEEDLE in txt,
                "finish": d["choices"][0].get("finish_reason"),
                "prompt_tokens": u["prompt_tokens"],
                "completion_tokens": u["completion_tokens"],
                "reasoning_tokens": u["reasoning_tokens"],
                "latency": dt, "provider": provider_of(d),
                "reply": txt[:40],
            }
            res["cost"] += u["cost"]
        except Exception as e:
            res["C"][target] = {"error": f"{type(e).__name__}: {str(e)[:80]}"}

    # ---- D: forced tool call ----
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
                         provider=provider, max_tokens=512, tools=[tool],
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
            res["cost"] += usage_of(d)["cost"]
        except Exception as e:
            res["errors"].append(f"D:{type(e).__name__}")
    res["D"] = {"valid": ok_n, "of": TOOL_N}

    # ---- score ----
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

    sp = res["speed_samples"]
    res["tps_median"] = float(np.median([s["tps"] for s in sp])) if sp else float("nan")
    res["latency_median"] = float(np.median([s["latency"] for s in sp])) if sp else float("nan")
    res["reasoning_median"] = (float(np.median([s["reasoning_tokens"] or 0 for s in sp]))
                               if sp else float("nan"))
    return res


def main():
    # ---- ladder ----
    r = requests.get(f"https://openrouter.ai/api/v1/models/{MODEL}/endpoints",
                     headers={"Authorization": f"Bearer {KEY}"}, timeout=60)
    r.raise_for_status()
    eps = r.json().get("data", {}).get("endpoints", [])
    lad = []
    for e in eps:
        p = e.get("pricing", {}) or {}
        try:
            pi = float(p.get("prompt", 0) or 0); po = float(p.get("completion", 0) or 0)
        except (TypeError, ValueError):
            pi = po = 0.0
        t = e.get("throughput_last_30m")
        lad.append({
            "name": e.get("provider_name") or e.get("name") or "unknown",
            "blend": (pi * 3 + po) / 4 * 1_000_000,
            "in": pi * 1_000_000, "out": po * 1_000_000,
            "quant": e.get("quantization"), "ctx": e.get("context_length"),
            "tps_listed": t.get("p50") if isinstance(t, dict) else None,
        })
    lad.sort(key=lambda x: x["blend"])

    print(f"Model: {MODEL} | endpoints: {len(lad)}")
    print(f"Needle budget: max_tokens={NEEDLE_MAX_TOKENS} (reasoning models need headroom)\n")

    # ---- default pick ----
    d, _ = call([{"role": "user", "content": "reply OK"}], max_tokens=8)
    default_name = provider_of(d)
    default_blend = next((e["blend"] for e in lad if e["name"] == default_name), None)
    print(f"Default routing -> {default_name} "
          f"(${default_blend:.4f}/M blended)\n" if default_blend else
          f"Default routing -> {default_name}\n")

    # ---- arms: walk the ladder by distinct provider ----
    seen, arms = set(), []
    for e in lad:
        if e["name"] in seen:
            continue
        seen.add(e["name"])
        arms.append(e)
        if len(arms) >= 7:
            break

    print("Arms (distinct providers, cheapest first):")
    for e in arms:
        print(f"  {e['name']:<20} ${e['blend']:>7.4f}/M  in ${e['in']:>6.3f}  "
              f"out ${e['out']:>6.3f}  {str(e['quant']):<8} "
              f"listed {e['tps_listed']} tok/s")
    print()

    # ---- run ----
    results = []
    for e in arms:
        print(f"Running {e['name']} ...", flush=True)
        try:
            results.append(run_arm(e["name"], e["name"]))
        except Exception as ex:
            print(f"  FAILED: {type(ex).__name__}: {ex}")
            results.append({"label": e["name"], "pin": e["name"],
                            "census": collections.Counter(), "errors": [str(ex)],
                            "cost": 0.0, "checks": {}, "passed": 0,
                            "long_ctx_ok": False, "tps_median": float("nan"),
                            "latency_median": float("nan"),
                            "reasoning_median": float("nan"), "B": {}, "C": {}, "D": {}})

    # ---- summary ----
    print("\n" + "=" * 122)
    print("CORRECTED RESULTS — real speed, real quality, real cost")
    print("=" * 122)
    print(f"{'provider':<20}{'served':<20}{'B':>3}{'32k':>5}{'64k':>5}{'tool':>6}"
          f"{'pass':>6}{'tok/s':>8}{'lat_s':>7}{'reason':>8}{'cost$':>10}"
          f"{'$/pass':>9}{'tps/$':>9}")
    print("-" * 122)
    for r_ in results:
        served = ",".join(f"{k}x{v}" for k, v in r_["census"].most_common(1)) or "-"
        ck = r_.get("checks", {})
        cost = r_["cost"]
        per_pass = cost / r_["passed"] if r_["passed"] else float("nan")
        tps = r_.get("tps_median", float("nan"))
        tps_per_dollar = (tps / cost) if (cost > 0 and tps == tps) else float("nan")
        print(f"{r_['label'][:19]:<20}{served[:19]:<20}"
              f"{'P' if ck.get('B_trunc') else 'F':>3}"
              f"{'P' if ck.get('C_32k') else 'F':>5}"
              f"{'P' if ck.get('C_64k') else 'F':>5}"
              f"{'P' if ck.get('D_tool') else 'F':>6}"
              f"{r_['passed']:>4}/4"
              f"{tps:>8.1f}{r_.get('latency_median', float('nan')):>7.2f}"
              f"{r_.get('reasoning_median', float('nan')):>8.0f}"
              f"{cost:>10.5f}{per_pass:>9.5f}{tps_per_dollar:>9.0f}")

    # ---- verdict ----
    print("\n" + "=" * 122)
    print("VERDICT")
    print("=" * 122)
    ok = [r_ for r_ in results if r_["passed"] == 4]
    if ok:
        best_val = min(ok, key=lambda r_: r_["cost"])
        fastest = max(ok, key=lambda r_: r_.get("tps_median", 0) or 0)
        print(f"  Providers passing all 4 probes: {len(ok)}/{len(results)}")
        print(f"  Cheapest that passes everything: {best_val['label']} "
              f"(${best_val['cost']:.5f} for the sweep)")
        print(f"  Fastest that passes everything:  {fastest['label']} "
              f"({fastest.get('tps_median', 0):.0f} tok/s)")
        if best_val["label"] != fastest["label"]:
            print(f"  => Cheap and fast are DIFFERENT providers here. "
                  f"Pick by workload: {best_val['label']} for cost, "
                  f"{fastest['label']} for speed.")
        else:
            print(f"  => {best_val['label']} is both cheapest and fastest among "
                  f"fully-passing providers. Clear winner.")
    else:
        print("  No provider passed all four probes.")

    failed = [r_ for r_ in results if r_["passed"] < 4]
    if failed:
        print(f"\n  Providers that failed at least one probe ({len(failed)}):")
        for r_ in failed:
            ck = r_.get("checks", {})
            bad = [k for k, v in ck.items() if not v]
            print(f"    {r_['label']:<20} failed: {', '.join(bad) or 'n/a'}")
            for t, v in r_.get("C", {}).items():
                if isinstance(v, dict) and not v.get("found"):
                    print(f"      C {t}: finish={v.get('finish')} "
                          f"reasoning={v.get('reasoning_tokens')} "
                          f"reply={v.get('reply')!r}")

    # ---- save ----
    dump = []
    for r_ in results:
        dump.append({
            "provider": r_["label"], "census": dict(r_["census"]),
            "checks": r_.get("checks", {}), "passed": r_["passed"],
            "tps_median": r_.get("tps_median"), "latency_median": r_.get("latency_median"),
            "reasoning_median": r_.get("reasoning_median"),
            "cost": round(r_["cost"], 6),
            "B": r_.get("B", {}),
            "C": {str(k): v for k, v in r_.get("C", {}).items()},
            "D": r_.get("D", {}), "errors": r_["errors"],
        })
    with open("provider_value_corrected.json", "w") as f:
        json.dump({"model": MODEL, "needle_max_tokens": NEEDLE_MAX_TOKENS,
                   "ladder": lad, "arms": dump}, f, indent=2, default=str)
    print("\nRaw -> provider_value_corrected.json")


if __name__ == "__main__":
    main()
