# OpenClaw Eval Skill 架构文档

**版本**：v0.4（2026-03-18）

---

## 三维度评测框架

所有 skill 评测统一使用三个维度：

```
                    ┌─────────────────────────────────┐
                    │           Skill Eval            │
                    └─────────────────────────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           ▼                       ▼                       ▼
    ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
    │   Quality   │         │   Speed     │         │    Cost     │
    │   (效果)    │         │   (速度)    │         │   (成本)    │
    └─────────────┘         └─────────────┘         └─────────────┘
           │                       │                       │
    ┌──────┴──────┐         ┌──────┴──────┐         ┌──────┴──────┐
    │ trigger_rate│         │ p50 / p90   │         │ tokens_in   │
    │ quality_score│        │ std_dev     │         │ tokens_out  │
    │ assertions  │         │ bottleneck  │         │ api_cost    │
    │ recall      │         │ stability   │         │ $/1k_evals  │
    │ specificity │         │             │         │             │
    └─────────────┘         └─────────────┘         └─────────────┘
```

### 维度定义

| 维度 | 回答的问题 | 核心指标 | 状态 |
|------|-----------|----------|------|
| **Quality** | skill 能不能完成任务？ | trigger_rate, quality_score | ✅ 已实现 |
| **Speed** | skill 跑得快不快？稳不稳？ | p50, p90, std_dev | 📋 设计完成 |
| **Cost** | skill 花多少钱？ | tokens, $/1k evals | 🔮 暂缓 |

---

## 统一数据结构

### EvalResult（单次评测结果）

```python
@dataclass
class EvalResult:
    eval_id: int
    eval_name: str
    model: str
    
    # Quality 维度
    quality: QualityMetrics
    
    # Speed 维度
    speed: SpeedMetrics
    
    # Cost 维度（暂缓）
    cost: Optional[CostMetrics] = None

@dataclass
class QualityMetrics:
    triggered: bool
    quality_score: float          # 0-10, by grader
    assertions_passed: int
    assertions_total: int
    recall: Optional[float]       # for trigger tests
    specificity: Optional[float]  # for trigger tests

@dataclass
class SpeedMetrics:
    latency_seconds: float        # 单次
    p50: Optional[float]          # 多次运行
    p90: Optional[float]
    std_dev: Optional[float]
    stable: bool                  # std_dev < 3s
    bottleneck: Optional[str]     # step-level 分析结果

@dataclass
class CostMetrics:
    tokens_in: int
    tokens_out: int
    api_cost_usd: float
    cost_per_1k_evals: float
```

### ComparisonMatrix（跨模型对比）

```python
@dataclass
class ComparisonMatrix:
    skill_name: str
    models: list[str]
    dimensions: list[str]         # ["quality", "speed"]
    timestamp: str
    
    # 每个 (eval, model) 组合的完整结果
    results: dict[tuple[int, str], EvalResult]
    
    # 汇总统计
    summary: dict[str, ModelSummary]

@dataclass
class ModelSummary:
    model: str
    avg_quality: float
    avg_latency: float
    trigger_rate: float
    stability: str                # "HIGH" | "MEDIUM" | "LOW"
```

---

## 工具分层

```
┌─────────────────────────────────────────────────────────────────┐
│                    run_orchestrator.py                          │
│                    （入口 + 调度）                                │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│ run_compare   │       │ run_trigger   │       │run_model_compare│
│ (A vs B)      │       │ (触发率)      │       │ (跨模型+维度)  │
└───────────────┘       └───────────────┘       └───────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │     spawn_eval()      │
                    │    (核心执行单元)      │
                    └───────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            ┌─────────────┐         ┌─────────────┐
            │   grader    │         │   profiler  │
            │ (质量评分)   │         │ (速度统计)  │
            └─────────────┘         └─────────────┘
```

### 工具职责

| 工具 | 输入 | 输出 | 维度 |
|------|------|------|------|
| `run_compare.py` | evals + skill A/B | quality 对比 | Quality |
| `run_trigger.py` | evals + skill | trigger_rate | Quality |
| `run_model_compare.py` | evals + skill + models | 跨模型矩阵 | Quality + Speed |
| `run_diagnostics.py` | trigger_results + skill | 诊断报告 | Quality（深入） |
| `run_latency_profile.py` | evals + skill | 速度分析 | Speed（深入） |

---

## Phase 与维度的映射

| Phase | 维度覆盖 | 深度 | 场景 |
|-------|---------|------|------|
| **3.1** Parallel | - | - | 加速执行 |
| **3.2** Diagnostics | Quality | 深 | description 诊断 |
| **3.4** Model Compare | Quality + Speed | 广 | 模型选择 |
| **3.5** Latency Profile | Speed | 深 | 瓶颈定位 |

**设计原则**：
- 3.4 做广度（多维度，多模型）
- 3.2 / 3.5 做深度（单维度，深入分析）

---

## 输出文件约定

```
workspace/
├── iteration-{N}/
│   ├── eval-{id}-{name}/
│   │   ├── with_skill_transcript.txt
│   │   ├── without_skill_transcript.txt
│   │   └── timing.json              # 包含 speed 数据
│   ├── trigger_rate_results.json    # Quality: trigger
│   ├── quality_scores.json          # Quality: grader
│   └── benchmark.md
│
├── model-compare-{N}/
│   ├── compare_matrix.json          # 完整矩阵
│   ├── model_comparison_report.md   # 人类可读
│   └── raw/
│       ├── eval-1-haiku-transcript.txt
│       ├── eval-1-sonnet-transcript.txt
│       └── ...
│
├── diagnostics-{N}/
│   ├── diagnosis.json
│   └── RECOMMENDATIONS.md
│
└── latency-{N}/
    ├── latency_report.json
    └── latency_report.md
```

---

## CLI 参数约定

### 通用参数

```bash
--evals         # evals.json 路径
--skill-path    # SKILL.md 路径
--output-dir    # 输出目录
--workers       # 并发数（默认 6）
```

### 维度相关参数

```bash
--dimensions quality,speed    # 选择评测维度（3.4）
--n-runs 5                    # speed 维度需要多次运行
--models haiku,sonnet,opus    # 模型列表
--step-level                  # speed 深度分析（3.5）
```

---

## 扩展点

### 添加新维度

1. 在 `EvalResult` 添加新的 metrics dataclass
2. 在 `spawn_eval()` 里收集数据
3. 在输出报告里添加对应 section

### 添加新工具

1. 复用 `spawn_eval()` 核心函数
2. 实现特定的分析逻辑
3. 输出符合约定的 JSON + Markdown

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1 | 2026-03-17 | 初始设计，单一 quality 维度 |
| v0.3 | 2026-03-18 | 并发执行 |
| v0.4 | 2026-03-18 | 三维度框架（Quality + Speed + Cost） |
