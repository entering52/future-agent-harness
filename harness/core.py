"""Core Agent Loop integrating heartbeat, evolving memory, trust gate, and observability."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from .heartbeat import Event, EventType, LightweightHeartbeat
from .memory import EvolvingMemory, MemoryEntry
from .observability import MindObserver, TraceKind
from .trust_gate import ActionRisk, ElasticTrustGate


@dataclass(slots=True)
class ToolSpec:
    name: str
    risk: ActionRisk
    handler: Callable[[dict[str, object]], str]
    description: str = ""


@dataclass(slots=True)
class PlannedStep:
    thought: str
    confidence: float
    tool_name: str | None = None
    tool_args: dict[str, object] = field(default_factory=dict)
    final_answer: str | None = None


@dataclass(slots=True)
class HarnessResponse:
    answer: str
    pending_confirmations: list[dict[str, object]] = field(default_factory=list)
    recalled_memories: list[MemoryEntry] = field(default_factory=list)


class LLMBackend(Protocol):
    def plan(
        self,
        event: Event,
        memories: list[MemoryEntry],
        tools: list[ToolSpec],
        observations: list[str],
    ) -> PlannedStep:
        ...


class MockReasoningBackend:
    """Offline deterministic backend for testing and demonstrating the harness without API keys."""

    def plan(
        self,
        event: Event,
        memories: list[MemoryEntry],
        tools: list[ToolSpec],
        observations: list[str],
    ) -> PlannedStep:
        if not observations:
            if event.type == EventType.BUILD_FAILED:
                return PlannedStep(
                    thought="Build failed; checking local test logs in sandbox before suggesting a fix.",
                    confidence=0.86,
                    tool_name="run_diagnostics",
                    tool_args={"target": event.payload.get("target", "main")},
                )
            if event.type == EventType.USER_MESSAGE:
                text = str(event.payload.get("text", ""))
                if "deploy" in text.lower() or "push" in text.lower():
                    return PlannedStep(
                        thought="User requested deployment; checking external push gate.",
                        confidence=0.91,
                        tool_name="push_release",
                        tool_args={"branch": "main"},
                    )
                return PlannedStep(
                    thought="Recalled relevant context; responding directly to user.",
                    confidence=0.92,
                    final_answer=f"Processed '{text}' with {len(memories)} recalled memory item(s).",
                )

        return PlannedStep(
            thought="Diagnostics complete; synthesizing root cause and next step.",
            confidence=0.89,
            final_answer=f"Completed analysis. Observations: {'; '.join(observations)}",
        )


class FutureHarness:
    """Orchestrates the 4 pillars of the next-gen personal Agent Harness."""

    def __init__(
        self,
        backend: LLMBackend | None = None,
        memory: EvolvingMemory | None = None,
        trust_gate: ElasticTrustGate | None = None,
        observer: MindObserver | None = None,
        heartbeat: LightweightHeartbeat | None = None,
        max_steps: int = 4,
    ) -> None:
        self.backend = backend or MockReasoningBackend()
        self.memory = memory or EvolvingMemory()
        self.trust_gate = trust_gate or ElasticTrustGate()
        self.observer = observer or MindObserver()
        self.heartbeat = heartbeat or LightweightHeartbeat()
        self.max_steps = max_steps
        self.tools: dict[str, ToolSpec] = {}
        self.responses: list[HarnessResponse] = []

    def register_tool(self, tool: ToolSpec) -> None:
        self.tools[tool.name] = tool

    async def handle_event(self, event: Event) -> HarnessResponse | None:
        if event.type == EventType.IDLE_TICK:
            count = self.memory.consolidate_sleep()
            self.observer.emit(
                TraceKind.SLEEP_CONSOLIDATION,
                f"Consolidated {count} working log item(s) during idle sleep.",
                consolidated_count=count,
            )
            return None

        query_text = " ".join(str(v) for v in event.payload.values()) or event.type.value
        if event.type == EventType.USER_MESSAGE:
            self.memory.log_turn("user", str(event.payload.get("text", "")))

        recalled = self.memory.recall(query_text, limit=3)
        self.observer.emit(
            TraceKind.MEMORY_RECALL,
            f"Recalled {len(recalled)} relevant episodic memory item(s).",
            topics=[m.topic for m in recalled],
        )

        observations: list[str] = []
        pending_confirmations: list[dict[str, object]] = []
        final_answer = ""

        for step_idx in range(1, self.max_steps + 1):
            plan = self.backend.plan(event, recalled, list(self.tools.values()), observations)
            self.observer.emit(
                TraceKind.THOUGHT,
                plan.thought,
                confidence=plan.confidence,
                step=step_idx,
            )
            self.observer.emit(
                TraceKind.CONFIDENCE,
                f"Step {step_idx} confidence: {plan.confidence:.2f}",
                confidence=plan.confidence,
            )

            if plan.final_answer is not None:
                final_answer = plan.final_answer
                break

            if plan.tool_name:
                tool = self.tools.get(plan.tool_name)
                if tool is None:
                    self.observer.emit(
                        TraceKind.BLOCKER,
                        f"Requested unknown tool '{plan.tool_name}'.",
                    )
                    observations.append(f"Error: unknown tool '{plan.tool_name}'")
                    continue

                decision = self.trust_gate.evaluate(tool.name, tool.risk)
                self.observer.emit(
                    TraceKind.GATE_CHECK,
                    decision.reason,
                    tool=tool.name,
                    risk=tool.risk.value,
                    allowed=decision.allowed,
                    trust_score=decision.trust_score,
                )

                if decision.requires_confirmation:
                    pending_confirmations.append(
                        {
                            "tool": tool.name,
                            "args": plan.tool_args,
                            "reason": decision.reason,
                            "trust_score": decision.trust_score,
                        }
                    )
                    self.observer.emit(
                        TraceKind.BLOCKER,
                        f"Paused for human confirmation before executing '{tool.name}'.",
                        tool=tool.name,
                    )
                    final_answer = f"Awaiting confirmation to run '{tool.name}': {decision.reason}"
                    break

                result = tool.handler(plan.tool_args)
                new_trust = self.trust_gate.record_outcome(tool.name, success=True)
                self.observer.emit(
                    TraceKind.ACTION,
                    f"Executed '{tool.name}' -> trust updated to {new_trust:.2f}",
                    tool=tool.name,
                    result_preview=result[:120],
                )
                observations.append(result)

        if not final_answer:
            final_answer = f"Completed {len(observations)} step(s)."

        self.memory.log_turn("assistant", final_answer)
        resp = HarnessResponse(
            answer=final_answer,
            pending_confirmations=pending_confirmations,
            recalled_memories=recalled,
        )
        self.responses.append(resp)
        return resp

    async def run_pending(self) -> list[HarnessResponse]:
        async def _wake(ev: Event) -> None:
            await self.handle_event(ev)

        def _skip(ev: Event) -> None:
            self.observer.emit(
                TraceKind.HEARTBEAT_TRIAGE,
                f"Skipped noisy event {ev.type.value} at zero LLM cost.",
                payload=ev.payload,
            )

        await self.heartbeat.drain_once(on_wake=_wake, on_skip=_skip)
        return self.responses
