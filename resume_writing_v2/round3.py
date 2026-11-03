#!/usr/bin/env python3
"""Round 3 — the explicitly requested model set, at named reasoning efforts.

Why a third round instead of reusing rounds 1/2:
  * rounds 1 and 2 ran every model at the provider DEFAULT effort (effort=None),
    so they cannot answer "Grok 4.7 at xhigh vs Kimi K3.1 Pro";
  * most of this set (Haiku, Grok, Kimi, Sol, Luna, Beam, Step, Nemotron, MiMo,
    Muse, Mistral, Gemini 3.8, Llama, GPT-3.5) was never run through the harness
    at all;
  * it spans three price decades, so it is the set that can plot score-vs-price.

Effort strings come from the user's request and are passed through as
`reasoning_effort`. A variant is a distinct model — the label names the effort
so a score can never be attributed to the wrong configuration.

`K2 Horizon 375B A23B` has no OpenRouter id (searched the live catalog for
`k2`, `horizon`, `375`) and is recorded as unavailable rather than silently
dropped.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resume_writing_v2 import runner, task
from resume_writing_v2.config import ModelEntry

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "contest_cheap_r3.json")

RUNS = int(os.environ.get("RUNS", "4"))
BUDGET = float(os.environ.get("BUDGET", "6.00"))
DRY = os.environ.get("DRY", "0") == "1"

# (openrouter id, label, reasoning_effort, max_tokens override)
REQUESTED: list[tuple[str, str, str | None, int | None]] = [
    ("z-ai/glm-5.3-flash",             "GLM-5.3-Flash",              None,   None),
    ("anthropic/claude-haiku-5.5",     "Claude Haiku 5.5 (max)",     "high", None),
    ("x-ai/grok-4.7",                  "Grok 4.7 (xhigh)",           "xhigh", None),
    ("x-ai/grok-4.6",                  "Grok 4.6 (xhigh)",           "xhigh", None),
    ("thinkingmachines/inkling",       "Inkling (xhigh)",            "xhigh", None),
    ("mistralai/mistral-large-4-0",    "Mistral Large 4 Preview",    None,   None),
    ("google/gemini-3.8-flash",        "Gemini 3.8 Flash (high)",    "high", None),
    ("moonshotai/kimi-k3.1-pro",       "Kimi K3.1 Pro",              None,   None),
    ("deepseek/deepseek-v4.1-flash-1017", "DeepSeek V4.1 Flash 1017 (max)", "xhigh", None),
    ("reflection/beam-1.0-501b-a23b",  "Beam 1.0",                   None,   None),
    ("nvidia/nemotron-3.5-super-vl",   "Nemotron 3.5 Super VL",      None,   None),
    ("deepseek/deepseek-v4.1-flash",   "DeepSeek V4.1 Flash (max)",  "xhigh", None),
    ("minimax/minimax-m3",             "MiniMax-M3",                 None,   None),
    ("openai/gpt-6.1-sol",             "GPT-6.1 Sol (max)",          "xhigh", None),
    ("openai/gpt-6-luna",              "GPT-6 Luna (max)",           "xhigh", None),
    ("meta/muse-glimmer-30b",          "Muse Glimmer (high)",        "high", None),
    ("minimax/minimax-m3.1-flash",     "MiniMax-M3.1-Flash",         None,   None),
    ("xiaomi/mimo-v2.6-pro",           "MiMo-V2.6-Pro",              None,   None),
    ("stepfun/step-5-preview",         "Step 5 Preview",             None,   None),
    ("nvidia/nemotron-3-ultra-550b-a55b", "Nemotron 3 Ultra 550B",   None,   None),
    ("qwen/qwen3.8-max-0902",          "Qwen3.8 Max (0902)",         None,   None),
    ("qwen/qwen3.8-27b",               "Qwen3.8 27B (xhigh)",        "xhigh", None),
    ("openai/gpt-5.4-mini",            "GPT-5.4 mini (non-reasoning)", None, None),
    ("meta-llama/llama-4-maverick",    "Llama 4 Maverick",           None,   None),
    # 4095-token context: the 16384 default would fail, the prompt is ~900.
    ("openai/gpt-3.5-turbo-0613",      "GPT-3.5 Turbo",              None,   1600),
]

UNAVAILABLE = {
    "K2 Horizon 375B A23B": "no matching OpenRouter id (catalog searched for "
                            "'k2', 'horizon', '375')",
}


def entries() -> list[ModelEntry]:
    out = []
    for mid, label, effort, mt in REQUESTED:
        kw = {} if mt is None else {"max_tokens": mt}
        out.append(ModelEntry(model_id=mid, label=label, effort=effort,
                              group="round3", **kw))
    return out


def main() -> int:
    ents = entries()
    print(f"{len(ents)} runnable models x {RUNS} runs; "
          f"{len(UNAVAILABLE)} unavailable: {list(UNAVAILABLE)}")
    payload = runner.run(ents, task.build_prompt(), task.SYSTEM_PROMPT,
                         runs=RUNS, budget_usd=BUDGET, out_path=OUT,
                         dry_run=DRY)
    if DRY:
        return 0
    print(f"spent ${payload['meta']['spent_usd']:.4f}")
    ok = sum(1 for r in payload["results"] if r.get("ok"))
    print(f"scorable {ok}/{len(payload['results'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
