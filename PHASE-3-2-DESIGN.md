# Phase 3.2: Description Diagnostics (Design Document)

**Status**: Design complete, pending evaluation (2026-03-18)

**Core problem**: Auto-optimizing a description easily leads to local optima (overfitting to eval set).

---

## Problem Analysis

### Three Local Optimum Traps

**Trap 1: Inflated Trigger Rate**
```
Iteration 1: 70% → Iteration 2: 94% ✅ (looks good)
Reality: description is over-optimized to fit specific trigger queries
New, unseen queries may actually trigger less reliably
```

**Trap 2: Specificity Collapse**
```
Recall 94% but Specificity 60% ❌
Many queries that should NOT trigger end up triggering

Example:
"How do I debug a single conversation" → Expected: False, Actual: True
(because description accumulated too many general keywords)
```

**Trap 3: Description Bloat**
```
Original: 40 chars, clear
After 3 iterations: 200 chars, incoherent

New users can no longer understand the core scope
```

### Root Cause

> Single-metric optimization → multi-dimension imbalance  
> Automatic loops → no human judgment  
> Eval set artifacts → real-world failure

---

## Solution: Description Diagnostics

**Core idea**: No automatic optimization — diagnose + recommend + human decision.

### Mode Comparison

| | Optimization Loop | Diagnostics |
|--|--|--|
| Goal | Maximize trigger_rate | Find real problems |
| Flow | Auto-iterate | Diagnose → suggest → human decides |
| Risk | Local optimum | Requires human review |
| Result | Description bloat | Stays concise and accurate |
| Control | Low | High |

### Workflow

```
1. Run Trigger Test
   └─ trigger_rate_results.json

2. Analyze Failures
   ├─ What queries failed?
   ├─ Real problem or eval set artifact?
   └─ Is modifying the description worth it?

3. Generate Diagnostics Report
   ├─ Issue classification (low/medium/high)
   ├─ Specific recommendations (≤5)
   └─ Estimated improvement

4. Manual Review & Update
   └─ Human decides whether to modify SKILL.md

5. Re-test (optional)
   └─ Verify improvement
```

---

## Detailed Design

### Failure Analysis

```python
@dataclass
class FailedQuery:
    query_id: str
    query_text: str
    expected: bool
    triggered: bool
    failure_type: str  # "false_negative" | "false_positive"
    severity: str      # "critical" | "high" | "medium" | "low"
    root_cause: str    # "missing_keyword" | "too_broad" | "ambiguous" | "eval_artifact"
    is_worth_fixing: bool
    suggested_fix: str
```

### Severity Classification

```
CRITICAL (must fix)
├─ Query: "benchmark" (primary trigger word)
│  Issue: Core functionality fails to trigger
│  Action: Add "benchmark" to description

HIGH (should fix)
├─ Query: "A/B compare" (common synonym)
│  Issue: Common phrasing fails to trigger
│  Action: Add "A/B compare" + clarify vs general "compare"

MEDIUM (consider)
├─ Query: "metrics compare" (unusual phrasing)
│  Issue: Edge case, not common
│  Action: Consider, but risk of false positives

LOW (ignore)
├─ Query: "how to debug code" (unrelated)
│  Issue: Unrelated to skill, no fix needed
│  Action: Mark as eval artifact, skip
```

### Multi-Dimension Health Score

```python
@dataclass
class DescriptionHealth:
    trigger_recall: float       # 0-1: triggered when expected
    trigger_specificity: float  # 0-1: not triggered when not expected
    clarity_score: float        # 0-1: heuristic readability
    coverage_score: float       # 0-1: heuristic core scenario coverage
    composite_score: float      # weighted
    is_healthy: bool
    weakest_dimension: str

# Health thresholds
trigger_recall >= 0.80
trigger_specificity >= 0.90
clarity_score >= 0.70      # heuristic, directional only
coverage_score >= 0.75     # heuristic, directional only
```

> **Note**: clarity and coverage scores are heuristic estimates based on text patterns.
> They are directional guides, not definitive judgments. Use human judgment.

---

## Diagnostics Report Format (RECOMMENDATIONS.md)

```markdown
# Description Diagnostics Report

## Summary
- Trigger Rate: 70% (recall: 85%, specificity: 92%)
- Failed Queries: 3 critical, 2 high, 2 low
- Recommendation: Fix 3 critical + 1 high = ~10pp improvement expected

## Critical Issues (Must Fix)

### Issue 1: "benchmark" not triggered
- Query ID: tq-3
- Severity: CRITICAL
- Root Cause: Primary trigger word missing from description
- Suggested Fix: Add "benchmark" to trigger words list
- Expected Impact: +5pp recall
- Risk: None

## Action Items
- [ ] Add "benchmark" to USE WHEN section
- [ ] Add "A/B compare" + clarify NOT for
- [ ] Re-test after changes
```

---

## Implementation Checklist

- [x] `scripts/run_diagnostics.py` — main script
- [x] Multi-dimension health scoring
- [x] Severity classification + is_worth_fixing logic
- [x] RECOMMENDATIONS.md report generation
- [ ] Evaluate: should clarity/coverage use LLM-as-judge instead of heuristics?

---

## Time Estimate

**Design**: ✅ Complete (2026-03-18)  
**Implementation**: ✅ Script complete  
**Single run**: ~30s
