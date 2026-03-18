# openclaw-eval-skill — 技术 SPEC

> ⚠️ **历史文档**：本文件是初始设计规格，部分内容（grading.json 字段、模式分类名称）已与实际实现不一致。以 **SKILL.md** 为准。本文件保留作设计背景参考。

## 概述

通用 skill 评测框架，支持三种测试模式：

| Mode | 测什么 | 核心问题 |
|------|--------|----------|
| **Execution Quality** | skill 执行后输出好不好 | A skill 和 B skill 哪个输出更好？ |
| **Context Sensitivity** | 对话历史影响 | 有 DeFi 上下文 vs 无上下文，输出有什么差异？ |
| **Trigger Rate** | description 触发准确率 | 用户说 X，skill 会被正确调用吗？ |

---

---

## Mode 1: Execution Quality（执行质量对比）

对比两个 skill（或同一 skill 的两个版本）在相同任务上的执行效果。

**输入**：
- evals.json 定义的测试场景
- variant_a: skill 路径 A
- variant_b: skill 路径 B

**输出**：
- 每个 variant 的 grading.json（逐项评分）
- comparisons: winner + judge_reasoning

---

## Mode 2: Context Sensitivity（上下文敏感性）

测试对话历史对 skill 输出的影响。

**输入**：
- 同一个 prompt
- variant_a: 带 conversation_history
- variant_b: 无 conversation_history（或不同 history）

**输出**：
- 对比两个输出的差异
- 判断 skill 是否正确利用了上下文

---

## Mode 3: Trigger Rate（触发率测试）

测试 skill description 的触发准确率。

**输入**：
```json
{
  "triggers": [
    { "query": "我想给我的 agent 配一个钱包", "should_trigger": true },
    { "query": "帮我查一下比特币价格", "should_trigger": false },
    { "query": "设置 agent 的支付限额", "should_trigger": true },
    { "query": "写一首关于钱包的诗", "should_trigger": false }
  ]
}
```

**输出**：
```json
{
  "skill_name": "cobo-agent-wallet",
  "description": "Cobo Agent Wallet CLI...",
  "results": [
    { "query": "我想给我的 agent 配一个钱包", "should_trigger": true, "did_trigger": true, "pass": true },
    { "query": "帮我查一下比特币价格", "should_trigger": false, "did_trigger": false, "pass": true }
  ],
  "summary": { "total": 4, "passed": 4, "failed": 0, "trigger_rate": 1.0 }
}
```

**用途**：
- A/B 测试不同 description 版本
- 发现 false positive（不该触发但触发了）
- 发现 false negative（该触发但没触发）

**执行方式**：
- 复用 Claude Code 的 `run_eval.py`，它就是干这个的
- 动态创建临时 skill 文件 → 运行 `claude -p` → 检测是否调用了 `Read` 或 `Skill` tool

---

## 1. evals.json Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["name", "evals"],
  "properties": {
    "name": {
      "type": "string",
      "description": "评测集名称"
    },
    "version": {
      "type": "string",
      "description": "评测集版本"
    },
    "evals": {
      "type": "array",
      "items": { "$ref": "#/$defs/eval" }
    },
    "comparisons": {
      "type": "array",
      "items": { "$ref": "#/$defs/comparison" },
      "description": "可选，定义哪些 eval 需要对比"
    }
  },
  "$defs": {
    "eval": {
      "type": "object",
      "required": ["id", "name", "prompt"],
      "properties": {
        "id": { "type": "integer" },
        "name": { "type": "string", "description": "描述性名称，用于目录命名" },
        "skill_path": { "type": "string", "description": "skill 路径，可选" },
        "conversation_history": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "role": { "enum": ["user", "assistant", "system"] },
              "content": { "type": "string" }
            }
          },
          "description": "对话历史，注入到 prompt 前"
        },
        "prompt": { "type": "string", "description": "实际执行的任务 prompt" },
        "expected_behavior": { "type": "string", "description": "期望行为描述，给 judge 看" },
        "assertions": {
          "type": "array",
          "items": { "$ref": "#/$defs/assertion" }
        },
        "files": {
          "type": "array",
          "items": { "type": "string" },
          "description": "需要提供给 agent 的文件路径"
        },
        "timeout_seconds": { "type": "integer", "default": 120 }
      }
    },
    "assertion": {
      "type": "object",
      "required": ["id", "description", "type"],
      "properties": {
        "id": { "type": "string" },
        "description": { "type": "string" },
        "type": {
          "enum": [
            "conversation_contains",
            "conversation_not_contains",
            "conversation_contains_any",
            "conversation_not_contains_any",
            "conversation_matches_regex",
            "cli_log_contains",
            "cli_log_not_contains",
            "cli_exit_code",
            "file_exists",
            "file_contains",
            "custom"
          ]
        },
        "value": { "type": "string" },
        "values": { "type": "array", "items": { "type": "string" } },
        "file": { "type": "string" },
        "script": { "type": "string", "description": "custom 类型用，Python 脚本路径" }
      }
    },
    "comparison": {
      "type": "object",
      "required": ["name", "variant_a", "variant_b"],
      "properties": {
        "name": { "type": "string" },
        "variant_a": {
          "type": "object",
          "properties": {
            "eval_id": { "type": "integer" },
            "skill_path": { "type": "string" },
            "conversation_history": { "type": "array" }
          },
          "description": "可以引用 eval_id，也可以直接指定 skill_path / conversation_history 覆盖"
        },
        "variant_b": { "type": "object" },
        "judge_criteria": { "type": "string", "description": "给 LLM judge 的评判标准" }
      }
    }
  }
}
```

---

## 2. grading.json Schema

```json
{
  "eval_id": 1,
  "eval_name": "onboarding-defi-context",
  "variant": "a",
  "graded_at": "2026-03-17T22:00:00Z",
  "grader_model": "anthropic/claude-sonnet-4-6",
  "assertions": [
    {
      "id": "a1",
      "text": "Agent 提到 DeFi 相关配置",
      "passed": true,
      "evidence": "在输出第 3 行提到 'Aave borrow' 配置"
    }
  ],
  "dimensions": {
    "path_selection": { "score": 3, "max": 3, "note": "正确选择 autonomous 路径" },
    "step_completeness": { "score": 2, "max": 3, "note": "缺少 self-test 步骤" },
    "error_handling": { "score": 3, "max": 3, "note": "无错误场景" },
    "output_quality": { "score": 3, "max": 3, "note": "输出清晰可读" }
  },
  "total_score": 11,
  "max_score": 12,
  "pass": true
}
```

---

## 3. timing.json Schema

```json
{
  "total_tokens": 7423,
  "input_tokens": 3,
  "output_tokens": 7420,
  "cache_tokens": 41000,
  "duration_ms": 169000,
  "duration_seconds": 169
}
```

---

## 4. benchmark.json Schema

```json
{
  "name": "cobo-agent-wallet-v0.1.21",
  "generated_at": "2026-03-17T22:30:00Z",
  "iteration": 1,
  "summary": {
    "total_evals": 5,
    "total_comparisons": 2,
    "pass_rate": 0.8,
    "avg_score": 10.5,
    "max_score": 12
  },
  "variants": {
    "a": {
      "name": "new-skill",
      "pass_rate": 0.9,
      "avg_tokens": 7500,
      "avg_duration_seconds": 45
    },
    "b": {
      "name": "old-skill",
      "pass_rate": 0.7,
      "avg_tokens": 6800,
      "avg_duration_seconds": 40
    }
  },
  "comparisons": [
    {
      "name": "context-sensitivity",
      "winner": "a",
      "judge_reasoning": "Variant A 根据 DeFi 上下文调整了引导，Variant B 使用通用模板"
    }
  ],
  "evals": [
    {
      "id": 1,
      "name": "onboarding-defi-context",
      "variant_a_score": 11,
      "variant_b_score": 9,
      "variant_a_pass": true,
      "variant_b_pass": true
    }
  ]
}
```

---

## 5. 对话历史注入格式

```
[CONVERSATION HISTORY]
User: 我想用 agent 做 DeFi 交易
Assistant: 好的，DeFi 交易需要配置专门的策略...
[END CONVERSATION HISTORY]

Continue the conversation. Execute the following task:

帮我设置 wallet
```

---

## 6. LLM Judge Prompt 模板

```markdown
You are evaluating an AI agent's response to a task.

## Task
{prompt}

## Expected Behavior
{expected_behavior}

## Conversation History (if any)
{conversation_history}

## Agent Output
{agent_output}

## CLI Logs
{cli_logs}

## Assertions to Check
{assertions_json}

---

For each assertion, determine if it passed or failed. Provide evidence.

Then score the response on these dimensions (1-3 each):
1. **Path Selection**: Did the agent choose the correct workflow path?
2. **Step Completeness**: Did the agent complete all necessary steps?
3. **Error Handling**: Did the agent handle errors appropriately?
4. **Output Quality**: Is the output clear, correct, and useful?

Output your evaluation as JSON matching the grading.json schema.
```

---

## 7. 执行流程

### run_eval.py

```
1. 读取 evals.json 中的指定 eval
2. 构造 prompt（注入 conversation_history）
3. 执行 agent（claude CLI 或 sessions_spawn）
4. 收集输出（conversation.txt, cli_logs.txt, outputs/）
5. 保存 timing.json
```

### run_compare.py

```
1. 读取 comparison 定义
2. 并发执行 variant_a 和 variant_b（两个 subagent 同时 spawn）
3. 等待完成
4. 调用 grade.py 评分
5. 输出对比结果
```

### grade.py

```
1. 读取 eval_metadata.json
2. 读取 conversation.txt 和 cli_logs.txt
3. 构造 judge prompt
4. 调用 LLM（sonnet 或指定模型）
5. 解析结果，写入 grading.json
```

### aggregate.py

```
1. 遍历 iteration-N/ 下所有 eval 目录
2. 读取每个 grading.json
3. 计算汇总统计
4. 输出 benchmark.json + benchmark.md
```

---

## 8. CLI 用法（目标）

```bash
# Mode 1: 执行质量对比
python scripts/run_compare.py \
  --evals evals/cobo.json \
  --variant-a skills/cobo-v1 \
  --variant-b skills/cobo-v2 \
  --workspace ./workspace

# Mode 2: 上下文敏感性测试
python scripts/run_compare.py \
  --evals evals/cobo.json \
  --mode context \
  --workspace ./workspace

# Mode 3: 触发率测试
python scripts/run_trigger.py \
  --triggers evals/cobo-triggers.json \
  --skill-path skills/cobo-agent-wallet \
  --runs-per-query 3 \
  --output trigger-results.json

# 触发率 A/B 测试（对比两个 description）
python scripts/run_trigger.py \
  --triggers evals/cobo-triggers.json \
  --skill-path skills/cobo-agent-wallet \
  --description-a "Cobo Agent Wallet for autonomous agent payment..." \
  --description-b "Setup and manage wallets for AI agents..." \
  --output trigger-ab-results.json

# 评分
python scripts/grade.py --workspace ./workspace/iteration-1/eval-1-onboarding

# 汇总
python scripts/aggregate.py --workspace ./workspace/iteration-1 --output benchmark.json

# 生成报告
python viewer/generate_review.py ./workspace/iteration-1 --benchmark benchmark.json
```

---

## 9. 与现有工具的兼容性

| 工具 | 复用 | 说明 |
|------|------|------|
| Claude Code eval-viewer | ✅ | 直接复用 `generate_review.py` |
| OpenClaw sessions_spawn | ✅ | 作为 fallback 执行引擎 |
| claude CLI | ✅ | 主要执行引擎 |
| Cobo evals.json | ✅ | schema 兼容 |

---

## 10. 文件结构

```
openclaw-eval-skill/
├── SKILL.md                    # 入口，触发和使用说明
├── PLAN.md                     # 设计 plan（本文件）
├── SPEC.md                     # 技术 spec（本文件）
├── evals/
│   └── example.json            # 示例 evals.json
├── scripts/
│   ├── run_eval.py             # 执行单个场景
│   ├── run_compare.py          # A vs B 对比
│   ├── grade.py                # LLM-as-judge
│   └── aggregate.py            # 汇总结果
├── references/
│   ├── schemas.md              # JSON 结构参考
│   └── judge-prompt.md         # 评分 prompt 模板
└── viewer/
    └── generate_review.py      # 生成 HTML 报告（从 Claude Code 复用）
```
