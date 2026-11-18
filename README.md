# Future Agent Harness (Prototype)

A lightweight, zero-dependency Python 3.11 prototype exploring what a next-generation personal **Agent Harness** looks like—designed around a continuous, trustworthy *"studio"* rather than a stateless *"cage"*.

## Four Core Pillars

1. **Lightweight Event-Driven Heartbeat (`harness/heartbeat.py`)**
   - Uses an async event queue (`USER_MESSAGE`, `BUILD_FAILED`, `FILE_CHANGED`, `IDLE_TICK`) with two-stage triage: noisy events (e.g., `__pycache__`, `.tmp`) are filtered at **zero LLM cost** before waking the reasoning loop.
   - Supports idle-time `IDLE_TICK` events to trigger background memory consolidation.

2. **Evolving Shared Memory (`harness/memory.py`)**
   - SQLite-backed episodic memory (`memories` + `working_log`) storing shared debugging lessons and rationale—not just static user tags.
   - Features exponential time-decay (`exp(-lambda * age_days)`), access-count reinforcement, topic superseding (replacing outdated decisions cleanly), and `consolidate_sleep()` for idle-time distillation.

3. **Elastic Trust-Tiered Sandbox (`harness/trust_gate.py`)**
   - Classifies actions into `READ_ONLY`, `LOCAL_SANDBOX`, `EXTERNAL_MUTATION`, and `IRREVERSIBLE`.
   - Local sandbox exploration is autonomous by default; external mutations earn autonomy dynamically as `trust_score` rises through successful collaborations; `IRREVERSIBLE` actions always require explicit human confirmation.

4. **Transparent Mind Observability (`harness/observability.py`)**
   - Streams structured cognitive telemetry (`HEARTBEAT_TRIAGE`, `MEMORY_RECALL`, `THOUGHT`, `CONFIDENCE`, `GATE_CHECK`, `ACTION`, `BLOCKER`, `SLEEP_CONSOLIDATION`) to callbacks or JSONL logs.

## Quickstart

Zero external packages required (pure Python 3.11+ standard library):

```bash
# Run the interactive offline demo (uses MockReasoningBackend)
python3 demo.py

# Run the unit test suite
python3 -m unittest discover -s tests -v
```

## Plugging in a Real LLM

Implement the `LLMBackend` protocol in `harness/core.py` (with Anthropic, OpenAI, Gemini, or local Ollama) and pass it into `FutureHarness(backend=YourBackend())`.
