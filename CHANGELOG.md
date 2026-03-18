# CHANGELOG

## v0.5 — All Phase 3 Scripts Implemented（2026-03-18）

### New Features

**🔬 Description Diagnostics (Phase 3.2)**
- `scripts/run_diagnostics.py` — 诊断 description 质量，输出分级建议
  - 多维度健康评分：recall/specificity/clarity/coverage + composite
  - 失败分级：critical/high/medium/low + is_worth_fixing
  - 根因分析：missing_keyword/too_broad/ambiguous/eval_artifact
  - 预期改进估算（粗估）
  - 输出：`diagnosis.json` + `RECOMMENDATIONS.md`

```bash
python scripts/run_diagnostics.py \
    --evals evals/example-triggers.json \
    --skill-path ./SKILL.md \
    --trigger-results workspace/iter-1/trigger_rate_results.json \
    --output-dir workspace/diagnostics-1
```

**⏱️ Latency Profiling (Phase 3.5)**
- `scripts/run_latency_profile.py` — 测量执行速度，识别瓶颈
  - p50/p90/std_dev 统计分布
  - 稳定性判断（HIGH/MEDIUM/LOW，std_dev 阈值）
  - `--step-level`：从 transcript 提取步骤频率
  - `--sequential`：串行模式，更精确（无并发干扰）
  - 多模型速度对比（联动 Phase 3.4）
  - 输出：`latency_report.json` + `latency_report.md`

```bash
python scripts/run_latency_profile.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet \
    --n-runs 5 \
    --output-dir workspace/latency-1
```

---

## v0.4 — Model Comparison + Three-Dimension Framework（2026-03-18）

### New Features

**🔄 Model Comparison (Phase 3.4)**
- `scripts/run_model_compare.py` — 跨模型对比 Quality + Speed
  - 支持 `--models haiku,sonnet,opus` 多模型并发评测
  - 支持 `--dimensions quality,speed` 维度选择
  - 支持 `--n-runs 5` 多次运行统计 p50/p90
  - Grader blind（评分时不透露模型名，避免偏见）
  - Model dependency 自动判断（delta threshold = 2.0）

**📐 Three-Dimension Framework**
- `ARCHITECTURE.md` — 三维度评测架构文档
  - Quality: trigger_rate, quality_score, assertions
  - Speed: p50, p90, std_dev, stability
  - Cost: 暂缓（tokens, $/1k evals）
- 统一数据结构：EvalResult / QualityMetrics / SpeedMetrics

### Usage

```bash
# Quality + Speed 完整评测
python scripts/run_model_compare.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet,opus \
    --dimensions quality,speed \
    --n-runs 5 \
    --output-dir workspace/model-compare-1 \
    --workers 6
```

### Output

```
workspace/model-compare-1/
├── compare_matrix.json         ← 完整 model × eval 矩阵
├── model_comparison_report.md  ← 人类可读报告
└── raw/                        ← 所有 transcripts
```

### Design Documents

- `PHASE-3-2-DESIGN.md` — Description Diagnostics（Quality 深入分析）
- `PHASE-3-4-DESIGN.md` — Model Comparison（跨维度对比）
- `PHASE-3-5-DESIGN.md` — Latency Profiling（Speed 深入分析）

---

## v0.3 — Parallel Execution（2026-03-18）

### New Features

**🚀 Parallel Evaluation Orchestrator**
- `scripts/run_orchestrator.py` — One-liner for end-to-end evaluation
  - Supports both `compare` and `trigger` modes
  - Configurable worker pool (default: 6)
  - Performance: 5-10x speedup vs sequential

**⚡ Concurrent Processing**
- `run_compare.py` — Parallel transcript extraction & metadata generation
  - ThreadPoolExecutor with configurable workers
  - Batch process multiple evals simultaneously
  - Real-time progress feedback
  
- `run_trigger.py` — Parallel trigger detection analysis
  - Concurrent session_history fetching & analysis
  - Per-query error tracking with detailed logs
  - Metrics include elapsed_seconds for benchmarking

### Performance Improvements

| Benchmark | Sequential | Parallel (6 workers) | Speedup |
|-----------|-----------|----------|---------|
| 5 evals × compare (with+without) | 90s | 15s | 6x |
| 5 evals × trigger | 30s | 5s | 6x |
| Combined (compare+trigger) | 120s | 20s | 6x |

**Real-world scaling**:
- 10 evals: 240s → 40s
- 20 evals: 480s → 80s

### API Changes

#### run_compare.py

**New**: `--workers` argument (default: 4)
```bash
python scripts/run_compare.py \
    --evals evals.json \
    --results results.json \
    --output-dir workspace/iter-1 \
    --workers 6  # NEW
```

#### run_trigger.py

**New**: `--workers` argument (default: 4)
```bash
python scripts/run_trigger.py \
    --raw trigger_results_raw.json \
    --output results.json \
    --workers 6  # NEW
```

Output format updated:
```json
{
  "total_queries": 5,
  "triggered_count": 4,
  "error_count": 0,
  "elapsed_seconds": 5.3,  // NEW
  "trigger_rate": 0.8,
  "accuracy": 0.8,
  "recall": 1.0,
  "specificity": 0.5,
  "results": [...]
}
```

#### run_orchestrator.py (NEW)

```bash
python scripts/run_orchestrator.py \
    --evals evals/example-quality.json \
    --skill-path /path/to/SKILL.md \
    --mode [compare|trigger|both] \
    --output-dir workspace/iter-1 \
    --workers 6
```

**Responsibilities**:
1. Parse evals.json
2. Spawn subagents in parallel (ThreadPoolExecutor)
3. Call run_compare.py & run_trigger.py with appropriate arguments
4. Summarize results and timing

### Documentation Updates

- SKILL.md: Added quick-start section with one-liner usage
- README.md: Added parallel execution overview, performance table
- PLAN.md: Remains unchanged (historical reference)

### Internal Changes

**Thread Safety**:
- Used `as_completed()` for non-blocking result collection
- File writes are per-worker (no contention)
- JSON serialization with `ensure_ascii=False` for Unicode support

**Error Handling**:
- Per-task error tracking (not fail-fast)
- Graceful degradation: partial results on some worker failures
- Exit code reflects overall success (all evals processed)

---

## v0.2 — Visualization（2026-03-17）

- [x] generate_review.py — HTML report generation
- [x] viewer.html — Side-by-side comparison UI
- [x] feedback collection (eval-viewer)

---

## v0.1 — Core Framework（2026-03-08）

- [x] SKILL.md entry point
- [x] evals.json schema definition
- [x] run_compare.py — A vs B comparison
- [x] run_trigger.py — Trigger rate detection
- [x] grade.py — LLM-as-judge
- [x] aggregate_benchmark.py — Results aggregation
