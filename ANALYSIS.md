# openclaw-eval-skill — Source Analysis

Initial analysis of reusable components from two source skill-creators:
- **OpenClaw official skill-creator**: `/opt/homebrew/lib/node_modules/openclaw/skills/skill-creator/`
- **Claude Code skill-creator**: `<openclaw-workspace>/skills/skill-creator/`

---

## Components Reused

| Component | Source | Status |
|-----------|--------|--------|
| `agents/grader.md` | Claude Code | ✅ Direct reuse |
| `agents/comparator.md` | Claude Code | ✅ Direct reuse |
| `agents/analyzer.md` | Claude Code | ✅ Direct reuse |
| `viewer/generate_review.py` | Claude Code | ✅ Direct reuse |
| `viewer/viewer.html` | Claude Code | ✅ Direct reuse |
| `scripts/aggregate_benchmark.py` | Claude Code | ✅ Direct reuse |
| `evals.json` schema | Claude Code | ✅ Extended (added conversation_history) |

## Components Written from Scratch

| Component | Notes |
|-----------|-------|
| `scripts/run_compare.py` | Concurrent A vs B execution with conversation_history injection |
| `scripts/run_trigger.py` | sessions_history-based trigger detection |
| `scripts/run_orchestrator.py` | Parallel eval runner (Phase 3.1) |
| `scripts/run_model_compare.py` | Cross-model Quality + Speed matrix (Phase 3.4) |
| `scripts/run_diagnostics.py` | Description health diagnostics (Phase 3.2) |
| `scripts/run_latency_profile.py` | Latency p50/p90 profiling (Phase 3.5) |
| `scripts/analyze_*.py` | Pure data-analysis scripts for two-layer architecture (v2) |
| `SKILL.md` | Entry point |

## Key Design Decisions

**Execution engine**: `sessions_spawn` (not claude CLI) — no external dependency, works within OpenClaw's security model.

**Trigger detection**: `sessions_history(includeTools=True)` scanning for `Read` tool calls on `SKILL.md` — ground truth observation, not intent inference.

**Two-layer architecture (v2)**: Agent handles all OpenClaw API calls; Python scripts do pure data analysis. This resolves the `oc_tools.invoke("sessions_spawn")` unavailability in `execute_program`.
