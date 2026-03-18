# openclaw-eval-skill

任何 OpenClaw skill 的评测框架。不依赖 claude CLI，通过 `sessions_spawn` + `sessions_history` 运行。

---

## 执行流程概览

```
你（orchestrator）
  │
  ├─ 准备 evals.json（测试用例 + assertions）
  │
  ├─ spawn with_skill subagents（读 SKILL.md + 执行 prompt）
  ├─ spawn without_skill subagents（直接执行 prompt，无 skill）
  │   └─ sessions_yield 等全部完成
  │
  ├─ python scripts/run_compare.py  → 整理 transcripts + full_history.json
  │
  ├─ spawn grader subagent（agents/grader.md + 两段对话）
  │   └─ 产出 grading.json（assertions + 问题分级 + 行为异常记录）
  │
  └─ python scripts/aggregate_benchmark.py → benchmark.json
```

**Trigger Rate 流程**（测 description 触发准确率）：

```
spawn subagents（每个 query 一个）
  └─ sessions_yield 等完成
python scripts/run_trigger.py → 分析 sessions_history tool_use → trigger_rate_results.json
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
│   ├── run_compare.py          ← 整理 subagent transcripts → eval 目录
│   ├── run_trigger.py          ← 分析 sessions_history，计算 trigger rate
│   ├── aggregate_benchmark.py  ← 汇总多个 eval grading → benchmark.json
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

**sessions_history 而非 CLI 输出检测**：`sessions_history(includeTools=True)` 扫描 `tool_use` block 是否 read 了 `SKILL.md`，这是 ground truth——不是推断意图，是观察实际行为。

**with/without skill 对照组**：with_skill subagent 显式引导读取 SKILL.md；without_skill 直接执行 prompt。对比两者的 assertions 通过率，量化 skill 的实际贡献。

**不修改被测 skill**：eval 结果只给建议（P0/P1/P2/P3 分级），orchestrator 决定是否修改。

---

## 文档

| 文件 | 说明 |
|------|------|
| `SKILL.md` | 完整执行指南，含 evals.json 格式、assertion 类型、输出规范 |
| `SPEC.md` | 详细技术规格（历史参考） |
| `PLAN.md` | 设计决策背景 |
