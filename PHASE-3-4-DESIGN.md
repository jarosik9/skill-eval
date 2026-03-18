# Phase 3.4：Model Comparison（设计文档）

**状态**：设计完成，待实现（2026-03-18，v2 更新）

**目标**：同一 skill + 同一 prompt，对比不同模型的 **Quality + Speed** 表现

**架构参考**：ARCHITECTURE.md（三维度框架）

---

## 核心问题

**Quality 维度**：
- 这个 skill 在 haiku 下能用吗？还是必须 sonnet+？
- 哪些 eval 对模型敏感（strong model dependency）？

**Speed 维度**：
- haiku 比 sonnet 快多少？
- 速度提升是否值得质量损失？

**Tradeoff**：
- 质量 vs 速度的平衡点在哪里？

---

## 工作流

```
evals.json + skill_path
       │
       ├─ Model A: haiku   ──┐
       ├─ Model B: sonnet  ──┼─ 并发 spawn（3 × N subagents）
       └─ Model C: opus    ──┘
                             │
                         grader（blind，不知道模型）
                             │
                      compare_matrix.json
                      model_comparison_report.md
```

**关键约束**：grader 不知道是哪个模型在回答（blind review），避免偏见。

---

## 技术实现

### sessions_spawn 的 model 参数

```python
# 对不同模型 spawn 相同 task
for model in ["anthropic/claude-haiku-4-5", "anthropic/claude-sonnet-4-6"]:
    result = invoke("sessions_spawn", {
        "task": task,
        "model": model,      # ← sessions_spawn 支持此参数
        "sandbox": "inherit",
        "cleanup": "keep",
        "mode": "run"
    })
```

### 并发策略

```python
# 3 模型 × 5 eval = 15 subagents，全部并发
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = []
    for model in models:
        for eval_item in evals:
            future = executor.submit(spawn_eval, eval_item, model, skill_path)
            futures.append((model, eval_item["id"], future))
    
    results = {}
    for model, eval_id, future in futures:
        output = future.result()
        results[(model, eval_id)] = output
```

### 评分矩阵构建

```python
matrix = {}
for eval_item in evals:
    eval_id = eval_item["id"]
    matrix[eval_id] = {}
    for model in models:
        output = results[(model, eval_id)]
        score = grade(output, eval_item["expected_output"])
        matrix[eval_id][model] = score
```

---

## 输出格式

### compare_matrix.json

```json
{
  "skill_name": "openclaw-eval-skill",
  "models_tested": ["haiku", "sonnet", "opus"],
  "timestamp": "2026-03-18T21:00:00+08:00",
  "eval_matrix": [
    {
      "eval_id": 1,
      "eval_name": "onboarding",
      "scores": {
        "haiku":  {"triggered": true,  "quality": 6.2, "assertions_passed": 3, "assertions_total": 6},
        "sonnet": {"triggered": true,  "quality": 8.4, "assertions_passed": 5, "assertions_total": 6},
        "opus":   {"triggered": true,  "quality": 9.1, "assertions_passed": 6, "assertions_total": 6}
      }
    },
    {
      "eval_id": 2,
      "eval_name": "transfer",
      "scores": {
        "haiku":  {"triggered": false, "quality": 3.1, "assertions_passed": 1, "assertions_total": 6},
        "sonnet": {"triggered": true,  "quality": 7.9, "assertions_passed": 4, "assertions_total": 6},
        "opus":   {"triggered": true,  "quality": 8.7, "assertions_passed": 5, "assertions_total": 6}
      }
    }
  ],
  "summary": {
    "haiku":  {"avg_quality": 4.7, "trigger_rate": 0.50, "avg_assertions": 2.0},
    "sonnet": {"avg_quality": 8.2, "trigger_rate": 0.90, "avg_assertions": 4.5},
    "opus":   {"avg_quality": 8.9, "trigger_rate": 0.95, "avg_assertions": 5.5}
  },
  "model_dependency": {
    "level": "HIGH",
    "reason": "haiku quality 4.7 vs sonnet 8.2, delta = 3.5 (>2.0 threshold)",
    "recommendation": "Skill requires sonnet+ to function reliably. Consider simplifying SKILL.md instructions."
  }
}
```

### model_comparison_report.md（人类可读）

```markdown
# Model Comparison Report: openclaw-eval-skill

## Quality Dimension

| Eval | haiku | sonnet | opus |
|------|-------|--------|------|
| onboarding | 6.2 ✅ | 8.4 ✅ | 9.1 ✅ |
| transfer   | 3.1 ❌ | 7.9 ✅ | 8.7 ✅ |
| **Average** | **4.7** | **8.2** | **8.9** |

## Speed Dimension

| Eval | haiku p50 | sonnet p50 | opus p50 |
|------|-----------|------------|----------|
| onboarding | 9.2s | 12.9s | 18.4s |
| transfer   | 15.1s | 18.4s | 25.2s |
| **Average** | **12.2s** | **15.7s** | **21.8s** |

## Model Dependency: HIGH ⚠️

**Quality Delta (haiku vs sonnet)**: 3.5 (threshold: 2.0)

**Speed Gain (haiku vs sonnet)**: 22% faster

## Tradeoff Analysis

| Model | Quality | Speed | Recommendation |
|-------|---------|-------|----------------|
| haiku | 4.7 (-42%) | 12.2s (+22%) | ❌ 质量损失太大 |
| sonnet | 8.2 (baseline) | 15.7s (baseline) | ✅ 推荐：平衡选择 |
| opus | 8.9 (+9%) | 21.8s (-39%) | ⚠️ 仅复杂任务使用 |

## Per-Eval Analysis

### eval-2: transfer — HAIKU FAILS ❌

haiku output:
> "I'll help you transfer. Please provide the wallet address..."
> (Stops here, doesn't complete the transfer)

sonnet output:
> "Reading SKILL.md... Using caw transfer command with --to flag..."
> (Completes the transfer correctly)

Root cause: Haiku doesn't independently read SKILL.md when it's complex.
Fix: Add explicit "FIRST: read SKILL.md" instruction in description.
```

---

## 模型依赖度判断

| Delta（haiku vs sonnet） | 依赖程度 | 建议 |
|--------------------------|----------|------|
| < 1.0 | 🟢 LOW — 无依赖 | skill 设计好，可以用 haiku 省成本 |
| 1.0–2.0 | 🟡 MEDIUM — 轻依赖 | 可接受，记录已知限制 |
| > 2.0 | 🔴 HIGH — 强依赖 | 简化 SKILL.md，改善 haiku 下的表现 |

---

## CLI 用法

```bash
# 完整评测：Quality + Speed
python scripts/run_model_compare.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet,opus \
    --dimensions quality,speed \
    --n-runs 5 \
    --output-dir workspace/model-compare-1 \
    --workers 8

# 只对比 Quality（快速，不需要多次运行）
python scripts/run_model_compare.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet \
    --dimensions quality \
    --output-dir workspace/model-compare-1

# 只对比 Speed（需要多次运行）
python scripts/run_model_compare.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet \
    --dimensions speed \
    --n-runs 10 \
    --output-dir workspace/model-compare-1

# 输出
workspace/model-compare-1/
├── compare_matrix.json       ← 机器可读（含 quality + speed）
├── model_comparison_report.md ← 人类可读
└── raw/
    ├── eval-1-haiku-run-1-transcript.txt
    ├── eval-1-haiku-run-2-transcript.txt
    ├── eval-1-sonnet-run-1-transcript.txt
    └── ...
```

---

## 与现有框架的关系

```
run_compare.py      → A vs B (with skill / without skill)
run_trigger.py      → Trigger rate test
run_model_compare.py → Model × Eval matrix  ← 新增
run_orchestrator.py → 调度以上三者（可扩展 model 维度）
```

**扩展 orchestrator（后续）**：
```bash
# 未来可以加 --models 参数到 orchestrator
python scripts/run_orchestrator.py \
    --evals evals/example-quality.json \
    --mode both \
    --models haiku,sonnet \    # 新参数
    --workers 8
```

---

## 实现清单

- [ ] `scripts/run_model_compare.py` — 主脚本
  - [ ] Quality 维度：复用 grader
  - [ ] Speed 维度：多次运行 + 统计 p50/p90
  - [ ] `--dimensions` 参数
  - [ ] `--n-runs` 参数（speed 用）
- [ ] 更新 `evals/example-quality.json` — 确认 assertions 字段完整
- [ ] 更新 `README.md` — 新增 Model Comparison 使用说明
- [ ] 更新 `CHANGELOG.md` — v0.5 记录
- [ ] 与 ARCHITECTURE.md 保持一致

---

## 时间估计

- **实现 run_model_compare.py**：2–3 小时
- **单次对比（3 模型 × 5 eval）**：~30 秒（并发）
- **输出 + 分析**：自动生成，无需手动处理

---

## 设计决策记录

| 决策 | 选项 | 原因 |
|------|------|------|
| Grader blind | ✅ 不告诉 grader 模型名 | 避免评分偏见 |
| 并发所有 (model, eval) | ✅ ThreadPoolExecutor | 与 Phase 3.1 一致，速度快 |
| 模型依赖度 Delta 阈值 | 2.0 | 经验值，可调 |
| Transcript 保留 | ✅ 保存原始输出 | 便于 debug，人工复核 |
