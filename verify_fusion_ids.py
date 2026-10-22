#!/usr/bin/env python3
"""Quick model ID verification + forced Fusion tool call test."""
import json, os, time, requests, sys

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY: print("ERROR: KEY"); sys.exit(1)

headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

SHORT_PROMPT = "In one sentence, what is 2+2?"

def quick_call(model_id, label):
    sys.stdout.write(f"  {label} ({model_id})... "); sys.stdout.flush()
    start = time.time()
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers=headers, timeout=60,
            json={"model": model_id, "messages": [{"role":"user","content":SHORT_PROMPT}],
                  "temperature":0, "max_tokens":50})
        elapsed = time.time() - start
        if resp.status_code == 200:
            d = resp.json()
            content = d["choices"][0]["message"].get("content","")[:80]
            print(f"OK {elapsed:.1f}s | {d.get('model','?')} | '{content}'")
            return True
        else:
            print(f"FAIL {resp.status_code}: {resp.text[:120]}")
            return False
    except Exception as e:
        print(f"ERR: {str(e)[:80]}")
        return False

# ═══════════════════════════════════════════════════════════════════
# STEP 1: Verify all model IDs work standalone
# ═══════════════════════════════════════════════════════════════════
print("=" * 60)
print("STEP 1: Standalone verification")
print("=" * 60)

model_ids = [
    "kwaipilot/kat-coder-pro-v2",
    "xiaomi/mimo-v2.5-pro",
    "z-ai/glm-5.1",
    "deepseek/deepseek-v4-pro",
]
results = {}
for mid in model_ids:
    results[mid] = quick_call(mid, mid.split("/")[-1])
    time.sleep(1)

# ═══════════════════════════════════════════════════════════════════
# STEP 2: Try Fusion with FORCED tool call (system prompt demands it)
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 2: Fusion with explicit tool-use instruction")
print("=" * 60)

FORCE_PROMPT = """You MUST use the openrouter:fusion tool to answer.
Call it NOW. Do not answer directly. Use the tool first."""

fusion_configs = [
    {
        "label": "Fusion-Forced-A: GLM judge",
        "judge": "z-ai/glm-5.1",
        "panel": ["kwaipilot/kat-coder-pro-v2", "xiaomi/mimo-v2.5-pro", "deepseek/deepseek-v4-pro"],
    },
    {
        "label": "Fusion-Forced-B: DeepSeek judge",
        "judge": "deepseek/deepseek-v4-pro",
        "panel": ["kwaipilot/kat-coder-pro-v2", "xiaomi/mimo-v2.5-pro", "z-ai/glm-5.1"],
    },
]

for cfg in fusion_configs:
    sys.stdout.write(f"  {cfg['label']}... "); sys.stdout.flush()
    start = time.time()
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers=headers, timeout=120,
            json={
                "model": "openrouter/fusion",
                "messages": [{"role": "user", "content": FORCE_PROMPT}],
                "temperature": 0, "max_tokens": 500,
                "plugins": [{
                    "id": "fusion",
                    "analysis_models": cfg["panel"],
                    "model": cfg["judge"],
                    "max_tool_calls": 2,
                }]
            })
        elapsed = time.time() - start
        if resp.status_code == 200:
            d = resp.json()
            content = d["choices"][0]["message"].get("content","")
            model_used = d.get("model","?")
            usage = d.get("usage",{})
            # Check for finish_reason — "tool_calls" means panel was invoked
            finish = d["choices"][0].get("finish_reason","?")
            
            print(f"OK {elapsed:.1f}s | model={model_used} | finish={finish} | {usage.get('total_tokens',0)}tk")
            
            # Did it actually call the tool? Check content for Fusion indicators
            has_deliberation = any(w in content.lower() for w in ["consensus","contradiction","unique insight","blind spot","analysis","panel","judge","fusion"])
            print(f"    Content preview: {content[:150]}...")
            print(f"    Fusion indicators in output: {has_deliberation}")
        else:
            print(f"FAIL {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        print(f"ERR: {str(e)[:80]}")
    time.sleep(2)

print("\nDone. Check OpenRouter logs now for panel model calls.")
