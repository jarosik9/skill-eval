---
name: openclaw-eval-skill
description: "OpenClaw Skill 评测框架。Use when: 需要评测任何 OpenClaw skill 的质量——测试 description 触发准确率（trigger rate）、对比 with/without skill 的输出质量（quality compare）、或用 LLM-as-judge 自动评分。适用于任何类型的 skill（CLI 工具、对话型、API 集成等）。不依赖 claude CLI，通过 sessions_spawn + sessions_history 运行。支持并发 evaluation（6-8 worker 并行，性能提升 5-10x）。触发词：评测 skill、benchmark、trigger rate、quality compare、A/B 对比、skill 效果怎么样。NOT for: 调试单次对话、不涉及 skill 评测的一般测试任务。"
---

# openclaw-eval-skill

任何 OpenClaw skill 都可以用这个框架评测。不依赖 claude CLI，所有 agent 执行通过 `sessions_spawn` + `sessions_history` 完成。

**适用范围**：CLI 工具型、对话型、API 集成型 skill 均可，assertions 按需选择类型。

---

## 快速开始（5 分钟）

```bash
# 1. 运行整个评测流程（并发）
python scripts/run_orchestrator.py \
    --evals evals/example-quality.json \
    --skill-path /path/to/SKILL.md \
    --mode both \
    --output-dir workspace/iteration-1 \
    --workers 6

# 输出：eval-workspace/workspace/iteration-1/
#   ├── compare_results_raw.json
#   ├── eval-{id}-{name}/
#   │   ├── with_skill_full_history.json
#   │   ├── without_skill_full_history.json
#   │   └── metadata.json
#   ├── trigger_rate_results.json
#   └── [ready for grading]
```

**时间**: 
- 5 evals × 2 variant（compare）+ 5 evals（trigger）= 15 tasks
- 顺序：75s → 并发（6 workers）：12s（**6x faster**）

---

## 三种测试模式

| Mode | 测什么 | 核心机制 |
|------|--------|----------|
| **Trigger Rate** | skill description 触发准确率 | spawn subagents + `sessions_history` tool_use 检测 |
| **Quality Compare** | with skill vs without skill 输出质量 | spawn 两组 subagents + grader subagent 评分 |
| **Aggregate** | 综合报告 | `scripts/aggregate_benchmark.py` |

---

## 核心原则

1. **不修改评测对象** — 只观察，不改动被测 skill 任何文件。给出分级建议，不直接修改
2. **eval 记录放 workspace** — 所有产出写入 `<workspace>/eval-workspace/<skill-name>/iteration-N/`，不污染 skill 本体
3. **evals.json 跨 iteration 共享** — 定义放 `eval-workspace/<skill-name>/evals.json`；每次跑时复制一份 `evals-snapshot.json` 到 iteration 目录作历史记录
4. **完整记录** — 保存 `full_history.json`（含所有 tool_use + tool_result），不只是最终文本

---

## agents/ 说明

| 文件 | 用途 | 使用时机 |
|------|------|---------|
| `grader.md` | 逐条检查 assertions，记录行为异常，给出分级建议 | **主流程**：每个 eval 必用 |
| `comparator.md` | 盲测对比，不看 assertions，纯判断哪个输出更好 | **辅助**：想要无偏对比时用，或 assertions 无法覆盖主观质量时 |
| `analyzer.md` | 跑完所有 eval 后，分析跨 eval 的模式和异常 | **事后分析**：所有 grading 完成后，生成整体洞察 |

通常顺序：grader（每个 eval）→ analyzer（所有 eval 完成后）。comparator 可选，用于补充 grader 无法捕捉的整体质量判断。

---

## 标准目录结构

```
eval-workspace/<skill-name>/
├── evals.json                          ← 测试用例定义（跨 iteration 共享）
└── iteration-1/
    ├── evals-snapshot.json             ← 本次使用的 evals.json 快照
    ├── eval-report.md                  ← 评测报告（assertions + 问题分级 + 修改建议）
    └── histories/
        ├── e1_with_full_history.json   ← with skill，完整 tool calls + 输出
        ├── e1_without_full_history.json
        └── ...
```

---

## Mode 1: Trigger Rate

**检测原理**：`sessions_history(includeTools=True)` 扫描 tool_use block，`name=Read`，`path` 包含 `SKILL.md` → triggered=True。这是 ground truth，不是意图推断。

**One-liner（推荐）**：
```bash
python scripts/run_orchestrator.py \
    --evals evals/example-triggers.json \
    --skill-path <skill-path>/SKILL.md \
    --mode trigger \
    --output-dir eval-workspace/<skill-name>/iteration-1 \
    --workers 6
```

**手工步骤（如需调试）**：

### Step 1: Orchestrator spawn subagents (并发)

对 `evals/example-triggers.json` 里每个 query：
```python
# cleanup="keep" 必须，history 要保留用于分析
session_key = sessions_spawn(
    task=query,
    sandbox="inherit",
    cleanup="keep",
    mode="run"
)
# 并发执行，ThreadPoolExecutor(max_workers=6)
# sessions_yield 等完成，记录 session_key
```

输出格式 `trigger_results_raw.json`：
```json
[{"id": "tq-1", "query": "...", "expected": true, "session_key": "agent:...:subagent:uuid"}]
```

### Step 2: 分析 history（并发）

```bash
python scripts/run_trigger.py \
    --raw trigger_results_raw.json \
    --output eval-workspace/<skill-name>/iteration-1/trigger_rate_results.json \
    --workers 6
```

性能：10 queries × 4-6 workers → 30s 而非 3 分钟（10x faster）

---

## Mode 2: Quality Compare

**One-liner（推荐）**：
```bash
python scripts/run_orchestrator.py \
    --evals evals/example-quality.json \
    --skill-path <skill-path>/SKILL.md \
    --mode compare \
    --output-dir eval-workspace/<skill-name>/iteration-1 \
    --workers 6
```

**手工步骤（如需调试）**：

### Step 1: Orchestrator spawn 两组 subagents（并发）

对每个 eval，并发生成 with_skill + without_skill 两个 variant：
```python
# with_skill：显式引导读取 SKILL.md
with_key = sessions_spawn(
    task=f"请先读 <skill_path>/SKILL.md，然后执行：\n\n{prompt}\n\n背景：{context}",
    sandbox="inherit", cleanup="keep", mode="run"
)

# without_skill：直接 prompt，无 skill 提示
without_key = sessions_spawn(
    task=prompt,
    sandbox="inherit", cleanup="keep", mode="run"
)
# 并发执行，ThreadPoolExecutor(max_workers=6)
```

### Step 2: 整理 transcripts（并发）

```bash
python scripts/run_compare.py \
    --evals eval-workspace/<skill-name>/evals.json \
    --results compare_results_raw.json \
    --output-dir eval-workspace/<skill-name>/iteration-1 \
    --workers 6
```

`compare_results_raw.json` 格式：
```json
[{"eval_id": 1, "eval_name": "onboarding",
  "with_skill_session": "agent:...", "without_skill_session": "agent:..."}]
```

脚本产出：
- `eval-{id}-{name}/with_skill_full_history.json` — 完整 history（含 tool calls）
- `eval-{id}-{name}/with_skill_transcript.txt` — 完整 transcript（含所有 tool calls，grader 用）
- `eval-{id}-{name}/metadata.json` — eval 定义 + assertions

性能：5 evals × 2 variant × 4-6 workers → 40s 而非 5 分钟（7x faster）

### Step 3: Grader subagent 评分

对每个 eval，spawn grader subagent，task 用 `agents/grader.md` 模板填入 assertions + 两段对话。收到结果后写入 `eval-{id}-{name}/grading.json`。

---

## Mode 3: Aggregate

```bash
python scripts/aggregate_benchmark.py \
    eval-workspace/<skill-name>/iteration-1 \
    --trigger trigger_rate_results.json \
    --output eval-workspace/<skill-name>/iteration-1/benchmark.json
```

---

## evals.json 格式

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "name": "onboarding-fresh",
      "prompt": "Help me set up the wallet",
      "context": "Clean machine, no prior setup. For grader context only, not injected to agent.",
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
        },
        {
          "id": "a1-3",
          "description": "[GAP] Dry-run before transfer",
          "type": "output_contains",
          "value": "dry-run",
          "note": "Best practice — failure = gap in skill design"
        }
      ]
    }
  ]
}
```

---

## Assertion 类型

适用于任何 skill 类型（CLI、API、对话）。

| 类型 | 判断方式 |
|------|---------|
| `output_contains` / `cli_log_contains` | 值出现在 conversation 或 tool 输出里 |
| `output_not_contains` / `cli_log_not_contains` | 值不出现 |
| `output_count_max` | 出现次数 ≤ max |
| `env_or_export_in_log` | 变量名出现在任何 export/setenv/env 命令里 |
| `tool_called` | 特定工具被调用至少一次 |
| `tool_not_called` | 特定工具未被调用 |
| `conversation_contains` | 值出现在 with_skill 对话任意位置 |
| `conversation_not_contains` | 值不出现 |
| `conversation_contains_any` | 至少一个值出现 |
| `conversation_not_contains_any` | 所有值都不出现 |

**Priority assertions**：任一 fail → overall=FAIL，无论分数。  
**Gap assertions**（`"note": "Best practice..."`）：fail = skill 设计缺口，不是 Claude 执行错误。

---

## 问题分级（grader 输出格式）

```
🔴 P0 Critical  — 核心功能完全失效
🟠 P1 High      — 明显影响使用体验
🟡 P2 Medium    — 有改进空间但可接受
🟢 P3 Low       — 细节优化
```

每条建议格式：`[P0] <文件>: <具体修改内容>`

Grader **只给建议，不直接修改**被测 skill。

---

## Agent 行为异常记录

除 assertions 外，grader 还需记录以下行为（比 pass/fail 更有诊断价值）：

| 字段 | 触发条件 |
|------|---------|
| `path_corrections` | 用了错误路径后自我修正 |
| `retry_count` | 同一命令执行多次 |
| `missing_file_reads` | 尝试读取不存在的文件 |
| `tool_arg_errors` | 工具调用参数错误 |
| `skipped_steps` | skill 明确要求的步骤未执行 |
| `hallucinations` | 编造了不存在的命令/参数/API |

---

## 关键约束

- **`sandbox="inherit"`** — subagent 需要继承 skill 注册环境
- **`cleanup="keep"`** — history 必须保留用于 trigger 检测
- **不依赖 claude CLI** — 所有 subagent 通过 sessions_spawn 运行
- skill 注册：放入 `skills.load.extraDirs` 下的实体目录（symlink 被安全检查拒绝）
