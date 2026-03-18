#!/usr/bin/env python3
"""Run A vs B comparison for skill evaluation using sessions_spawn.

Spawns subagents via OpenClaw sessions API — no claude CLI dependency.
The orchestrator (any agent) calls this by reading SKILL.md and
following the execution flow described there.

This script is called AFTER the orchestrator has already spawned and
collected subagent results. It handles:
  - Loading conversation transcripts from sessions_history
  - Writing structured output for grader consumption

Usage:
    # Normally invoked by the orchestrator after subagents complete.
    # Can also be run directly if you have session keys:
    python run_compare.py \
        --evals evals/example-quality.json \
        --results compare_results_raw.json \
        --output-dir workspace/iteration-1

Input format (compare_results_raw.json):
    [
      {
        "eval_id": 1,
        "eval_name": "fresh-install",
        "with_skill_session": "agent:...:subagent:uuid",
        "without_skill_session": "agent:...:subagent:uuid"
      }
    ]
"""

import argparse
import json
from pathlib import Path
from oc_tools import invoke


def get_full_history(session_key: str) -> dict:
    """Fetch complete sessions_history including all tool calls and results."""
    return invoke("sessions_history", {
        "sessionKey": session_key,
        "includeTools": True  # includes tool_use + tool_result blocks
    })


def extract_full_transcript(history: dict) -> str:
    """
    Extract complete conversation transcript (all turns) from history.

    Includes all assistant text and tool call summaries — not just the final reply.
    Graders need this to check cli_log_contains, tool_called, skipped_steps etc.
    """
    messages = history.get("messages", [])
    lines = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", [])
        if isinstance(content, str):
            lines.append(f"[{role}] {content}")
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")
            if btype == "text":
                lines.append(f"[{role}] {block.get('text', '')}")
            elif btype in ("toolCall", "tool_use"):
                name = block.get("name") or block.get("toolName", "")
                args = block.get("arguments") or block.get("input", {})
                lines.append(f"[tool_call] {name}({json.dumps(args, ensure_ascii=False)})")
            elif btype == "toolResult":
                result_content = block.get("content", [])
                text = ""
                if isinstance(result_content, list):
                    for rc in result_content:
                        if isinstance(rc, dict) and rc.get("type") == "text":
                            text = rc.get("text", "")
                elif isinstance(result_content, str):
                    text = result_content
                lines.append(f"[tool_result] {text[:500]}")  # truncate long outputs
    return "\n".join(lines)


def run(evals_file: str, results_file: str, output_dir: str) -> None:
    with open(evals_file) as f:
        evals_data = json.load(f)
    with open(results_file) as f:
        results_raw = json.load(f)

    evals_by_id = {e["id"]: e for e in evals_data.get("evals", [])}
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for result in results_raw:
        eval_id = result["eval_id"]
        eval_name = result["eval_name"]
        eval_item = evals_by_id.get(eval_id, {})

        print(f"Processing eval-{eval_id} ({eval_name})...")

        # Fetch FULL history (prompt + tool calls + results + responses)
        with_history = get_full_history(result["with_skill_session"])
        without_history = get_full_history(result["without_skill_session"])

        # Full transcript includes all tool calls + results (needed for grader assertions)
        with_transcript = extract_full_transcript(with_history)
        without_transcript = extract_full_transcript(without_history)

        eval_dir = out_dir / f"eval-{eval_id}-{eval_name}"
        eval_dir.mkdir(exist_ok=True)

        # Save raw histories (source of truth)
        (eval_dir / "with_skill_full_history.json").write_text(
            json.dumps(with_history, indent=2))
        (eval_dir / "without_skill_full_history.json").write_text(
            json.dumps(without_history, indent=2))

        # Save full transcripts (all turns + tool calls, for grader)
        (eval_dir / "with_skill_transcript.txt").write_text(with_transcript)
        (eval_dir / "without_skill_transcript.txt").write_text(without_transcript)

        # Save eval metadata for grader — explicitly points to transcript files
        metadata = {
            "eval_id": eval_id,
            "eval_name": eval_name,
            "prompt": eval_item.get("prompt", ""),
            "context": eval_item.get("context", ""),
            "expected_output": eval_item.get("expected_output", ""),
            "assertions": eval_item.get("assertions", []),
            "with_skill_session": result["with_skill_session"],
            "without_skill_session": result["without_skill_session"],
            "grader_files": {
                "with_skill": "with_skill_transcript.txt",
                "without_skill": "without_skill_transcript.txt",
                "note": "Transcripts contain all tool calls and results. Use these for assertion checking."
            }
        }
        (eval_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
        print(f"  Saved to {eval_dir}/ (transcript + full_history)")

    print(f"\nDone. {len(results_raw)} evals ready for grading.")
    print(f"Next: run grade.py --workspace {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evals", required=True, help="Evals JSON file")
    parser.add_argument("--results", required=True, help="Raw results with session keys")
    parser.add_argument("--output-dir", default="workspace/iteration-1", help="Output directory")
    args = parser.parse_args()
    run(args.evals, args.results, args.output_dir)
