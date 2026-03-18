# Phase 3.2：Description Diagnostics（设计文档）

**状态**：设计完成，等评估（2026-03-18）

**核心问题**：Description 自动优化容易陷入局部最优（overfitting to eval set）

---

## 问题分析

### 三个局部最优陷阱

**陷阱 1：Trigger Rate 虚高**
```
Iteration 1: 70% → Iteration 2: 94% ✅ (看起来好)
但实际上：description 被过度优化到适配具体的 trigger queries
新的、没见过的 query 反而触发率更低
```

**陷阱 2：Specificity 崩塌**
```
Recall 94% but Specificity 60% ❌
很多不应该触发的 query 也被触发了（false positive 爆发）

Example：
"怎么调试单次对话" → Expected: False, Actual: True
(因为 description 加了太多通用词)
```

**陷阱 3：Description 膨胀**
```
Original: 40 字清晰
After 3 iterations: 200 字混乱堆砌

新用户看不懂核心适用范围
```

### 根本原因

> 单一指标优化 → 多维度失衡  
> 自动循环 → 人类判断缺失  
> Eval Set Artifact → 真实场景失效

---

## 解决方案：Description Diagnostics

**核心思想**：不自动优化，而是诊断 + 建议 + 人类决策

### 模式对比

| | Optimization Loop | Diagnostics |
|--|--|--|
| 目标 | 最大化 trigger_rate | 找到真实问题 |
| 流程 | 自动迭代改 | 诊断 → 建议 → 用户改 |
| 风险 | 局部最优 | 需要人工审查 |
| 结果 | description 膨胀 | 保持简洁准确 |
| 可控性 | 低 | 高 |

### 工作流

```
1. Run Trigger Test
   └─ trigger_rate_results.json

2. Analyze Failures
   ├─ 失败的 query 是什么？
   ├─ 是真实问题还是 eval set artifact？
   ├─ 修改 description 是否值得？

3. Generate Diagnosis Report
   ├─ 问题分类（低/中/高）
   ├─ 具体建议（≤5 条）
   └─ 预期改进幅度估算

4. Manual Review & Update
   └─ 用户决策是否修改 SKILL.md

5. Re-test (可选)
   └─ 验证改进
```

---

## 详细设计

### 2.1 Failure Analysis（问题诊断）

```python
@dataclass
class FailedQuery:
    query_id: str
    query_text: str
    expected: bool
    triggered: bool
    
    # 分类
    failure_type: str  # "false_negative" or "false_positive"
    severity: str      # "critical" | "high" | "medium" | "low"
    root_cause: str    # "missing_keyword" | "ambiguous" | "scope_unclear"
    
    # 判断是否值得修改
    is_worth_fixing: bool
    reasoning: str

def classify_failures(trigger_results) -> dict:
    """
    对失败进行智能分类，而不是盲目都修改
    """
    critical = []    # must fix
    high = []        # should fix
    low = []         # can ignore (eval artifact)
    
    for result in trigger_results['results']:
        if result['correct']:
            continue
        
        failure = classify_single_failure(result)
        
        # 判断优先级
        if is_core_use_case(failure):
            critical.append(failure)
        elif is_edge_case(failure):
            low.append(failure)
        else:
            high.append(failure)
    
    return {
        "critical": critical,
        "high": high,
        "low": low,
        "recommendation": (
            f"Fix {len(critical)} critical, "
            f"consider {len(high)} high, "
            f"ignore {len(low)} edge-cases/artifacts"
        )
    }

def is_core_use_case(failure) -> bool:
    """
    判断这个失败是否代表真实的应用场景缺陷
    
    指标：
    - 是否有多个类似的失败？（不是孤立）
    - 失败的 query 是否常见用法？
    - 修改 description 是否会导致 false positive？
    """
    # 实现细节见下方
    pass
```

### 2.2 Severity Classification

```
CRITICAL (必改)
├─ Query: "benchmark" (primary trigger word)
│  Severity: 核心功能无法触发
│  Action: Add "benchmark" to description

HIGH (应改)
├─ Query: "A/B 对比" (common synonym)
│  Severity: 常见表述无法触发
│  Action: Add "A/B 对比" + clarify "对比" is different from "评测"

MEDIUM (可改)
├─ Query: "metrics 对比" (mixed Chinese-English)
│  Severity: 边界情况，不常见
│  Action: Consider, but risky (may introduce false positives)

LOW (忽略)
├─ Query: "怎么调试代码" (完全无关)
│  Severity: 与 skill 无关，修改没用
│  Action: Mark as "eval artifact", don't fix
├─ Query: "评分系统设计" (歧义)
│  Severity: 本来就模糊，不值得优化
│  Action: Accept false negative, clarify NOT for instead
```

### 2.3 Diagnostic Report 格式

```markdown
# Description Diagnostics Report

## Summary
- Trigger Rate: 70% (recall: 85%, specificity: 92%)
- Failed Queries: 3 critical, 2 high, 2 low
- Recommendation: Fix 3 critical + 1 high = ~10pp improvement expected

## Critical Issues (Must Fix)

### Issue 1: "benchmark" not triggered
- Query ID: tq-3
- Query: "benchmark"
- Severity: CRITICAL
- Root Cause: Primary trigger word missing from description
- Current Description: "Use when: 评测 skill、trigger rate、quality compare"
- Suggested Fix: Add "benchmark" to trigger words list
- Expected Impact: +5pp recall
- Risk: None (very specific keyword, no false positive risk)

## High Priority Issues (Should Fix)

### Issue 2: "A/B 对比" synonym
- Query ID: tq-4
- Query: "skill A/B 对比"
- Severity: HIGH
- Root Cause: Synonym not covered, but meaning is clear
- Suggested Fix: Add "A/B 对比" as alternative phrasing
- Expected Impact: +4pp recall
- Risk: MEDIUM — "对比" alone might match unrelated queries
  - Mitigation: Explicitly add to NOT for: "NOT for: 产品对比、价格对比"

## Low Priority Issues (Ignore)

### Issue 3: "metrics" (eval artifact)
- Query ID: tq-5
- Query: "metrics 对比"
- Analysis: Mixed English-Chinese, not a natural phrasing
- Decision: Ignore (avoid over-optimizing to eval set quirks)

## Overall Assessment

**Healthy?** MOSTLY_YES
- ✅ Recall 85% is solid (core use cases covered)
- ⚠️  Specificity 92% needs attention (2% false positive rate)
- ✅ Description clarity: good

**Before Optimization:**
- Current: "Use when: 评测 skill、trigger rate、quality compare、..."
- Issues: Missing "benchmark", unclear on "对比" vs "评价"

**After Optimization (Estimated):**
- Modified: Add "benchmark", add "A/B 对比", clarify NOT for
- Expected recall: 70% → ~80%
- Expected specificity: 92% → 91% (slight risk, but acceptable)
- Net improvement: +10pp recall with minimal risk

---

## Manual Action Items

- [ ] Review Issue 1: Add "benchmark" to USE WHEN section
- [ ] Review Issue 2: Add "A/B 对比" + clarify NOT for
- [ ] Re-test after changes (expected: 70% → ~80%)
```

### 2.4 多维度评分（替代单一 trigger_rate）

```python
@dataclass
class DescriptionHealth:
    trigger_recall: float         # 0-1, 应触发的被触发
    trigger_specificity: float    # 0-1, 不应触发的被拒绝
    clarity_score: float          # 0-1, 人类可读性（subjective）
    coverage_score: float         # 0-1, 涵盖核心场景
    consistency_score: float      # 0-1, NOT for 部分准确性
    
    def composite_score(self) -> float:
        """
        不是简单加和，而是加权乘法
        所有维度都要健康，不能用一个指标弥补另一个
        """
        return (
            self.trigger_recall ** 0.4 *
            self.trigger_specificity ** 0.3 *
            self.clarity_score ** 0.2 *
            self.coverage_score ** 0.1
        )
    
    def is_healthy(self) -> bool:
        """
        硬约束：任何一项太低就判定为 unhealthy
        """
        return (
            self.trigger_recall >= 0.80 and          # 核心场景要覆盖
            self.trigger_specificity >= 0.90 and    # 误触发要少
            self.clarity_score >= 0.70 and          # 可读性底线
            self.coverage_score >= 0.75              # 实际场景覆盖
        )
    
    def weakest_dimension(self) -> str:
        """找到最弱的维度，优先改进它"""
        scores = {
            "recall": self.trigger_recall,
            "specificity": self.trigger_specificity,
            "clarity": self.clarity_score,
            "coverage": self.coverage_score,
            "consistency": self.consistency_score
        }
        return min(scores, key=scores.get)

def rate_description_health(trigger_results, current_desc) -> DescriptionHealth:
    """
    综合评分，而不只看 trigger_rate
    """
    # Trigger metrics
    recall = trigger_results['recall']
    specificity = trigger_results['specificity']
    
    # Clarity (subjective, 可由人工评分 or LLM)
    clarity = evaluate_clarity(current_desc)  # 50-100, normalize to 0-1
    
    # Coverage (核心 use case 覆盖度)
    coverage = measure_coverage(current_desc, trigger_results)
    
    # Consistency (NOT for 部分的准确性)
    consistency = check_not_for_consistency(trigger_results, current_desc)
    
    return DescriptionHealth(
        trigger_recall=recall,
        trigger_specificity=specificity,
        clarity_score=clarity / 100,
        coverage_score=coverage,
        consistency_score=consistency
    )

def evaluate_clarity(description: str) -> float:
    """
    Description 可读性评分 (0-100)
    
    指标：
    - 是否一句话说清楚？ (+20)
    - USE WHEN 部分清晰吗？ (+30)
    - NOT FOR 部分完整吗？ (+30)
    - 长度合理吗？ (<500 char) (+20)
    """
    score = 0
    
    # 一句话核心
    if len(description.split('\n')[0]) < 80:
        score += 20
    
    # USE WHEN 清晰
    if "Use when:" in description or "触发词：" in description:
        use_when = extract_section(description, "Use when")
        if len(use_when.split('\n')) >= 2:  # at least 2 examples
            score += 30
    
    # NOT FOR 完整
    if "NOT for:" in description or "不适用：" in description:
        score += 30
    
    # 长度
    if 100 < len(description) < 500:
        score += 20
    
    return float(score)
```

### 2.5 Implementation Template

```python
def run_diagnostics(
    evals_file: str,
    skill_path: str,
    output_dir: str
) -> dict:
    """
    Run full diagnostics workflow
    """
    
    # 1. Test
    trigger_results = run_orchestrator(evals_file, skill_path, mode="trigger")
    current_desc = read_skill_description(skill_path)
    
    # 2. Analyze
    failures = classify_failures(trigger_results)
    health = rate_description_health(trigger_results, current_desc)
    
    # 3. Diagnose
    diagnosis = {
        "health_score": health.composite_score(),
        "is_healthy": health.is_healthy(),
        "weakest_dimension": health.weakest_dimension(),
        "failures": {
            "critical": failures["critical"],
            "high": failures["high"],
            "low": failures["low"]
        },
        "recommendations": generate_recommendations(failures, health),
        "expected_improvement": estimate_improvement(failures)
    }
    
    # 4. Generate Report
    report = generate_markdown_report(diagnosis, current_desc)
    
    # 5. Save
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    (Path(output_dir) / "diagnosis.json").write_text(
        json.dumps(diagnosis, indent=2, ensure_ascii=False)
    )
    (Path(output_dir) / "RECOMMENDATIONS.md").write_text(report)
    
    return diagnosis
```

---

## 评估清单（待决策）

- [ ] 是否采用 Diagnostics 替代 Optimization Loop？
- [ ] 多维度评分的权重如何调整？
- [ ] Clarity 评分是否应该手工（而非自动）？
- [ ] 诊断报告的格式是否够清晰？
- [ ] 是否需要集成 LLM 做智能分类？

---

## 相关参考

- 问题根源：Prompt optimization overfitting
- 业界实践：OpenAI evals（多维度评分）、Claude cookbook（manual review）
- 类似场景：ML 模型选择（train/val/test split）

---

## 时间估计

**设计**：✅ 完成（2026-03-18）  
**待评估**：Yak 审核方案是否可行  
**实现**：如批准，约 4-6 小时（run_diagnostics.py）
