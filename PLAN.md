# openclaw-eval-skill — Design Plan

**Status**: v0.4 (2026-03-18)

**Architecture reference**: ARCHITECTURE.md (three-dimension framework)

---

## Background

Merges OpenClaw's official skill-creator (structure standards) with Claude Code's skill-creator (eval loop) into a focused **skill evaluation and comparison** tool.

Core use case: iterating on Agent Wallet skill development — testing different skill formulations, different conversation contexts, and their effect on agent behavior.

---

## Three-Dimension Evaluation Framework (v0.4)

All evaluations use three unified dimensions:

| Dimension | Question Answered | Key Metrics | Status |
|-----------|-------------------|-------------|--------|
| **Quality** | Can the skill complete the task? | trigger_rate, quality_score | ✅ Implemented |
| **Speed** | Is the skill fast and stable? | p50, p90, std_dev | 📋 Design complete |
| **Cost** | How much does it cost to run? | tokens, $/1k evals | 🔮 Deferred |

---

## Core Requirements

### 1. A vs B Comparison (not just skill vs no-skill)

- Skill A (old version) vs Skill B (new version)
- Two different skills (which fits a scenario better)
- Same skill, different conversation history

### 2. Conversation History as an Input Variable

- With context (has conversation_history) vs without context
- Test whether agent adapts responses based on history
- Test whether skill generalizes sufficiently

### 3. Universal Evaluation Framework

- Not tied to any specific skill
- JSON-defined test scenarios

---

## Supported Comparison Types

| Comparison Variable | Fixed Variable |
|---------------------|----------------|
| **with skill / without skill** | skill_path + prompt |
| **Skill A vs Skill B** | prompt |
| **With context / without context** | skill_path + prompt |
| **Memory comparison** | conversation_history | skill_path + prompt |
| **Mixed comparison** | both can vary | same prompt |

---

## Evaluation Methods

### LLM-as-Judge (primary)

- Automated scoring against a rubric
- Raw output retained for human review
- Multi-dimension scoring (Path Selection / Step Completeness / Error Handling / Output Quality)

### Human Review (supplementary)

- eval-viewer generates HTML report
- Side-by-side A vs B output display
- Downloadable feedback.json

---

## Two-Layer Architecture (v2)

```
Layer 1: Agent (main session)
  - Read evals.json
  - sessions_spawn → subagents
  - sessions_history → extract data
  - Write raw/ files

Layer 2: Python scripts (exec)
  - Read raw/ files
  - Compute statistics
  - Generate reports
```

**Rationale**: `oc_tools.invoke("sessions_spawn")` is not available inside `execute_program`. The agent (main session) handles all OpenClaw API calls directly; scripts are pure data processors.

---

## Development Phases

### Phase 1: Core (v0.1) ✅ Complete

- SKILL.md entry point
- evals.json schema (SPEC.md)
- run_compare.py — A vs B + context mode
- run_trigger.py — trigger rate test (Mode 3)
- grade.py — LLM-as-judge
- aggregate_benchmark.py — results aggregation

### Phase 2: Visualization (v0.2) ✅ Complete

- generate_review.py — HTML report
- viewer.html — side-by-side view
- Feedback collection (eval-viewer built-in)

### Phase 3: Advanced Features

**Phase 3.1: Concurrent Execution (v0.3) ✅ Complete (2026-03-18)**

- `run_orchestrator.py` — one-liner parallel eval execution
- `run_compare.py` + `run_trigger.py` — `--workers` parameter added
- ThreadPoolExecutor concurrent spawn + fetch + extract
- 5-10x performance improvement (5 evals: 120s → 20s)

**Phase 3.2: Description Diagnostics (v0.4) ✅ Script complete**

Design: PHASE-3-2-DESIGN.md
- `run_diagnostics.py` — diagnose description quality, output classified recommendations
- Multi-dimension scoring (recall/specificity/clarity/coverage)
- Severity classification (critical/high/medium/low)
- Diagnostic report RECOMMENDATIONS.md
- **No auto-optimization** (avoids local optimum) — diagnose + human decision

**Phase 3.4: Model Comparison (v0.5) ✅ Script complete**

Design: PHASE-3-4-DESIGN.md
- `run_model_compare.py` — multi-model parallel evaluation
- `--dimensions quality,speed` parameter
- Model × eval scoring matrix
- Model dependency detection (delta threshold)
- Also covers: Cost Efficiency (quality/cost ratio)

**Phase 3.5: Latency Profiling (v0.6) ✅ Script complete**

Design: PHASE-3-5-DESIGN.md
- `run_latency_profile.py` — multiple runs, statistical p50/p90
- Option A: total latency distribution (default)
- Option B: step-level transcript parsing (`--step-level`)
- Multi-model support (paired with 3.4, outputs haiku vs sonnet speed comparison)
- Stability classification (std_dev threshold)

---

## Deferred

**Phase 3.3: True Session Resumption**  (2026-03-18 deferred)

- Tools already implemented: `extract_session_history.py` + `build_evals_with_context.py`
- Design: PHASE-3-3-DESIGN.md
- Deferred reason: not the most urgent need at this stage; focus on 3.2 and 3.4 first
- Can be revisited when testing "memory continuity" is needed

---

## Risk Analysis

| Risk | Level | Mitigation |
|------|-------|------------|
| sessions_spawn unavailable in execute_program | 🔴 Fixed | Two-layer architecture: agent handles spawning |
| Conversation history injection not realistic | 🟡 Medium | v1 accepts this, v2 uses real session extraction |
| LLM judge unstable | 🟡 Medium | Multiple runs + average, retain raw output |
| eval-viewer requires browser | 🟢 Low | Supports `--static` for static HTML generation |

---

## Success Criteria

1. Complete an A vs B comparison in under 5 minutes
2. LLM judge scoring agrees with human judgment at >80%
3. Output format clear, human review frictionless
4. Reusable for any skill, not limited to Agent Wallet
