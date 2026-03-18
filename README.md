# openclaw-eval-skill

Evaluation framework for any OpenClaw skill. No claude CLI dependency — all agent execution runs through `sessions_spawn` + `sessions_history`. **Parallel evaluation supported: 5-10x performance gain.**

**Three evaluation dimensions**: Quality + Speed + Cost (pending). See `ARCHITECTURE.md`.

---

## Quick Start

```bash
cd <skill-root>

# Run full evaluation (compare + trigger, parallel)
python scripts/run_orchestrator.py \
    --evals evals/example-quality.json \
    --skill-path <YOUR-SKILL-PATH>/SKILL.md \
    --mode both \
    --output-dir workspace/my-skill/iteration-1 \
    --workers 6
```

**Output** → `workspace/my-skill/iteration-1/`:
- `compare_results_raw.json` — raw results (with/without skill session keys)
- `eval-{id}-{name}/` — per-eval transcripts + metadata
- `trigger_rate_results.json` — description trigger rate analysis

**Performance**:
| | Sequential | Parallel (6 workers) |
|--|--|--|
| 5 evals × compare + trigger | 120s | 20s |
| **Speedup** | **baseline** | **6x faster** |

---

## Architecture

Two-layer design (v2):

```
Layer 1: Agent (main session)
  ├─ Read evals.json
  ├─ sessions_spawn → subagents
  ├─ sessions_history → extract data
  └─ Write files to raw/ directory

Layer 2: Python scripts (run via exec)
  ├─ Read JSON/txt from raw/
  ├─ Compute statistics
  └─ Generate reports
```

See `USAGE.md` for the full agent-driven workflow.

---

## Three Evaluation Modes

| Mode | Tests | Mechanism |
|------|-------|-----------|
| **Trigger Rate** | Description trigger accuracy | spawn subagents + `sessions_history` tool_use detection |
| **Quality Compare** | with skill vs without skill output quality | spawn two groups + grader subagent scoring |
| **Model Comparison** | Quality + Speed across models | spawn per model + analyze_model_compare.py |

---

## Directory Structure

```
openclaw-eval-skill/
├── SKILL.md                       ← Entry point (full execution guide)
├── README.md                      ← This file
├── USAGE.md                       ← Agent-driven operation manual
├── ARCHITECTURE.md                ← Three-dimension framework
│
├── agents/
│   ├── grader.md                  ← Checks assertions + behavior anomalies
│   ├── comparator.md              ← Blind comparison (no assertion bias)
│   └── analyzer.md                ← Cross-eval pattern analysis
│
├── scripts/
│   ├── run_orchestrator.py        ← Parallel eval runner (legacy v1)
│   ├── run_compare.py             ← Transcript extraction (v1)
│   ├── run_trigger.py             ← Trigger detection (v1)
│   ├── run_diagnostics.py         ← Description health diagnostics
│   ├── analyze_triggers.py        ← Trigger analysis from pre-fetched histories (v2)
│   ├── analyze_quality.py         ← Quality scoring from pre-fetched transcripts (v2)
│   ├── analyze_model_compare.py   ← Model comparison matrix (v2)
│   ├── analyze_latency.py         ← Latency p50/p90 from timing files (v2)
│   └── aggregate_benchmark.py     ← Summarize all eval gradings
│
└── evals/
    ├── example-quality.json       ← Quality Compare eval examples
    └── example-triggers.json      ← Trigger Rate query examples
```

---

## Mode: Trigger Rate

Test whether a skill's `description` field causes the agent to read it at the right times.

**Detection method**: `sessions_history(includeTools=True)` scans `tool_use` blocks for `Read` calls on `SKILL.md`. This is ground truth — observed behavior, not inferred intent.

```bash
python scripts/run_orchestrator.py \
    --evals evals/example-triggers.json \
    --skill-path <skill-path>/SKILL.md \
    --mode trigger \
    --output-dir workspace/<skill>/iteration-1 \
    --workers 6
```

Then run diagnostics on the results:
```bash
python scripts/run_diagnostics.py \
    --evals evals/<skill>/triggers.json \
    --skill-path <skill-path>/SKILL.md \
    --trigger-results workspace/<skill>/iteration-1/trigger_results.json \
    --output-dir workspace/<skill>/iteration-1/diagnostics/
```

---

## Mode: Quality Compare

Compare output quality with vs without skill guidance.

```bash
python scripts/run_orchestrator.py \
    --evals evals/example-quality.json \
    --skill-path <skill-path>/SKILL.md \
    --mode compare \
    --output-dir workspace/<skill>/iteration-1 \
    --workers 6
```

---

## Mode: Model Comparison

Compare Quality + Speed across models for the same skill.

```bash
python scripts/run_model_compare.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet,opus \
    --dimensions quality,speed \
    --n-runs 5 \
    --output-dir workspace/model-compare-1 \
    --workers 6
```

**Output**:
```
## Quality
| Eval       | haiku | sonnet | opus  |
|------------|-------|--------|-------|
| onboarding | 6.2 ✅ | 8.4 ✅ | 9.1 ✅ |
| transfer   | 3.1 ❌ | 7.9 ✅ | 8.7 ✅ |

## Model Dependency: HIGH ⚠️
Quality delta (haiku vs opus): 3.5
Recommendation: Skill requires sonnet+ to function reliably.
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
      "context": "Clean machine, no prior setup.",
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
        }
      ]
    }
  ]
}
```

For trigger tests, use `query` and `expected` fields instead:
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

## Key Constraints

- **`sandbox="inherit"`** — subagents must inherit the skill registration environment
- **`cleanup="keep"`** — history must be retained for trigger detection
- **No claude CLI dependency** — all subagents run via `sessions_spawn`
- Skill registration: place in a real directory under `skills.load.extraDirs` (symlinks rejected by security check)

---

## Documentation

| File | Description |
|------|-------------|
| `ARCHITECTURE.md` | Three-dimension framework (Quality + Speed + Cost) |
| `USAGE.md` | Agent-driven operation manual for all 4 workflows |
| `SKILL.md` | Full execution guide with eval formats and assertion types |
| `SPEC.md` | Detailed technical specification (historical reference) |
| `PLAN.md` | Design decisions and phase roadmap |
| `PHASE-3-*.md` | Per-phase design documents |
| `CHANGELOG.md` | Version history |
