# Phase 3.5：Latency Profiling（设计文档）

**状态**：设计完成，待实现（2026-03-18）

**目标**：找出 skill 执行的速度瓶颈——哪个步骤最慢，p50/p90 是多少

---

## 核心问题

- 这个 skill 从触发到完成任务要多久？
- 哪个步骤是瓶颈（read external file？API call？多步推理？）
- 跑 5 次，结果稳定吗（方差大不大）？
- haiku 比 sonnet 快多少？（结合 3.4）

---

## 两种 Latency 维度

### 维度 1：Total Latency（总时长）

```
eval 开始 → subagent 完成 = 总时长
```

现在 timing.json 已经有这个，但只有单次值，没有统计分布。

### 维度 2：Step-Level Latency（步骤级）

```
SKILL.md 里的每个步骤：
  Step 1: Read SKILL.md          → 2s
  Step 2: Parse config           → 0.5s
  Step 3: Fetch external URL     → 8s  ← 瓶颈
  Step 4: Execute command        → 3s
  Step 5: Format output          → 1s
  Total: 14.5s
```

**实现方式**：在 transcript 里找时间戳，推断每步耗时。

---

## 实现方案

### 方案 A：多次重复运行，统计分布（简单）

```python
# 同一个 eval 跑 N 次，收集总时长
def profile_latency(eval_item, skill_path, n_runs=5, model="sonnet"):
    timings = []
    for i in range(n_runs):
        start = time.time()
        result = spawn_eval(eval_item, skill_path, model)
        elapsed = time.time() - start
        timings.append(elapsed)
    
    return {
        "eval_id": eval_item["id"],
        "model": model,
        "n_runs": n_runs,
        "timings_seconds": timings,
        "p50": sorted(timings)[n_runs // 2],
        "p90": sorted(timings)[int(n_runs * 0.9)],
        "mean": sum(timings) / n_runs,
        "min": min(timings),
        "max": max(timings),
        "std_dev": statistics.stdev(timings)
    }
```

**优点**：简单，不需要修改 subagent 逻辑  
**缺点**：只有总时长，看不到步骤级细节

### 方案 B：Transcript 时间戳解析（中等复杂）

```python
# 分析 transcript，找每个 tool call 的时间戳
def parse_step_timings(transcript: str) -> list:
    """
    从 transcript 提取步骤级时间：
    
    transcript 格式大概是：
    [21:00:01] User: Help me set up wallet
    [21:00:02] [Tool: read SKILL.md] → 0.8s
    [21:00:10] [Tool: exec caw init] → 8.2s  ← 瓶颈
    [21:00:11] [Tool: read output] → 0.5s
    [21:00:12] Assistant: Done.
    """
    steps = []
    lines = transcript.split('\n')
    
    prev_time = None
    for line in lines:
        # 提取时间戳（如果 transcript 有）
        ts = extract_timestamp(line)
        tool = extract_tool_name(line)
        
        if ts and prev_time and tool:
            elapsed = ts - prev_time
            steps.append({
                "step": tool,
                "duration_seconds": elapsed.total_seconds()
            })
        
        if ts:
            prev_time = ts
    
    return steps
```

**优点**：可以看到步骤级瓶颈  
**缺点**：transcript 格式不固定，解析可能不稳定

### 方案 C：Structured Timing Markers（最准确，需改 subagent prompt）

```python
# 在 task prompt 里要求 subagent 输出时间标记
task = f"""
{skill_instructions}

IMPORTANT: After each major step, output a timing marker:
[STEP_START: step_name]
... do the step ...
[STEP_END: step_name]

This is for performance profiling only.
"""
```

**优点**：精确，结构化  
**缺点**：改变了 subagent 的行为，可能影响正常评测

---

## 推荐方案：A + B 混合

- **默认**：方案 A（5次重复，总时长分布）——简单可靠
- **深度分析**：方案 B（解析 transcript，步骤级）——可选，加 `--step-level` flag

```bash
# 基础：5 次重复，总时长分布
python scripts/run_latency_profile.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --n-runs 5 \
    --output-dir workspace/latency-1

# 深度：步骤级分析
python scripts/run_latency_profile.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --n-runs 5 \
    --step-level \
    --output-dir workspace/latency-1
```

---

## 输出格式

### latency_report.json

```json
{
  "skill_name": "openclaw-eval-skill",
  "model": "sonnet",
  "n_runs": 5,
  "timestamp": "2026-03-18T21:00:00+08:00",
  "evals": [
    {
      "eval_id": 1,
      "eval_name": "onboarding",
      "total_latency": {
        "timings_seconds": [12.1, 13.5, 11.8, 14.2, 12.9],
        "p50": 12.9,
        "p90": 14.2,
        "mean": 12.9,
        "min": 11.8,
        "max": 14.2,
        "std_dev": 0.89,
        "stable": true
      },
      "step_latency": [
        {"step": "read_skill_md",     "mean_seconds": 1.2, "pct_of_total": "9%"},
        {"step": "exec_caw_init",     "mean_seconds": 8.4, "pct_of_total": "65%", "bottleneck": true},
        {"step": "parse_output",      "mean_seconds": 0.8, "pct_of_total": "6%"},
        {"step": "format_response",   "mean_seconds": 2.5, "pct_of_total": "19%"}
      ]
    }
  ],
  "summary": {
    "overall_p50": 12.9,
    "overall_p90": 14.2,
    "bottleneck_step": "exec_caw_init (65% of total)",
    "stability": "HIGH (std_dev < 1s across all evals)"
  }
}
```

### latency_report.md（人类可读）

```markdown
# Latency Profile: openclaw-eval-skill

Model: sonnet | Runs: 5 | Date: 2026-03-18

## Summary

| Eval | p50 | p90 | Stable? |
|------|-----|-----|---------|
| onboarding | 12.9s | 14.2s | ✅ |
| transfer   | 18.4s | 32.1s | ⚠️ |

## Bottleneck Analysis

### eval-2: transfer — HIGH VARIANCE ⚠️

p50: 18.4s, p90: 32.1s, std_dev: 5.2s

Step breakdown:
  exec_caw_transfer: 12–25s (variable, likely network)

Recommendation: Add timeout + retry logic in SKILL.md step 4.

## Comparison: haiku vs sonnet

| Eval       | haiku p50 | sonnet p50 | Speed gain |
|------------|-----------|------------|------------|
| onboarding | 9.2s      | 12.9s      | haiku 28% faster |
| transfer   | 15.1s     | 18.4s      | haiku 18% faster |
```

---

## 稳定性判断

| 指标 | 阈值 | 判断 |
|------|------|------|
| std_dev < 1s | 低方差 | 🟢 STABLE |
| std_dev 1–3s | 中方差 | 🟡 MODERATE |
| std_dev > 3s | 高方差 | 🔴 UNSTABLE（需要 retry 逻辑或更多 runs）|

高方差 = skill 有不确定性（网络、工具调用、随机性）

---

## 与 Phase 3.4 的联动

```python
# run_latency_profile.py 支持多模型
python scripts/run_latency_profile.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --models haiku,sonnet \
    --n-runs 5

# 输出额外的 model_latency_comparison 部分
# → 直接回答"haiku 快多少？"
```

---

## 实现清单

- [ ] `scripts/run_latency_profile.py` — 主脚本
  - [ ] 方案 A：多次重复 + 统计分布
  - [ ] 方案 B：transcript 时间戳解析（`--step-level` flag）
  - [ ] 多模型支持（`--models`）
- [ ] 更新 `README.md` — 新增 Latency Profiling 使用说明
- [ ] 更新 `CHANGELOG.md` — v0.6 记录

---

## 时间估计

- **实现 run_latency_profile.py（方案 A）**：2–3 小时
- **方案 B（步骤级）**：额外 2 小时
- **单次 profiling（5 runs × 3 evals）**：~5 分钟（并发）

---

## 注意事项

- n_runs 默认 5，最少 3（统计意义）
- 方案 A 并发跑 5 次会比串行快，但结果可能有 interference
  - 建议：并发跑，但在 summary 里注明"并发环境下的测量"
- transcript 时间戳依赖 OpenClaw 的输出格式，可能需要适配
