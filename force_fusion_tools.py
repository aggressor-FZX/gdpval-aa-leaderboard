#!/usr/bin/env python3
"""Force Fusion tool invocation via tools array + tool_choice: required."""
import json, os, time, requests, sys

KEY = os.getenv("OPENROUTER_API_KEY_1")
if not KEY: print("ERROR: KEY"); sys.exit(1)

headers = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

SHORT_PROMPT = "What is the capital of France? Use the fusion tool to get multiple perspectives before answering."

configs = [
    {"label": "Forced Fusion: tools+required (GLM judge)", "judge": "z-ai/glm-5.1"},
    {"label": "Forced Fusion: tools+required (DeepSeek judge)", "judge": "deepseek/deepseek-v4-pro"},
]

for cfg in configs:
    sys.stdout.write(f"\n{cfg['label']}... "); sys.stdout.flush()
    start = time.time()
    try:
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers=headers, timeout=120,
            json={
                "model": cfg["judge"],
                "messages": [{"role": "user", "content": SHORT_PROMPT}],
                "temperature": 0, "max_tokens": 500,
                "tools": [{"type": "openrouter:fusion"}],
                "tool_choice": "required",
                "plugins": [{
                    "id": "fusion",
                    "analysis_models": ["kwaipilot/kat-coder-pro-v2", "xiaomi/mimo-v2.5-pro"],
                    "model": cfg["judge"],
                    "max_tool_calls": 2,
                }],
            })
        elapsed = time.time() - start
        d = resp.json() if resp.status_code == 200 else {}
        finish = d.get("choices", [{}])[0].get("finish_reason", "?")
        model_used = d.get("model", "?")
        usage = d.get("usage", {})
        content = d.get("choices", [{}])[0].get("message", {}).get("content", "")[:200]
        
        print(f"HTTP{resp.status_code} | finish={finish} | model={model_used} | {usage.get('total_tokens','?')}tk | {elapsed:.1f}s")
        
        # Check for tool_calls in the response
        msg = d.get("choices", [{}])[0].get("message", {})
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            print(f"  ✅ TOOL CALLS DETECTED: {len(tool_calls)}")
            for tc in tool_calls[:3]:
                print(f"     id={tc.get('id','?')} name={tc.get('function',{}).get('name','?')}")
        else:
            print(f"  ❌ No tool_calls in response. Content: {content[:120]}...")
            
    except Exception as e:
        print(f"ERR: {str(e)[:120]}")
    time.sleep(2)

print("\nDone. Check OpenRouter logs — you should see panel model calls if tool_choice worked.")
