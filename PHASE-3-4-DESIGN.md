# Phase 3.4: Model Comparison (Design Document)

**Status**: Design complete + script implemented (2026-03-18, v2 update)

**Goal**: Compare Quality + Speed across models for the same skill and prompt.

**Architecture reference**: ARCHITECTURE.md (three-dimension framework)

---

## Core Questions

**Quality dimension**:
- Does this skill work on haiku? Or does it require sonnet+?
- Which evals are model-sensitive (strong model dependency)?

**Speed dimension**:
- How much faster is haiku than sonnet?
- Is the speed gain worth the quality loss?

**Tradeoff**:
- Where is the quality vs speed balance point?

---

## Workflow

```
evals.json + skill_path
       │
       ├─ Model A: haiku   ──┐
       ├─ Model B: sonnet  ──┼─ Parallel spawn (3 × N subagents)
       └─ Model C: opus    ──┘
                             │
                         Grader (blind — model name hidden)
                             │
                      compare_matrix.json
                      model_comparison_report.md
```

**Key constraint**: Grader does not know which model produced which output (blind review), preventing evaluation bias.

---

## Technical Implementation

### sessions_spawn model parameter

```python
for model in ["anthropic/claude-haiku-4-5", "anthropic/claude-sonnet-4-6"]:
    result = invoke("sessions_spawn", {
        "task": task,
        "model": model,      # ← supported by sessions_spawn
        "sandbox": "inherit",
        "cleanup": "keep",
        "mode": "run",
        "runTimeoutSeconds": 120
    })
```

### Concurrency strategy

```python
# 3 models × 5 evals = 15 subagents, all concurrent
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = []
    for model in models:
        for eval_item in evals:
            future = executor.submit(spawn_eval, eval_item, model, skill_path)
            futures.append((model, eval_item["id"], future))
```

---

## Output Format

### compare_matrix.json

```json
{
  "skill_name": "openclaw-eval-skill",
  "models_tested": ["haiku", "sonnet", "opus"],
  "dimensions": ["quality", "speed"],
  "eval_matrix": [
    {
      "eval_id": 1,
      "eval_name": "onboarding",
      "scores": {
        "haiku":  {"triggered": true,  "quality": 6.2, "p50": 9.2,  "stable": true},
        "sonnet": {"triggered": true,  "quality": 8.4, "p50": 12.9, "stable": true},
        "opus":   {"triggered": true,  "quality": 9.1, "p50": 18.4, "stable": true}
      }
    }
  ],
  "summary": {
    "haiku":  {"avg_quality": 4.7, "avg_p50": 9.2,  "trigger_rate": 0.50},
    "sonnet": {"avg_quality": 8.2, "avg_p50": 12.9, "trigger_rate": 0.90},
    "opus":   {"avg_quality": 8.9, "avg_p50": 18.4, "trigger_rate": 0.95}
  },
  "model_dependency": {
    "level": "HIGH",
    "quality_delta": 3.5,
    "recommendation": "Skill requires sonnet+ to function reliably."
  }
}
```

### model_comparison_report.md

```markdown
## Quality Dimension
| Eval       | haiku | sonnet | opus  |
|------------|-------|--------|-------|
| onboarding | 6.2 ✅ | 8.4 ✅ | 9.1 ✅ |
| transfer   | 3.1 ❌ | 7.9 ✅ | 8.7 ✅ |

## Speed Dimension
| Eval       | haiku p50 | sonnet p50 | opus p50 |
|------------|-----------|------------|----------|
| onboarding | 9.2s ✅   | 12.9s ✅   | 18.4s ✅ |

## Model Dependency: HIGH ⚠️
Quality delta (haiku vs sonnet): 3.5 (threshold: 2.0)
Recommendation: Skill requires sonnet+. Consider simplifying SKILL.md instructions.

## Tradeoff Analysis
| Model  | Quality        | Speed (p50)    | Recommendation  |
|--------|----------------|----------------|-----------------|
| haiku  | 4.7 (-42%)     | 9.2s (+29%)    | ❌ Quality too low |
| sonnet | 8.2 (baseline) | 12.9s (baseline) | ✅ Recommended |
| opus   | 8.9 (+9%)      | 18.4s (-43%)   | ⚠️ Complex tasks only |
```

---

## Model Dependency Classification

| Delta (haiku vs sonnet) | Dependency | Recommendation |
|--------------------------|------------|----------------|
| < 1.0 | 🟢 LOW | Skill works well on haiku, can save cost |
| 1.0–2.0 | 🟡 MEDIUM | Acceptable, document known limits |
| > 2.0 | 🔴 HIGH | Simplify SKILL.md to improve haiku performance |

---

## CLI Usage

```bash
# Full evaluation: Quality + Speed
python scripts/run_model_compare.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet,opus \
    --dimensions quality,speed \
    --n-runs 5 \
    --output-dir workspace/model-compare-1 \
    --workers 8

# Quality only (fast)
python scripts/run_model_compare.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet \
    --dimensions quality \
    --output-dir workspace/model-compare-1

# Output
workspace/model-compare-1/
├── compare_matrix.json          ← machine-readable
├── model_comparison_report.md   ← human-readable
└── raw/
    ├── eval-1-haiku-run-1-transcript.txt
    └── ...
```

---

## Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Blind grader | ✅ Model name hidden | Prevent evaluation bias |
| Concurrent (model, eval) pairs | ✅ ThreadPoolExecutor | Consistent with Phase 3.1 |
| Model dependency delta threshold | 2.0 | Empirical, adjustable |
| Retain all transcripts | ✅ | Enable debugging and human review |

---

## Implementation Checklist

- [x] `scripts/run_model_compare.py` — main script
- [x] Quality scoring (heuristic, LLM grader in production)
- [x] Speed stats (p50/p90/std_dev)
- [x] Model dependency detection
- [x] Tradeoff analysis report
- [ ] Integration with ARCHITECTURE.md unified data structures
