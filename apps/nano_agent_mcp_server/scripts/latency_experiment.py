#!/usr/bin/env python3
"""
Empirical latency experiment for nano-agent.

Measures wall-clock time and turn count for the same prompt across:
  - different models (--model, --provider)
  - thinking on vs off (--thinking on/off/skip)

Not a unit test. Manual investigation only.

Usage:
    uv run python scripts/latency_experiment.py \\
        --model glm-5.1 --provider zai --thinking on --runs 2

    uv run python scripts/latency_experiment.py \\
        --model glm-5.1 --provider zai --thinking off --runs 2

    uv run python scripts/latency_experiment.py \\
        --model gpt-5-mini --provider openai --runs 2
"""
import argparse
import asyncio
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, cast

THIS = Path(__file__).resolve()
SRC = THIS.parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nano_agent.modules.constants import MODEL_CAPABILITIES  # noqa: E402
from nano_agent.modules.data_types import PromptNanoAgentRequest  # noqa: E402
from nano_agent.modules.nano_agent import _execute_nano_agent_async  # noqa: E402

DEFAULT_PROMPT = (
    "Create a file named 'latency_marker.txt' in the workspace containing "
    "the text 'hello'. Then read it back and report the content. Be brief."
)


def patch_thinking(model: str, mode: str):
    """Mutate MODEL_CAPABILITIES[model].extra_body['thinking']['type'] in-place.

    Returns a callable that restores the original extra_body on exit, or None
    if no mutation was applied.
    """
    if mode == "skip":
        return None
    caps = MODEL_CAPABILITIES.get(model)
    if caps is None or caps.extra_body is None:
        return None
    extra_body = caps.extra_body
    if "thinking" not in extra_body:
        return None
    original_value = extra_body["thinking"]
    extra_body["thinking"] = {"type": "enabled" if mode == "on" else "disabled"}

    def restore():
        extra_body["thinking"] = original_value

    return restore


async def run_once(model: str, provider: str, prompt: str, workspace: str) -> dict:
    request = PromptNanoAgentRequest(
        agentic_prompt=prompt,
        model=model,
        provider=cast(Any, provider),  # validated by pydantic Literal at construction
        workspace=workspace,
    )
    start = time.monotonic()
    response = await _execute_nano_agent_async(request, enable_rich_logging=False)
    elapsed = time.monotonic() - start
    return {
        "elapsed_s": elapsed,
        "success": response.success,
        "error": (response.error or "")[:120],
        "metadata": response.metadata,
        "result_len": len(response.result or ""),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--provider", required=True)
    p.add_argument("--thinking", choices=["on", "off", "skip"], default="skip",
                   help="force thinking config (only relevant for models with thinking in extra_body)")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = p.parse_args()

    restore = patch_thinking(args.model, args.thinking)
    print(f"# model={args.model} provider={args.provider} thinking={args.thinking} runs={args.runs}")
    print(f"# prompt: {args.prompt}")

    caps = MODEL_CAPABILITIES.get(args.model)
    if caps and caps.extra_body and "thinking" in caps.extra_body:
        print(f"# actual thinking config in effect: {caps.extra_body['thinking']}")

    try:
        for i in range(1, args.runs + 1):
            with tempfile.TemporaryDirectory(prefix=f"latency_{args.model}_{i}_") as ws:
                r = asyncio.run(run_once(args.model, args.provider, args.prompt, ws))
                turns = r["metadata"].get("turns") or r["metadata"].get("turn_count") or "?"
                tokens = r["metadata"].get("total_tokens") or "?"
                tag = "OK" if r["success"] else "FAIL"
                err = f" err={r['error']}" if r["error"] else ""
                print(f"run={i} elapsed={r['elapsed_s']:.2f}s turns={turns} tokens={tokens} status={tag}{err}")
    finally:
        if restore is not None:
            restore()


if __name__ == "__main__":
    main()
