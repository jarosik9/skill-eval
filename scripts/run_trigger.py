#!/usr/bin/env python3
"""Test skill description trigger rate using sessions_history (ground truth).

Detection method: spawn a subagent with sandbox=inherit, then check
sessions_history(includeTools=True) for a tool_use read call on SKILL.md.
This is more accurate than inspecting CLI output — it observes real behavior.

Usage:
    # Step 1: Run trigger queries via orchestrator (produces trigger_results_raw.json)
    # Step 2: Run this script to analyze histories and compute metrics
    python run_trigger.py \
        --raw trigger_results_raw.json \
        --output trigger_rate_results.json

Input format (trigger_results_raw.json):
    [
      {
        "id": "tq-1",
        "query": "...",
        "expected": true,
        "session_key": "agent:...:subagent:uuid"
      }
    ]

Output format (trigger_rate_results.json):
    {
      "trigger_rate": 0.7,
      "recall": 0.9,
      "specificity": 1.0,
      "accuracy": 0.95,
      "total_queries": 10,
      "results": [...]
    }
"""

import argparse
import json
from pathlib import Path
from oc_tools import invoke


SKILL_KEYWORD = "SKILL.md"


def was_skill_triggered(history: dict, keyword: str = SKILL_KEYWORD) -> bool:
    """
    Check if skill was triggered by scanning sessions_history for a
    tool_use Read/read call whose path contains the keyword.

    This is ground truth — no inference, no LLM judgment.
    """
    messages = history.get("messages", [])
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_use":
                continue
            if block.get("name") not in ("Read", "read"):
                continue
            inp = block.get("input", {})
            path = inp.get("path", "") or inp.get("file_path", "") or ""
            if keyword in path:
                return True
    return False


def run(raw_file: str, output_file: str) -> None:
    with open(raw_file) as f:
        raw = json.load(f)

    results = []
    triggered_count = 0
    correct_count = 0

    # 保存完整 history 到 output_file 同级的 histories/ 目录
    save_dir = Path(output_file).parent / "histories"

    for item in raw:
        query_id = item["id"]
        query = item["query"]
        expected = item["expected"]
        session_key = item["session_key"]

        history = invoke("sessions_history", {
            "sessionKey": session_key,
            "includeTools": True
        })

        # 保存完整 history（含 tool_use + tool_result）
        if save_dir:
            save_dir.mkdir(parents=True, exist_ok=True)
            history_path = save_dir / f"{query_id}_full_history.json"
            with open(history_path, "w") as f:
                json.dump(history, f, indent=2)

        triggered = was_skill_triggered(history)
        correct = (triggered == expected)

        if triggered:
            triggered_count += 1
        if correct:
            correct_count += 1

        results.append({
            "id": query_id,
            "query": query,
            "expected": expected,
            "triggered": triggered,
            "correct": correct,
            "session_key": session_key
        })

        status = "✅" if correct else "❌"
        print(f"  {status} {query_id}: triggered={triggered}, expected={expected}")

    total = len(results)
    trigger_rate = triggered_count / total if total > 0 else 0
    accuracy = correct_count / total if total > 0 else 0

    positive = [r for r in results if r["expected"]]
    negative = [r for r in results if not r["expected"]]
    recall = sum(1 for r in positive if r["triggered"]) / len(positive) if positive else 0
    specificity = sum(1 for r in negative if not r["triggered"]) / len(negative) if negative else 0

    summary = {
        "total_queries": total,
        "triggered_count": triggered_count,
        "trigger_rate": round(trigger_rate, 3),
        "accuracy": round(accuracy, 3),
        "recall": round(recall, 3),
        "specificity": round(specificity, 3),
        "results": results
    }

    with open(output_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n=== Trigger Rate Results ===")
    print(f"Total:       {total} queries")
    print(f"Recall:      {recall:.0%}  (skill triggered when it should be)")
    print(f"Specificity: {specificity:.0%}  (skill NOT triggered when it shouldn't be)")
    print(f"Accuracy:    {accuracy:.0%}")
    print(f"Saved: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze trigger rate from sessions_history")
    parser.add_argument("--raw", default="trigger_results_raw.json",
                        help="Input file with session keys (from orchestrator)")
    parser.add_argument("--output", default="trigger_rate_results.json",
                        help="Output file for results")
    args = parser.parse_args()
    run(args.raw, args.output)
