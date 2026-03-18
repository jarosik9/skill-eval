# openclaw-eval-skill

任何 OpenClaw skill 的评测框架。不依赖 claude CLI，通过 `sessions_spawn` + `sessions_history` 运行。**支持并发评测，5-10 倍性能提升**。

**三维度评测**：Quality（效果）+ Speed（速度）+ Cost（成本，暂缓）。详见 `ARCHITECTURE.md`。

---

## 快速开始（一行命令）

```bash
cd ~/.openclaw/workspace/operations/openclaw-eval-skill

# 运行完整评测（both 模式：compare + trigger）
python scripts/run_orchestrator.py \
    --evals evals/example-quality.json \
    --skill-path <YOUR-SKILL-PATH>/SKILL.md \
    --mode both \
    --output-dir workspace/my-skill/iteration-1 \
    --workers 6
```

**输出** → `workspace/my-skill/iteration-1/`，包含：
- `compare_results_raw.json` — 原始结果（with/without skill session keys）
- `eval-{id}-{name}/` — 每个 eval 的 transcripts + metadata + 待 grading
- `trigger_rate_results.json` — description 触发率分析结果

**时间对比**：
| | 顺序执行 | 并发 6 workers |
|--|--|--|
| 5 evals × compare + trigger | 120s | 20s |
| **性能提升** | **基线** | **6x faster** |

---

## 执行流程概览

```
你（orchestrator）
  │
  ├─ 准备 evals.json（测试用例 + assertions）
  │
  ├─ [并发] spawn with_skill subagents（读 SKILL.md + 执行 prompt）
  ├─ [并发] spawn without_skill subagents（直接执行 prompt，无 skill）
  │   └─ sessions_yield 等全部完成（ThreadPoolExecutor, 6 workers）
  │
  ├─ [并发] python scripts/run_compare.py  → 整理 transcripts + full_history.json
  │
  ├─ spawn grader subagent（agents/grader.md + 两段对话）
  │   └─ 产出 grading.json（assertions + 问题分级 + 行为异常记录）
  │
  └─ python scripts/aggregate_benchmark.py → benchmark.json
```

**Trigger Rate 流程**（测 description 触发准确率）：

```
[并发] spawn subagents（每个 query 一个，6 workers）
  └─ sessions_yield 等完成
[并发] python scripts/run_trigger.py → 分析 sessions_history tool_use → trigger_rate_results.json
```

---

## 目录结构

```
openclaw-eval-skill/
├── SKILL.md                    ← 完整执行指南（入口）
├── README.md                   ← 本文件
│
├── agents/
│   ├── grader.md               ← Grader subagent task 模板（assertions + 行为异常 + 分级建议）
│   ├── comparator.md           ← 盲测对比（不知道哪个是 with/without）
│   └── analyzer.md             ← 跑完后分析为什么 winner 赢了
│
├── scripts/
│   ├── run_orchestrator.py     ← [NEW] 一行命令并发执行所有 eval（推荐）
│   ├── run_compare.py          ← 整理 subagent transcripts → eval 目录（支持并发）
│   ├── run_trigger.py          ← 分析 sessions_history，计算 trigger rate（支持并发）
│   └── aggregate_benchmark.py  ← 汇总多个 eval grading → benchmark.json
│
└── evals/
    ├── example-quality.json    ← 示例：Quality Compare 测试用例
    └── example-triggers.json   ← 示例：Trigger Rate 查询
```

**eval 产出目录**（在 skill 目录外）：

```
eval-workspace/<skill-name>/
├── evals.json                          ← 测试用例（跨 iteration 共享）
└── iteration-1/
    ├── evals-snapshot.json             ← 本次使用的 evals.json 快照
    ├── eval-report.md                  ← 评测报告
    └── histories/
        ├── e1_with_full_history.json   ← 完整 sessions_history（含所有 tool calls）
        └── e1_without_full_history.json
```

---

## 示例：完整 Quality Compare 流程

```python
# Step 1: orchestrator spawn evals（以 eval-1 为例）
with_key = sessions_spawn(
    task="请先读 /path/to/skill/SKILL.md，然后执行：Help me set up the wallet",
    sandbox="inherit", cleanup="keep", mode="run", label="e1-with"
)
without_key = sessions_spawn(
    task="Help me set up the wallet",
    sandbox="inherit", cleanup="keep", mode="run", label="e1-without"
)
sessions_yield()  # 等两个完成

# Step 2: 整理 transcripts
# 把 session keys 写入 compare_results_raw.json，然后：
# python scripts/run_compare.py --evals evals.json --results compare_results_raw.json --output-dir eval-workspace/my-skill/iteration-1

# Step 3: spawn grader
# 读 agents/grader.md，填入 metadata.json + 两段对话，spawn grader subagent
# 结果写入 eval-workspace/my-skill/iteration-1/eval-1-onboarding/grading.json

# Step 4: 汇总
# python scripts/aggregate_benchmark.py eval-workspace/my-skill/iteration-1
```

---

## 关键设计决策

**并发执行**（新增）：
- `run_orchestrator.py` 用 `ThreadPoolExecutor` 并发 spawn subagents（6-8 workers）
- `run_compare.py` + `run_trigger.py` 都支持 `--workers` 参数
- 测试 5 evals：顺序 120s → 并发 20s（6x speedup）

**sessions_history 而非 CLI 输出检测**：`sessions_history(includeTools=True)` 扫描 `tool_use` block 是否 read 了 `SKILL.md`，这是 ground truth——不是推断意图，是观察实际行为。

**with/without skill 对照组**：with_skill subagent 显式引导读取 SKILL.md；without_skill 直接执行 prompt。对比两者的 assertions 通过率，量化 skill 的实际贡献。

**不修改被测 skill**：eval 结果只给建议（P0/P1/P2/P3 分级），orchestrator 决定是否修改。

---

## Mode 3: Model Comparison（新增）

跨模型对比 Quality + Speed 表现：

```bash
# 对比 haiku vs sonnet vs opus
python scripts/run_model_compare.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet,opus \
    --dimensions quality,speed \
    --n-runs 5 \
    --output-dir workspace/model-compare-1 \
    --workers 6
```

**输出**：
- `compare_matrix.json` — 完整 model × eval 矩阵（质量 + 速度）
- `model_comparison_report.md` — 人类可读报告（含 Tradeoff 分析）
- `raw/` — 所有 transcripts

**Sample output**：
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
Quality delta (haiku vs opus): 3.5
Recommendation: Skill requires sonnet+ to function reliably.
```

---

## 文档

| 文件 | 说明 |
|------|------|
| `ARCHITECTURE.md` | 三维度评测框架（Quality + Speed + Cost） |
| `SKILL.md` | 完整执行指南，含 evals.json 格式、assertion 类型、输出规范 |
| `SPEC.md` | 详细技术规格（历史参考） |
| `PLAN.md` | 设计决策背景 |
| `PHASE-3-*.md` | 各阶段设计文档 |
