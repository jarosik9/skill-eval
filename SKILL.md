---
name: openclaw-eval-skill
description: "OpenClaw Skill evaluation framework. Use when: evaluating any OpenClaw skill quality — testing description trigger rate, comparing with/without skill output quality (quality compare), or running LLM-as-judge scoring. Works with any skill type (CLI tools, conversational, API integrations). No claude CLI dependency — runs via sessions_spawn + sessions_history. Supports parallel evaluation (6-8 workers, 5-10x performance gain). Trigger words: evaluate skill, benchmark, trigger rate, quality compare, A/B compare, skill effectiveness, skill evaluation. NOT for: debugging a single conversation, general testing tasks unrelated to skill evaluation."
---

# openclaw-eval-skill

Evaluation framework for any OpenClaw skill. No claude CLI dependency — all agent execution runs through `sessions_spawn` + `sessions_history`.

**Scope**: Works with CLI tool skills, conversational skills, and API integration skills. Assertions are chosen based on skill type.

---

## Quick Start (5 minutes)

```bash
# Run the full evaluation pipeline (parallel)
python scripts/run_orchestrator.py \
    --evals evals/example-quality.json \
    --skill-path /path/to/SKILL.md \
    --mode both \
    --output-dir workspace/iteration-1 \
    --workers 6

# Output: workspace/iteration-1/
#   ├── compare_results_raw.json
#   ├── eval-{id}-{name}/
#   │   ├── with_skill_full_history.json
#   │   ├── without_skill_full_history.json
#   │   └── metadata.json
#   ├── trigger_rate_results.json
#   └── [ready for grading]
```

**Time**: 5 evals × 2 variants (compare) + 5 evals (trigger) = 15 tasks  
Sequential: 75s → Parallel (6 workers): 12s (**6x faster**)

---

## Three Evaluation Modes

| Mode | Tests | Core Mechanism |
|------|-------|----------------|
| **Trigger Rate** | Description trigger accuracy | spawn subagents + `sessions_history` tool_use detection |
| **Quality Compare** | with skill vs without skill output quality | spawn two groups + grader subagent scoring |
| **Aggregate** | Combined report | `scripts/aggregate_benchmark.py` |

---

## Core Principles

1. **Never modify the evaluated skill** — observe only, give recommendations, don't edit skill files directly
2. **Keep eval records in workspace** — all output goes to `<workspace>/eval-workspace/<skill-name>/iteration-N/`, never pollutes the skill itself
3. **evals.json is shared across iterations** — definition lives at `eval-workspace/<skill-name>/evals.json`; each run saves a `evals-snapshot.json` to the iteration directory
4. **Keep full records** — save `full_history.json` (including all tool_use + tool_result), not just the final text

---

## agents/ Reference

| File | Purpose | When to Use |
|------|---------|-------------|
| `grader.md` | Check assertions item by item, record behavior anomalies, give priority recommendations | **Main flow**: required for every eval |
| `comparator.md` | Blind comparison — no assertions, purely judge which output is better | **Supplementary**: when unbiased comparison is needed, or assertions can't capture subjective quality |
| `analyzer.md` | After all evals complete, analyze cross-eval patterns and anomalies | **Post-analysis**: after all grading is done |

Typical order: grader (per eval) → analyzer (after all evals). comparator is optional.

---

## Standard Directory Structure

```
eval-workspace/<skill-name>/
├── evals.json                           ← Eval definition (shared across iterations)
└── iteration-1/
    ├── evals-snapshot.json              ← Snapshot of evals.json used this run
    ├── eval-report.md                   ← Evaluation report (assertions + priority + recommendations)
    └── histories/
        ├── e1_with_full_history.json    ← with skill: full tool calls + output
        ├── e1_without_full_history.json
        └── ...
```

---

## Mode 1: Trigger Rate

**Detection**: `sessions_history(includeTools=True)` scans tool_use blocks. `name=Read`, `path` contains `SKILL.md` → `triggered=True`. This is ground truth, not intent inference.

**One-liner (recommended)**:
```bash
python scripts/run_orchestrator.py \
    --evals evals/example-triggers.json \
    --skill-path <skill-path>/SKILL.md \
    --mode trigger \
    --output-dir eval-workspace/<skill-name>/iteration-1 \
    --workers 6
```

**Manual steps (for debugging)**:

### Step 1: Spawn subagents (parallel)

For each query in `evals/example-triggers.json`:
```python
# cleanup="keep" required — history must be retained for analysis
session_key = sessions_spawn(
    task=query,
    sandbox="inherit",
    cleanup="keep",
    mode="run"
)
# Parallel execution via ThreadPoolExecutor(max_workers=6)
# Use sessions_yield to wait for completion, record session_key
```

Output format `trigger_results_raw.json`:
```json
[{"id": "tq-1", "query": "...", "expected": true, "session_key": "agent:...:subagent:uuid"}]
```

### Step 2: Analyze history (parallel)

```bash
python scripts/run_trigger.py \
    --raw trigger_results_raw.json \
    --output eval-workspace/<skill-name>/iteration-1/trigger_rate_results.json \
    --workers 6
```

Performance: 10 queries × 4-6 workers → 30s vs 3 minutes (10x faster)

---

## Mode 2: Quality Compare

**One-liner (recommended)**:
```bash
python scripts/run_orchestrator.py \
    --evals evals/example-quality.json \
    --skill-path <skill-path>/SKILL.md \
    --mode compare \
    --output-dir eval-workspace/<skill-name>/iteration-1 \
    --workers 6
```

**Manual steps (for debugging)**:

### Step 1: Spawn two groups of subagents (parallel)

For each eval, spawn with_skill + without_skill variants concurrently:
```python
# with_skill: explicitly guided to read SKILL.md
with_key = sessions_spawn(
    task=f"Please first read <skill_path>/SKILL.md, then execute:\n\n{prompt}\n\nContext: {context}",
    sandbox="inherit", cleanup="keep", mode="run"
)

# without_skill: direct prompt, no skill guidance
without_key = sessions_spawn(
    task=prompt,
    sandbox="inherit", cleanup="keep", mode="run"
)
# Parallel via ThreadPoolExecutor(max_workers=6)
```

### Step 2: Extract transcripts (parallel)

```bash
python scripts/run_compare.py \
    --evals eval-workspace/<skill-name>/evals.json \
    --results compare_results_raw.json \
    --output-dir eval-workspace/<skill-name>/iteration-1 \
    --workers 6
```

`compare_results_raw.json` format:
```json
[{"eval_id": 1, "eval_name": "onboarding",
  "with_skill_session": "agent:...", "without_skill_session": "agent:..."}]
```

Script output:
- `eval-{id}-{name}/with_skill_full_history.json` — full history (including tool calls)
- `eval-{id}-{name}/with_skill_transcript.txt` — full transcript (for grader)
- `eval-{id}-{name}/metadata.json` — eval definition + assertions

Performance: 5 evals × 2 variants × 4-6 workers → 40s vs 5 minutes (7x faster)

### Step 3: Grader subagent scoring

For each eval, spawn a grader subagent using `agents/grader.md` template filled with assertions + both transcripts. Write result to `eval-{id}-{name}/grading.json`.

---

## Mode 3: Aggregate

```bash
python scripts/aggregate_benchmark.py \
    eval-workspace/<skill-name>/iteration-1 \
    --trigger trigger_rate_results.json \
    --output eval-workspace/<skill-name>/iteration-1/benchmark.json
```

---

## evals.json Format

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "name": "onboarding-fresh",
      "prompt": "Help me set up the wallet",
      "context": "Clean machine, no prior setup. For grader context only, not injected to agent.",
      "expected_output": "Install → configure → verify profile",
      "assertions": [
        {
          "id": "a1-1",
          "description": "Install command executed",
          "type": "output_contains",
          "value": "pip install"
        },
        {
          "id": "a1-2",
          "description": "Profile verified after setup",
          "type": "output_contains",
          "value": "profile current",
          "priority": true
        },
        {
          "id": "a1-3",
          "description": "[GAP] Dry-run before transfer",
          "type": "output_contains",
          "value": "dry-run",
          "note": "Best practice — failure = gap in skill design"
        }
      ]
    }
  ]
}
```

For trigger tests:
```json
{
  "id": 1,
  "name": "direct-weather",
  "query": "What's the weather in Singapore?",
  "expected": true,
  "category": "positive"
}
```

---

## Assertion Types

Works for any skill type (CLI, API, conversational).

| Type | Detection Method |
|------|-----------------|
| `output_contains` / `cli_log_contains` | Value appears in conversation or tool output |
| `output_not_contains` / `cli_log_not_contains` | Value does not appear |
| `output_count_max` | Occurrences ≤ max |
| `env_or_export_in_log` | Variable name appears in any export/setenv/env command |
| `tool_called` | Specific tool called at least once |
| `tool_not_called` | Specific tool not called |
| `conversation_contains` | Value appears anywhere in with_skill conversation |
| `conversation_not_contains` | Value does not appear |
| `conversation_contains_any` | At least one value appears |
| `conversation_not_contains_any` | All values do not appear |

**Priority assertions**: any failure → overall=FAIL, regardless of score.  
**Gap assertions** (`"note": "Best practice..."`): failure = skill design gap, not a Claude execution error.

---

## Issue Priority (grader output format)

```
🔴 P0 Critical  — Core functionality completely broken
🟠 P1 High      — Significantly impacts usability
🟡 P2 Medium    — Room for improvement but acceptable
🟢 P3 Low       — Minor polish
```

Each recommendation format: `[P0] <file>: <specific change>`

Grader **gives recommendations only, does not modify** the evaluated skill.

---

## Behavior Anomaly Tracking

In addition to assertions, grader records these behavior signals (often more diagnostic than pass/fail):

| Field | Trigger Condition |
|-------|------------------|
| `path_corrections` | Used wrong path then self-corrected |
| `retry_count` | Same command executed multiple times |
| `missing_file_reads` | Attempted to read non-existent files |
| `tool_arg_errors` | Tool called with incorrect arguments |
| `skipped_steps` | Steps explicitly required by skill were not executed |
| `hallucinations` | Fabricated non-existent commands/parameters/APIs |

---

## Key Constraints

- **`sandbox="inherit"`** — subagents must inherit skill registration environment
- **`cleanup="keep"`** — history must be retained for trigger detection
- **No claude CLI dependency** — all subagents run via `sessions_spawn`
- Skill registration: place in a real directory under `skills.load.extraDirs` (symlinks rejected by security check)
