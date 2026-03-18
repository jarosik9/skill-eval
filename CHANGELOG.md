# CHANGELOG

## v0.6 — Public Release Prep (2026-03-19)

### Breaking Changes

- **Single recommended usage**: removed `run_orchestrator.py` one-liner from documentation
  - v1 scripts (`run_orchestrator.py`, `run_compare.py`, `run_trigger.py`) moved to legacy status
  - All docs now point to `USAGE.md` agent-driven workflows only
  - Scripts remain in repo for reference but are not the recommended path

### Added

- `.gitignore` — excludes `workspace/` and `eval-workspace/` output directories
- `LICENSE` — MIT
- `CONTRIBUTING.md` — eval set contribution guidelines
- `docs/` directory — moved internal design docs (SPEC, PLAN, ARCHITECTURE, PHASE-3-*)
- `SKILL.md` metadata block with emoji
- Result Viewer section in README

### Fixed

- Removed committed test artifacts from `workspace/`
- Pinned `requirements.txt` version range

### Simplified

- SKILL.md reduced from 360 lines to 160 lines
- Root directory now contains only: SKILL.md, README.md, USAGE.md, CHANGELOG.md, LICENSE, CONTRIBUTING.md

---

## v0.5 — All Phase 3 Scripts Implemented (2026-03-18)

### New Features

**🔬 Description Diagnostics (Phase 3.2)**
- `scripts/run_diagnostics.py` — diagnose description quality, output prioritized recommendations
  - Multi-dimension health scoring: recall/specificity/clarity/coverage + composite
  - Failure classification: critical/high/medium/low + is_worth_fixing
  - Root cause analysis: missing_keyword/too_broad/ambiguous/eval_artifact
  - Rough improvement estimate
  - Output: `diagnosis.json` + `RECOMMENDATIONS.md`

```bash
python scripts/run_diagnostics.py \
    --evals evals/example-triggers.json \
    --skill-path ./SKILL.md \
    --trigger-results workspace/iter-1/trigger_rate_results.json \
    --output-dir workspace/diagnostics-1
```

**⏱️ Latency Profiling (Phase 3.5)**
- `scripts/run_latency_profile.py` — measure execution speed, identify bottlenecks
  - p50/p90/std_dev statistical distribution
  - Stability classification (HIGH/MEDIUM/LOW, std_dev threshold)
  - `--step-level`: extract step frequency from transcripts
  - `--sequential`: serial mode for more accurate measurement (no concurrency interference)
  - Multi-model speed comparison (pairs with Phase 3.4)
  - Output: `latency_report.json` + `latency_report.md`

```bash
python scripts/run_latency_profile.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet \
    --n-runs 5 \
    --output-dir workspace/latency-1
```

---

## v0.4 — Model Comparison + Three-Dimension Framework (2026-03-18)

### New Features

**🔄 Model Comparison (Phase 3.4)**
- `scripts/run_model_compare.py` — cross-model Quality + Speed comparison
  - `--models haiku,sonnet,opus` multi-model parallel evaluation
  - `--dimensions quality,speed` dimension selection
  - `--n-runs 5` multiple runs for speed statistics p50/p90
  - Blind grader (model name hidden from grader to avoid bias)
  - Automatic model dependency detection (delta threshold = 2.0)

**📐 Three-Dimension Framework**
- `ARCHITECTURE.md` — three-dimension evaluation architecture
  - Quality: trigger_rate, quality_score, assertions
  - Speed: p50, p90, std_dev, stability
  - Cost: deferred (tokens, $/1k evals)
- Unified data structures: EvalResult / QualityMetrics / SpeedMetrics

### Usage

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

---

## v0.3 — Parallel Execution (2026-03-18)

### New Features

**🚀 Parallel Evaluation Orchestrator**
- `scripts/run_orchestrator.py` — one-liner for end-to-end evaluation
  - Supports `compare` and `trigger` modes
  - Configurable worker pool (default: 6)
  - Performance: 5-10x speedup vs sequential

**⚡ Concurrent Processing**
- `run_compare.py` — parallel transcript extraction & metadata generation
  - ThreadPoolExecutor with configurable workers
  - Batch process multiple evals simultaneously
  - Real-time progress feedback

- `run_trigger.py` — parallel trigger detection analysis
  - Concurrent session_history fetching & analysis
  - Per-query error tracking with detailed logs
  - Metrics include elapsed_seconds for benchmarking

### Performance Improvements

| Benchmark | Sequential | Parallel (6 workers) | Speedup |
|-----------|-----------|----------------------|---------|
| 5 evals × compare (with+without) | 90s | 15s | 6x |
| 5 evals × trigger | 30s | 5s | 6x |
| Combined (compare+trigger) | 120s | 20s | 6x |

---

## v0.2 — Visualization (2026-03-17)

- generate_review.py — HTML report generation
- viewer.html — side-by-side comparison UI
- Feedback collection (eval-viewer)

---

## v0.1 — Core Framework (2026-03-08)

- SKILL.md entry point
- evals.json schema definition
- run_compare.py — A vs B comparison
- run_trigger.py — trigger rate detection
- grade.py — LLM-as-judge
- aggregate_benchmark.py — results aggregation
