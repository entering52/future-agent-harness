"""Future Agent Harness — a lightweight prototype demonstrating:
1. Event-driven lightweight heartbeat with two-stage wakeup & idle consolidation
2. Evolving shared memory with salience decay, reinforcement & superseding
3. Elastic trust-tiered sandbox with dynamic autonomy & irreversible guardrails
4. Transparent mind observability stream (intent, confidence, blockers)
"""

from .core import FutureHarness, LLMBackend, MockReasoningBackend, HarnessResponse
from .heartbeat import Event, EventType, LightweightHeartbeat
from .memory import EvolvingMemory, MemoryEntry
from .observability import MindObserver, TraceEvent, TraceKind
from .trust_gate import ActionRisk, ElasticTrustGate, GateDecision

__all__ = [
    "ActionRisk",
    "ElasticTrustGate",
    "Event",
    "EventType",
    "EvolvingMemory",
    "FutureHarness",
    "GateDecision",
    "HarnessResponse",
    "LLMBackend",
    "LightweightHeartbeat",
    "MemoryEntry",
    "MindObserver",
    "MockReasoningBackend",
    "TraceEvent",
    "TraceKind",
]
