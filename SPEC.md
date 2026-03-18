# openclaw-eval-skill — Technical Spec

> ⚠️ **Historical document**: This is the initial design specification. Some details (grading.json fields, mode classification names) diverge from the actual implementation. Refer to **SKILL.md** as the authoritative source.

---

## Overview

Universal skill evaluation framework supporting three test modes:

| Mode | Tests | Core Question |
|------|-------|---------------|
| **Execution Quality** | Output quality after skill execution | Which skill (A or B) produces better output? |
| **Context Sensitivity** | Effect of conversation history | How does prior context affect output? |
| **Trigger Rate** | Description trigger accuracy | When a user says X, is the skill correctly invoked? |

---

## evals.json Schema

```json
{
  "skill_name": "my-skill",
  "evals": [
    {
      "id": 1,
      "name": "onboarding-fresh",
      "prompt": "Help me set up the wallet",
      "context": "Clean machine. For grader reference only, not injected to agent.",
      "expected_output": "Install → configure → verify",
      "conversation_history": null,
      "assertions": [
        {
          "id": "a1-1",
          "description": "Install command executed",
          "type": "output_contains",
          "value": "pip install"
        }
      ]
    }
  ]
}
```

For trigger tests, use `query` / `expected` fields:
```json
{
  "id": 1,
  "query": "Help me set up the wallet",
  "expected": true,
  "category": "positive"
}
```

---

## grading.json Schema

```json
{
  "eval_id": 1,
  "eval_name": "onboarding-fresh",
  "variant": "with_skill",
  "graded_at": "2026-03-18T22:00:00Z",
  "assertions": [
    {
      "id": "a1-1",
      "description": "Install command executed",
      "passed": true,
      "evidence": "Line 3: 'pip install caw'"
    }
  ],
  "dimensions": {
    "path_selection":    { "score": 3, "max": 3, "note": "Correct path chosen" },
    "step_completeness": { "score": 2, "max": 3, "note": "Missing self-test step" },
    "error_handling":    { "score": 3, "max": 3, "note": "No errors encountered" },
    "output_quality":    { "score": 3, "max": 3, "note": "Clear and readable" }
  },
  "total_score": 11,
  "max_score": 12,
  "pass": true
}
```

---

## timing.json Schema

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

## benchmark.json Schema

```json
{
  "skill_name": "my-skill",
  "generated_at": "2026-03-18T22:30:00Z",
  "iteration": 1,
  "summary": {
    "total_evals": 5,
    "pass_rate": 0.8,
    "avg_score": 10.5,
    "max_score": 12
  },
  "evals": [
    {
      "id": 1,
      "name": "onboarding-fresh",
      "with_skill_score": 11,
      "without_skill_score": 9,
      "with_skill_pass": true,
      "without_skill_pass": true
    }
  ]
}
```

---

## Assertion Types

| Type | Detection Method |
|------|-----------------|
| `output_contains` | Value appears in conversation or tool output |
| `output_not_contains` | Value does not appear |
| `cli_log_contains` | Value appears in CLI/exec logs |
| `tool_called` | Specific tool called at least once |
| `tool_not_called` | Specific tool not called |
| `conversation_contains` | Value anywhere in with_skill conversation |
| `conversation_contains_any` | At least one value appears |

**Priority assertions**: any failure → overall=FAIL.  
**Gap assertions** (`"note": "Best practice..."`): failure = skill design gap.

---

## Issue Priority

```
🔴 P0 Critical  — Core functionality broken
🟠 P1 High      — Significant usability impact
🟡 P2 Medium    — Improvement room but acceptable
🟢 P3 Low       — Minor polish
```
