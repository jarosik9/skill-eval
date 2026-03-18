# Phase 3.3: True Session Context (Design & Implementation)

**Status**: Design + core tools implemented, deferred (2026-03-18)

**Decision**: Use real history extraction (not synthetic generation).

---

## Core Approach: True History Extraction

### Workflow

```
Run 1 (Iteration 1)
├─ run_orchestrator.py with evals/example-quality.json
├─ Output: session keys per eval
└─ Record session keys

Extract Histories (from Run 1 results)
├─ extract_session_history.py --session-key uuid-A --eval-id 1 → eval-1.json
└─ Output: workspace/.../raw/histories/eval-{id}.json files

Build Combined Evals
├─ build_evals_with_context.py
│   --base-evals evals/example-quality.json
│   --histories evals/histories
│   --output evals/with-context.json
└─ Output: evals.json with conversation_history populated

Run 2 (Iteration 2 - with context)
├─ run_orchestrator.py with evals/with-context.json
└─ Measures: does history improve quality/recall?
```

---

## Implemented Tools

### Tool 1: extract_session_history.py

**Purpose**: Extract conversation history from a completed session.

```bash
python scripts/extract_session_history.py \
    --session-key "agent:mo9:subagent:abc123def456" \
    --eval-id 1 \
    --eval-name "onboarding-setup" \
    --output-file evals/histories/eval-1.json
```

**Output format**:
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

**Extraction rules**:
- ✅ Keep: `role="user"` and `role="assistant"` messages
- ✅ Keep: string content and text blocks from array content
- ❌ Skip: tool_use / tool_result blocks
- ❌ Skip: empty messages

---

### Tool 2: build_evals_with_context.py

**Purpose**: Merge extracted histories into evals.json.

```bash
python scripts/build_evals_with_context.py \
    --base-evals evals/example-quality.json \
    --histories evals/histories \
    --output evals/with-context.json \
    --summary
```

**Output**: For each base eval, creates two variants:
- Fresh (no history): original ID
- With-context: ID × 10 + 1 (e.g., eval-1 → eval-11)

---

## Full Workflow Example

```bash
# Step 1: Initial evaluation
cd <skill-root>
python scripts/run_orchestrator.py \
    --evals evals/example-quality.json \
    --skill-path ./SKILL.md \
    --mode both \
    --output-dir workspace/iter-1 \
    --workers 6
# Note down session keys from logs

# Step 2: Extract histories
mkdir -p evals/histories
python scripts/extract_session_history.py \
    --session-key "agent:mo9:subagent:xxx2" \
    --eval-id 1 \
    --output-file evals/histories/eval-1.json \
    --print

# Step 3: Build combined evals
python scripts/build_evals_with_context.py \
    --base-evals evals/example-quality.json \
    --histories evals/histories \
    --output evals/with-context.json \
    --summary

# Step 4: Run with context
python scripts/run_orchestrator.py \
    --evals evals/with-context.json \
    --skill-path ./SKILL.md \
    --mode both \
    --output-dir workspace/iter-2-context \
    --workers 6
```

---

## Use Cases

### Use Case 1: Memory Continuity Testing
Does the skill behave differently when the agent already knows context?
```
Fresh:        "Help me evaluate skill quality"
With context: "I read about your eval framework. Now help me test my custom skill."
```

### Use Case 2: Context Utilization
Does the agent actually use the history?
```
eval-1 (fresh):   "You can use run_orchestrator.py..."
eval-11 (context): "Based on your setup, use run_orchestrator.py with these flags..."
```

### Use Case 3: Context Contamination Detection
Does history introduce incorrect assumptions?
```
If eval-11 performs WORSE than eval-1 → history may be misleading the agent
```

---

## Known Limitations

- **Not true session resumption**: uses text prefix to simulate history, agent doesn't know it's "continuing"
- **Context window growth**: full history may be 100-500 tokens extra
- **History from eval runs**: not natural user conversation, but sufficient for testing "can history be utilized"

---

## Implementation Checklist

- [x] `scripts/extract_session_history.py`
- [x] `scripts/build_evals_with_context.py`
- [ ] Update `run_compare.py` to support conversation_history injection
- [ ] Documentation: full usage guide (README Phase 3.3 section)

**Deferred reason**: Not the most urgent need. Focus on Phase 3.2 and 3.4 first.
Can be revisited when testing memory continuity is needed.
