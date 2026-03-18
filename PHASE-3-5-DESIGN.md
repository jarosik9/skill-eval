# Phase 3.5: Latency Profiling (Design Document)

**Status**: Design complete + script implemented (2026-03-18)

**Goal**: Identify skill execution speed bottlenecks — which step is slowest, and what are p50/p90.

---

## Core Questions

- How long does this skill take from trigger to task completion?
- Which step is the bottleneck (read external file? API call? multi-step reasoning?)
- Run 5 times — are the results stable (low variance)?
- How much faster is haiku vs sonnet? (pairs with Phase 3.4)

---

## Two Latency Dimensions

### Dimension 1: Total Latency

```
eval start → subagent completes = total elapsed
```

timing.json already captures this, but only as a single-run value with no statistical distribution.

### Dimension 2: Step-Level Latency

```
Steps in SKILL.md:
  Step 1: Read SKILL.md          → 2s
  Step 2: Parse config           → 0.5s
  Step 3: Fetch external URL     → 8s  ← bottleneck
  Step 4: Execute command        → 3s
  Step 5: Format output          → 1s
  Total: 14.5s
```

**Implementation**: extract timestamps from transcript, infer per-step elapsed time.

---

## Implementation Approaches

### Approach A: Repeated Runs — Statistical Distribution (simple)

```python
def profile_latency(eval_item, skill_path, n_runs=5, model="sonnet"):
    timings = []
    for i in range(n_runs):
        start = time.time()
        result = spawn_eval(eval_item, skill_path, model)
        elapsed = time.time() - start
        timings.append(elapsed)
    return {
        "p50": sorted(timings)[n_runs // 2],
        "p90": sorted(timings)[int(n_runs * 0.9)],
        "std_dev": statistics.stdev(timings)
    }
```

**Pros**: Simple, no changes to subagent logic  
**Cons**: Total latency only, no per-step breakdown

### Approach B: Transcript Tool-Call Frequency Analysis (medium complexity)

```python
def parse_step_timings(transcript: str) -> list:
    """
    Extract step-level timing from transcript.
    Scans for tool call names and their approximate frequency.
    Returns qualitative step breakdown, not wall-clock time.
    """
```

**Pros**: Shows which steps are called most / least  
**Cons**: No timestamps in OpenClaw transcripts; approximation only

### Approach C: Structured Timing Markers (most accurate, changes subagent)

```python
task = f"""
{skill_instructions}

IMPORTANT: After each major step, output a timing marker:
[STEP_START: step_name] ... [STEP_END: step_name]
This is for performance profiling only.
"""
```

**Pros**: Precise, structured  
**Cons**: Changes subagent behavior, may affect eval validity

---

## Recommended: Approach A + B

- **Default**: Approach A (5 repeated runs, total latency distribution) — simple and reliable
- **Deep analysis**: Approach B (parse transcript tool-call frequency) — optional, add `--step-level` flag

---

## Output Format

### latency_report.json

```json
{
  "skill_name": "openclaw-eval-skill",
  "model": "sonnet",
  "n_runs": 5,
  "evals": [
    {
      "eval_id": 1,
      "eval_name": "onboarding",
      "timings_seconds": [12.1, 13.5, 11.8, 14.2, 12.9],
      "p50": 12.9,
      "p90": 14.2,
      "mean": 12.9,
      "std_dev": 0.89,
      "stable": true,
      "stability_level": "HIGH"
    }
  ],
  "summary": {
    "sonnet": { "avg_p50": 12.9, "avg_p90": 14.2, "stability": "HIGH" }
  }
}
```

### latency_report.md

```markdown
# Latency Profile: openclaw-eval-skill

Model: sonnet | Runs: 5

## Summary
| Eval       | p50   | p90   | Stability |
|------------|-------|-------|-----------|
| onboarding | 12.9s | 14.2s | ✅ HIGH   |
| transfer   | 18.4s | 32.1s | ⚠️ LOW    |

## Unstable Evals

### transfer — HIGH VARIANCE ⚠️
p50: 18.4s, p90: 32.1s, std_dev: 5.2s
Recommendation: Add timeout + retry logic in SKILL.md step 4.
```

---

## Stability Classification

| std_dev | Level | Action |
|---------|-------|--------|
| < 1s | 🟢 HIGH | Stable, no action needed |
| 1–3s | 🟡 MEDIUM | Acceptable, monitor |
| > 3s | 🔴 LOW | Skill has non-determinism (network/tool); consider retry logic |

---

## CLI Usage

```bash
# Basic: total latency distribution (5 runs)
python scripts/run_latency_profile.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --n-runs 5 \
    --output-dir workspace/latency-1

# Deep: step-level tool frequency analysis
python scripts/run_latency_profile.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --n-runs 5 \
    --step-level \
    --output-dir workspace/latency-1

# Sequential mode (no concurrency interference, more accurate)
python scripts/run_latency_profile.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet \
    --n-runs 5 \
    --sequential \
    --output-dir workspace/latency-1
```

---

## Pairing with Phase 3.4

```bash
# Multi-model speed comparison
python scripts/run_latency_profile.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet \
    --n-runs 5 \
    --output-dir workspace/latency-1

# Output includes:
# haiku avg p50: 9.2s
# sonnet avg p50: 12.9s
# haiku is 29% faster
```

---

## Notes

- n_runs minimum 3 for meaningful statistics; default 5
- Concurrent n_runs are faster but may have interference; use `--sequential` for precise measurement
- Transcript timestamps depend on OpenClaw output format; Approach B may need adaptation
- p90 is only meaningful with n_runs ≥ 10; with 5 runs, p90 = max value

---

## Implementation Checklist

- [x] `scripts/run_latency_profile.py` — Approach A + B
- [x] `--sequential` flag for precise measurement
- [x] Multi-model support (`--models`)
- [x] Stability classification
- [x] `scripts/analyze_latency.py` — v2 pure data analysis version
