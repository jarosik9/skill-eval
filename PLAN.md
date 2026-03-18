# openclaw-eval-skill — 设计 PLAN

**状态**：v0.2 完成（2026-03-17）

## 背景

合并 OpenClaw 官方 skill-creator（结构规范）和 Claude Code skill-creator（eval 循环）的能力，创建一个专注于 **skill 评测与对比** 的工具。

核心场景：Agent Wallet skill 开发迭代——测试不同 skill 写法、不同对话上下文对 agent 行为的影响。

---

## 核心需求

### 1. A vs B 对比（不是 skill vs no-skill）

- Skill A（旧版）vs Skill B（新版）
- 两个完全不同的 skill（比较哪个更适合某个场景）
- 同一个 skill，不同的对话历史

### 2. 对话历史作为输入变量

- 带上下文（有 conversation_history）vs 不带上下文
- 测试 agent 是否根据历史调整响应
- 测试 skill 是否足够泛化

### 3. 通用评测框架

- 不绑定特定 skill
- JSON 定义评测场景
- 可复用的评分标准

---

## 三种对比模式

| 模式 | 变量 | 不变 |
|------|------|------|
| **skill 对比** | skill_path | conversation_history + prompt |
| **记忆对比** | conversation_history | skill_path + prompt |
| **混合对比** | 都可以变 | prompt 相同 |

---

## 评测方式

### LLM-as-Judge（主要）

- 自动打分，按 rubric 评估
- 保留原始输出供人工复核
- 支持多维度评分（Path Selection / Step Completeness / Error Handling / Output Quality）

### 人工复核（辅助）

- eval-viewer 生成 HTML 报告
- 并排展示 A vs B 输出
- 可下载 feedback.json

---

## 技术实现

### 执行引擎

**选项 A**：OpenClaw `sessions_spawn`（subagent）
- 优点：和当前环境一致，可控制 skill 加载
- 缺点：无法精确控制 `--plugin-dir`，skill 通过 task 内容传递

**选项 B**：Claude Code CLI `claude -p`
- 优点：`--plugin-dir` 精确控制 skill 加载，`--disable-slash-commands` 做 baseline
- 缺点：需要 claude CLI 可用

**决策**：优先 Claude Code CLI，fallback 到 sessions_spawn

### 对话历史注入

将 conversation_history 构造为 prompt 前缀：

```
[Context: Previous conversation]
User: ...
Assistant: ...
[End context]

Now, continue with the following task:
<actual prompt>
```

或者用 Claude Code 的 `--resume` 从保存的 session 恢复（更真实但更复杂）。

**决策**：v1 用 prompt 前缀方式，简单可控。v2 考虑真实 session 恢复。

---

## 输出结构

```
workspace/
├── iteration-{N}/
│   ├── eval-{id}-{name}/
│   │   ├── variant-a/
│   │   │   ├── outputs/          # agent 产出的文件
│   │   │   ├── conversation.txt  # 完整对话记录
│   │   │   ├── cli_logs.txt      # CLI 执行日志
│   │   │   └── timing.json       # tokens + duration
│   │   ├── variant-b/
│   │   │   └── ...
│   │   ├── eval_metadata.json    # prompt + assertions
│   │   └── grading.json          # LLM judge 结果
│   ├── benchmark.json            # 汇总统计
│   └── benchmark.md              # 可读版本
└── feedback.json                 # 人工反馈（如有）
```

---

## 开发计划

### Phase 1：核心功能（v0.1）✅ 完成

- [x] SKILL.md 入口
- [x] evals.json schema 定义（SPEC.md）
- [x] run_compare.py — A vs B 对比 + context 模式
- [x] run_trigger.py — 触发率测试（Mode 3）
- [x] grade.py — LLM-as-judge
- [x] aggregate_benchmark.py — 汇总结果（复用 Claude Code）

### Phase 2：可视化（v0.2）✅ 完成

- [x] generate_review.py — HTML 报告（复用 Claude Code）
- [x] viewer.html — 并排对比视图（复用 Claude Code）
- [x] feedback 收集（eval-viewer 内置）

### Phase 3：高级功能（v0.3）⏳ 待开发 — 当前 SKILL.md 不包含此功能

- [ ] description 优化循环（从 Claude Code 移植 run_loop.py）
- [ ] 批量运行 + 统计分析
- [ ] 真实 session 恢复（替代 prompt 前缀）

---

## 风险分析

| 风险 | 等级 | 缓解 |
|------|------|------|
| claude CLI 不可用 | 🟡 中 | fallback 到 sessions_spawn |
| 对话历史注入不真实 | 🟡 中 | v1 接受，v2 用真实 session |
| LLM judge 不稳定 | 🟡 中 | 多次运行取平均，保留原始输出 |
| eval-viewer 依赖浏览器 | 🟢 低 | 支持 `--static` 生成静态 HTML |

---

## 成功标准

1. 能在 5 分钟内跑完一个 A vs B 对比
2. LLM judge 评分和人工判断一致率 > 80%
3. 输出格式清晰，人工复核无障碍
4. 可复用于任何 skill，不限于 Agent Wallet
