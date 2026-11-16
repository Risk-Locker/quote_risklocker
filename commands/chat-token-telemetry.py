"""Antigravity Conversation Token Telemetry Helper.

Reads the active conversation transcript in real-time, calculates:
- Active Context Tokens (Prompt + Cached) vs 1,000,000 (1M) limit.
- Remaining Context Headroom.
- Cumulative Tokens Processed in session.
- Context Health recommendation (when to open fresh chat or /compact).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def get_active_conversation_token_stats(conversation_id: str | None = None) -> dict:
    user_home = Path.home()
    app_data = user_home / ".gemini" / "antigravity"
    brain_dir = app_data / "brain"

    if not brain_dir.exists():
        return {
            "error": "Antigravity brain directory not found",
            "active_context_tokens": 0,
            "context_limit": 1_000_000,
            "context_pct": 0.0,
            "remaining_headroom": 1_000_000,
            "cumulative_tokens": 0,
        }

    conv_dirs = [
        d for d in brain_dir.iterdir()
        if d.is_dir() and (d / ".system_generated" / "logs" / "transcript.jsonl").exists()
    ]

    if not conv_dirs:
        return {
            "error": "No conversation transcript found",
            "active_context_tokens": 0,
            "context_limit": 1_000_000,
            "context_pct": 0.0,
            "remaining_headroom": 1_000_000,
            "cumulative_tokens": 0,
        }

    if conversation_id:
        target_dir = brain_dir / conversation_id
        if not target_dir.exists():
            target_dir = max(conv_dirs, key=lambda d: (d / ".system_generated" / "logs" / "transcript.jsonl").stat().st_mtime)
    else:
        target_dir = max(conv_dirs, key=lambda d: (d / ".system_generated" / "logs" / "transcript.jsonl").stat().st_mtime)

    t_file = target_dir / ".system_generated" / "logs" / "transcript.jsonl"

    total_input = 0
    total_cached = 0
    total_output = 0
    last_input = 0
    last_cached = 0
    last_output = 0
    step_count = 0

    with open(t_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                step_count += 1
                inp = data.get("input_tokens", 0)
                cache = data.get("cache_read_tokens", 0)
                out = data.get("output_tokens", 0)
                total_input += inp
                total_cached += cache
                total_output += out
                if inp or cache:
                    last_input = inp
                    last_cached = cache
                if out:
                    last_output = out
            except Exception:
                pass

    active_context = last_input + last_cached
    context_limit = 1_000_000
    pct = (active_context / context_limit) * 100 if context_limit > 0 else 0.0
    remaining = max(0, context_limit - active_context)
    cumulative = total_input + total_cached + total_output

    if pct >= 50.0:
        recommendation = "High context load (>50%). Recommended: open fresh chat (Ctrl+L) or run /compact."
    elif pct >= 25.0:
        recommendation = "Moderate context load. Healthy for multi-step milestones; consider fresh chat upon milestone completion."
    else:
        recommendation = "Low/optimal context load (<25%). Fast processing and high token efficiency."

    return {
        "conversation_id": target_dir.name,
        "step_count": step_count,
        "active_context_tokens": active_context,
        "active_input_tokens": last_input,
        "active_cached_tokens": last_cached,
        "active_output_tokens": last_output,
        "context_limit": context_limit,
        "context_pct": round(pct, 1),
        "remaining_headroom": remaining,
        "cumulative_input_tokens": total_input,
        "cumulative_cached_tokens": total_cached,
        "cumulative_output_tokens": total_output,
        "cumulative_tokens": cumulative,
        "recommendation": recommendation,
    }


def format_token_report_markdown(stats: dict) -> str:
    if "error" in stats and stats["error"]:
        return f"> [!WARNING] Token Telemetry: {stats['error']}"

    act = stats["active_context_tokens"]
    limit = stats["context_limit"]
    pct = stats["context_pct"]
    rem = stats["remaining_headroom"]
    cum = stats["cumulative_tokens"]

    return (
        f"| Metric | Token Count | Status / Limit |\n"
        f"| :--- | :--- | :--- |\n"
        f"| **Active Context Used** | **{act:,}** tokens | **{pct:.1f}%** of 1,000,000 (1M) limit |\n"
        f"| **Remaining Context Headroom** | **{rem:,}** tokens | Available before 1M window ceiling |\n"
        f"| **• Fresh Input (Latest Turn)** | {stats['active_input_tokens']:,} tokens | Non-cached recent messages & tool outputs |\n"
        f"| **• Cached Read (Latest Turn)** | {stats['active_cached_tokens']:,} tokens | Cached context (low-latency prompt cache) |\n"
        f"| **Cumulative Session Activity** | **{cum:,}** tokens | Processed across {stats['step_count']} steps in this chat |\n"
        f"| **Chat Context Health** | {stats['recommendation']} |"
    )


def main():
    conv_id = sys.argv[1] if len(sys.argv) > 1 else None
    stats = get_active_conversation_token_stats(conv_id)
    print(format_token_report_markdown(stats))


if __name__ == "__main__":
    main()
