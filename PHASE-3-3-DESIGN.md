# Phase 3.3：True Session Context（设计与实现）

**状态**：设计 + 核心工具实现完成（2026-03-18）

**决策**：使用 **真实提取方案（方案 2）**，不合成

---

## 核心方案：True History Extraction

### 工作流

```
Run 1 (Iteration 1)
├─ run_orchestrator.py with evals/example-quality.json
├─ Output: session keys (eval-1-with: uuid-A, eval-1-without: uuid-B, ...)
└─ Record session keys

Extract Histories (from Run 1 results)
├─ extract_session_history.py --session-key uuid-A --eval-id 1 → eval-1.json
├─ extract_session_history.py --session-key uuid-B --eval-id 2 → eval-2.json
└─ Output: evals/histories/eval-{id}.json files

Build Combined Evals
├─ build_evals_with_context.py
│   --base-evals evals/example-quality.json
│   --histories evals/histories
│   --output evals/with-context.json
└─ Output: evals.json with conversation_history populated

Run 2 (Iteration 2 - with context)
├─ run_orchestrator.py with evals/with-context.json
├─ Compares: fresh vs with-context outputs
└─ Measures: does history affect quality/recall?
```

---

## 实现工具

### 工具 1：extract_session_history.py

**用途**：从完成的 session 中提取对话历史

```bash
python scripts/extract_session_history.py \
    --session-key "agent:mo9:subagent:abc123def456" \
    --eval-id 1 \
    --eval-name "onboarding-setup" \
    --output-file evals/histories/eval-1.json
```

**输出格式**：
```json
{
  "eval_id": 1,
  "eval_name": "onboarding-setup",
  "source_session_key": "agent:mo9:subagent:abc123def456",
  "conversation_history": [
    {"role": "user", "content": "Help me set up the wallet"},
    {"role": "assistant", "content": "Let me read SKILL.md first..."},
    {"role": "user", "content": "What's the next step?"}
  ],
  "metadata": {
    "num_turns": 3,
    "user_turns": 2,
    "assistant_turns": 1
  }
}
```

**核心逻辑**：
- 调用 `sessions_history(sessionKey, includeTools=False)`
- 只提取 role="user"|"assistant" 的消息
- 跳过 tool_use/tool_result blocks
- 处理 content 为字符串或数组的两种情况

---

### 工具 2：build_evals_with_context.py

**用途**：将提取的历史合并到 evals.json

```bash
python scripts/build_evals_with_context.py \
    --base-evals evals/example-quality.json \
    --histories evals/histories \
    --output evals/with-context.json \
    --summary
```

**输入**：
- Base evals.json（原始测试用例）
- Extracted histories 目录（eval-{id}.json 文件）

**输出**：
```json
{
  "skill_name": "openclaw-eval-skill",
  "evals": [
    {
      "id": 1,
      "name": "onboarding-setup",
      "prompt": "Help me set up the wallet",
      "conversation_history": null,
      "variant": "fresh"
    },
    {
      "id": 11,
      "name": "onboarding-setup-with-context",
      "prompt": "Help me set up the wallet",
      "conversation_history": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
      ],
      "variant": "with-context"
    }
  ]
}
```

**ID 命名规则**：
- Fresh variant：保留原 ID（如 1）
- With-context variant：原 ID × 10 + 1（如 11）
- 便于追踪和对比

---

## 完整流程示例

### Step 1: 初始评测

```bash
cd ~/.openclaw/workspace/operations/skills/openclaw-eval-skill

# 运行初始评测，获得 session keys
python scripts/run_orchestrator.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --mode both \
    --output-dir workspace/iter-1 \
    --workers 6

# 输出：session keys in run logs
# [标记下来：eval-1-with: agent:mo9:subagent:xxx1, eval-1-without: agent:mo9:subagent:xxx2, ...]
```

### Step 2: 提取历史

```bash
# 创建历史目录
mkdir -p evals/histories

# 从 eval-1-without 的 session 提取历史
# （选择"without skill"的 session，因为它是更自然的对话）
python scripts/extract_session_history.py \
    --session-key "agent:mo9:subagent:xxx2" \
    --eval-id 1 \
    --eval-name "quality-fresh" \
    --output-file evals/histories/eval-1.json \
    --print

# 对所有 eval 重复（脚本可以批量化）
python scripts/extract_session_history.py \
    --session-key "agent:mo9:subagent:xxx4" \
    --eval-id 2 \
    --eval-name "quality-compare" \
    --output-file evals/histories/eval-2.json

# ... 更多 eval
```

### Step 3: 合并历史

```bash
# 构建包含历史的 evals
python scripts/build_evals_with_context.py \
    --base-evals evals/example-quality.json \
    --histories evals/histories \
    --output evals/with-context.json \
    --summary

# 输出：
# ✅ Loaded history for eval-1 (3 messages)
# ✅ Created with-context variant for eval-1
# 
# === Summary ===
# Total evals: 4
#   Fresh (no history): 2
#   With context: 2
```

### Step 4: 对比评测

```bash
# 用新的 evals 运行评测
python scripts/run_orchestrator.py \
    --evals evals/with-context.json \
    --skill-path ./SKILL.md \
    --mode both \
    --output-dir workspace/iter-2-context \
    --workers 6

# 输出：
# [两组结果] fresh vs with-context
```

### Step 5: 分析对比

```
workspace/iter-2-context/
├── eval-1-quality-fresh/       (eval-1, no history)
│   ├── with_skill_transcript.txt
│   └── without_skill_transcript.txt
├── eval-11-quality-with-context/ (eval-1 with history)
│   ├── with_skill_transcript.txt
│   └── without_skill_transcript.txt
├── trigger_rate_results.json
└── [待 grader 评分]
```

**关键对比**：
- eval-1 vs eval-11：同一 task，区别在于有无历史
- 衡量：是否历史改善了触发率/质量？
- 量化：(eval-11 trigger_rate) - (eval-1 trigger_rate)

---

## 设计细节

### 3.1 Conversation History 提取规则

**保留**：
- ✅ role="user" 的所有消息
- ✅ role="assistant" 的所有消息
- ✅ content 为字符串的消息
- ✅ content 为数组时，提取所有 type="text" 的块

**过滤**：
- ❌ role 其他值（如"system", "tool"）
- ❌ tool_use / tool_result blocks
- ❌ 空消息（content=""）

**原因**：
- Tool calls 对真实对话体验没意义
- 历史应该是"自然语言对话"的形态
- 更接近真实的"记忆"（human 的记忆也不包括 API calls）

### 3.2 ID 命名规则

```
Fresh eval:        ID = 1, 2, 3, ...
With-context eval: ID = 11, 21, 31, ...  (原 ID × 10 + 1)

优势：
- 易于追踪对应关系
- 便于分组对比
- 避免 ID 碰撞
```

### 3.3 Context Injection 方式

在 `run_compare.py` 中：

```python
# When conversation_history is present
if eval_item.get("conversation_history"):
    history_text = "=== PREVIOUS CONVERSATION ===\n"
    for turn in eval_item["conversation_history"]:
        role = turn["role"].upper()
        content = turn["content"]
        history_text += f"{role}: {content}\n\n"
    history_text += "=== END PREVIOUS CONVERSATION ===\n\n"
    
    task = history_text + "Now, " + prompt
else:
    task = prompt
```

**时机**：在 `sessions_spawn` 的 task 字段中，作为 prompt 前缀

---

## 质量检查

### 提取的历史应该满足

- ✅ 至少 2-3 个 turn（对话片段）
- ✅ user 和 assistant 交替出现
- ✅ 内容有意义（不是截断或错误的）
- ✅ 长度合理（每条消息 50-500 字）

### 脚本会输出

```
✅ Extracted 3 messages
   User turns: 2
   Assistant turns: 1
✅ Saved to evals/histories/eval-1.json
```

用户应该快速扫一下日志，确保没有异常。

---

## 使用场景

### 场景 1：测试"记忆连续性"

**问题**：Skill description 是否依赖对话历史？

```
Fresh query:        "Help me evaluate skill quality"
With context query: "I read about your evaluation framework. 
                     Now help me evaluate my custom skill."

对比：
- 无历史：agent 理解通用的 eval framework
- 有历史：agent 理解"我已经知道框架了，现在要用它"
```

### 场景 2：测试"上下文利用"

**问题**：Agent 是否真的使用了历史信息？

```
输出对比：
- eval-1 (fresh): "You can use run_orchestrator.py..."
- eval-11 (context): "Based on your setup, use run_orchestrator.py with these flags..."
```

改进幅度 > 10% ⟹ 历史确实有帮助

### 场景 3：调试"上下文污染"

**问题**：历史是否引入了错误的假设？

```
如果 eval-11 表现比 eval-1 差 ⟹ 历史可能误导了 agent
需要检查：历史内容是否有错误？是否过时？
```

---

## 局限与已知问题

### ⚠️ 已知限制

1. **不支持真正的 session 恢复**
   - 当前方案：用文本 prefix 模拟历史
   - 不是真正的 session 继续（agent 不知道自己在"继续"）
   - 但足以测试"是否历史有帮助"

2. **Context window 膨胀**
   - 完整历史可能 100-500 tokens
   - 解决：后续可加 summarization（Phase 3.3b）

3. **提取的历史可能包含 bias**
   - 历史来自"之前运行的 eval"
   - 不是自然的用户对话
   - 但可接受，因为目的是测试"能否利用历史"，不是"历史有多现实"

### 🔮 Future Improvements

- **Phase 3.3b**：自动摘要化历史（减少 token）
- **Phase 3.3c**：LLM-as-judge 评分"上下文利用度"
- **Phase 3.3d**：真实 session 恢复（如果 OpenClaw 支持 --resume）

---

## 实现清单

- [x] `extract_session_history.py` — 从 session 提取历史
- [x] `build_evals_with_context.py` — 合并历史到 evals.json
- [ ] 更新 `run_compare.py` — 支持 conversation_history 注入
- [ ] 更新 `run_orchestrator.py` — 优化 history 模式（可选）
- [ ] 文档：完整使用指南（README 新增 Phase 3.3 section）

---

## 时间估计

- **提取 + 合并**：2 min/eval（手工）
- **自动化脚本**：1 min（全部并发）
- **完整 Run 2 评测**：10-15 min（6 workers）

**总时间**：~30 min from Run 1 to comparison results

---

## 参考

- 之前的设计讨论：PHASE-3-2-DESIGN.md（诊断工具）
- OpenClaw 架构：sessions_history API + sessions_spawn
- 类似实践：Claude Code 的 session resume 机制
