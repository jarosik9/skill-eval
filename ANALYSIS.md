# openclaw-eval-skill — 源码分析与复用清单

从两个来源提取可复用组件：
- **OpenClaw 官方 skill-creator**：`/opt/homebrew/lib/node_modules/openclaw/skills/skill-creator/`
- **Claude Code skill-creator**：`<openclaw-workspace>/skills/skill-creator/`

---

## 一、两个 skill 的核心流程对比

### OpenClaw 官方 skill-creator

```
1. 理解 skill 需求（用户访谈）
2. 规划 skill 结构（scripts/references/assets）
3. init_skill.py — 初始化目录结构
4. 编写 SKILL.md + 资源文件
5. package_skill.py — 打包成 .skill 文件
6. 迭代（基于真实使用）
```

**核心脚本**：
- `init_skill.py` — 创建 skill 目录模板
- `package_skill.py` — 打包 + 校验
- `quick_validate.py` — 格式验证

**与我们目标无关**：初始化和打包，我们做的是 **评测**，不是创建 skill。

---

### Claude Code skill-creator

```
1. 写 skill 草稿
2. 写 test prompts（evals.json）
3. 并发 spawn with-skill vs baseline
4. grader 评分 → eval-viewer 展示
5. 人类反馈 → 改进 skill
6. 重复迭代
7. run_loop.py 优化 description 触发
```

**核心脚本**：
| 脚本 | 功能 | 是否复用 |
|------|------|----------|
| `run_eval.py` | 测试 skill 触发率（description 是否被正确触发） | ⚠️ 部分 |
| `run_loop.py` | description 优化循环 | 🟡 可选 |
| `aggregate_benchmark.py` | 汇总多 run 结果 → benchmark.json | ✅ 直接复用 |
| `generate_review.py` | 生成 HTML viewer | ✅ 直接复用 |

**核心 agents**：
| Agent | 功能 | 是否复用 |
|-------|------|----------|
| `grader.md` | 按 assertions 评分，输出 grading.json | ✅ 直接复用 |
| `comparator.md` | 盲测对比两个输出，判断 winner | ✅ 直接复用 |
| `analyzer.md` | 分析为什么 winner 赢了，给改进建议 | ✅ 直接复用 |

**核心 schemas**：
| Schema | 说明 | 是否复用 |
|--------|------|----------|
| `evals.json` | 定义测试场景 | ✅ 扩展（加 conversation_history） |
| `grading.json` | 评分结果 | ✅ 直接复用 |
| `benchmark.json` | 汇总统计 | ✅ 直接复用 |
| `comparison.json` | 盲测结果 | ✅ 直接复用 |
| `timing.json` | 执行时间和 tokens | ✅ 直接复用 |

---

## 二、与我们目标匹配的组件

### 完全匹配（直接复用）

| 组件 | 来源 | 说明 |
|------|------|------|
| `agents/grader.md` | Claude Code | LLM-as-judge 评分 prompt |
| `agents/comparator.md` | Claude Code | 盲测对比 |
| `agents/analyzer.md` | Claude Code | 差异分析 |
| `references/schemas.md` | Claude Code | JSON 结构定义 |
| `eval-viewer/generate_review.py` | Claude Code | HTML 报告生成 |
| `eval-viewer/viewer.html` | Claude Code | 前端模板 |
| `scripts/aggregate_benchmark.py` | Claude Code | 结果汇总 |

### 需要修改/扩展

| 组件 | 修改点 |
|------|--------|
| `evals.json` schema | 加 `conversation_history` 字段 |
| `run_eval.py` | 改为执行 agent 任务（不只是测触发率） |
| 对比逻辑 | 从 with-skill vs without-skill 改为 variant_a vs variant_b |

### 我们需要新写的

| 组件 | 说明 |
|------|------|
| `run_compare.py` | 并发执行两个 variant，注入 conversation_history |
| `grade.py` | 调用 grader.md prompt |
| SKILL.md | 入口文件 |

---

## 三、目录结构（最终）

```
openclaw-eval-skill/
├── SKILL.md                       # 入口
├── PLAN.md                        # 设计 plan
├── SPEC.md                        # 技术 spec
├── ANALYSIS.md                    # 本文件
│
├── agents/                        # 复用自 Claude Code
│   ├── grader.md                  # ✅ 直接复制
│   ├── comparator.md              # ✅ 直接复制
│   └── analyzer.md                # ✅ 直接复制
│
├── references/
│   ├── schemas.md                 # ✅ 复制 + 扩展（conversation_history）
│   └── judge-prompt.md            # 简化版 grader prompt
│
├── scripts/
│   ├── run_compare.py             # 🆕 新写（并发执行两个 variant）
│   ├── grade.py                   # 🆕 新写（调用 grader prompt）
│   └── aggregate_benchmark.py     # ✅ 直接复制
│
├── viewer/
│   ├── generate_review.py         # ✅ 直接复制
│   └── viewer.html                # ✅ 直接复制
│
└── evals/
    └── example.json               # 示例 evals.json
```

---

## 四、关键设计决策

### 1. 执行引擎

**Claude Code skill-creator 用的是**：`claude -p` CLI

**我们可以用**：
- `claude -p`（主要，支持 `--plugin-dir`）
- `sessions_spawn`（fallback，OpenClaw 原生）

**决策**：优先 `claude -p`，它支持精确控制 skill 加载。

### 2. 对话历史注入

**Claude Code 没有这个功能**（它只测触发率，不测上下文敏感性）

**我们需要加**：
```
方式 A：prompt 前缀注入
  [CONVERSATION HISTORY]
  User: ...
  Assistant: ...
  [END CONVERSATION HISTORY]
  
  Now continue with: <actual prompt>

方式 B：真实 session resume（v2）
  用 claude --resume 从保存的 session 恢复
```

**决策**：v1 用方式 A（简单可控）。

### 3. 对比模式

**Claude Code 只支持**：with-skill vs without-skill

**我们需要支持**：
- skill_a vs skill_b
- history_a vs history_b
- 混合对比

**改动点**：
- `run_compare.py` 不硬编码 with_skill/without_skill
- `aggregate_benchmark.py` 已支持任意 config name（无需改）
- `viewer.html` 已支持任意 config name（无需改）

---

## 五、还缺什么

| 功能 | 状态 | 说明 |
|------|------|------|
| SKILL.md | ❌ 未写 | 入口文件 |
| run_compare.py | ❌ 未写 | 核心执行逻辑 |
| grade.py | ❌ 未写 | 调用 grader |
| agents/*.md | ❌ 未复制 | 直接复制即可 |
| viewer/*.py | ❌ 未复制 | 直接复制即可 |
| schemas.md 扩展 | ❌ 未写 | 加 conversation_history |
| example evals.json | ❌ 未写 | 示例 |

---

## 六、下一步

1. **复制 Claude Code 组件**：agents/、viewer/、aggregate_benchmark.py
2. **扩展 schemas.md**：加 conversation_history 字段
3. **写 run_compare.py**：核心执行逻辑
4. **写 grade.py**：调用 grader
5. **写 SKILL.md**：入口
6. **写示例 evals.json**：用通用场景（原以 Cobo Agent Wallet 为例）
