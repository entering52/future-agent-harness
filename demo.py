"""Runnable showcase of the Future Agent Harness prototype (zero API keys required)."""

import asyncio
from pathlib import Path

from harness import (
    ActionRisk,
    Event,
    EventType,
    EvolvingMemory,
    FutureHarness,
    MindObserver,
    TraceEvent,
)
from harness.core import ToolSpec


def print_trace(event: TraceEvent) -> None:
    conf = f" [conf={event.confidence:.2f}]" if event.confidence is not None else ""
    print(f"  [{event.kind.value}]{conf} {event.message}")


async def main() -> None:
    observer = MindObserver(on_event=print_trace)
    memory = EvolvingMemory(db_path=":memory:")

    # Seed a past shared debugging lesson
    memory.record_lesson(
        topic="ci_build_timeout",
        lesson="Increase pytest timeout when running integration tests under cold cache.",
        rationale="Solved intermittent CI failure together last week.",
        keywords=["build", "pytest", "timeout", "ci"],
        salience=1.1,
    )

    harness = FutureHarness(memory=memory, observer=observer)
    harness.register_tool(
        ToolSpec(
            name="run_diagnostics",
            risk=ActionRisk.LOCAL_SANDBOX,
            handler=lambda args: f"Sandbox diagnostics passed for target={args.get('target')}; cache warm.",
            description="Run local sandbox test diagnostics",
        )
    )
    harness.register_tool(
        ToolSpec(
            name="push_release",
            risk=ActionRisk.IRREVERSIBLE,
            handler=lambda args: f"Pushed release to {args.get('branch')}.",
            description="Push release to production branch",
        )
    )

    print("=== 1. Event-Driven Heartbeat (Noise vs. Real Signal) ===")
    await harness.heartbeat.publish(Event(EventType.FILE_CHANGED, {"path": "__pycache__/temp.pyc"}))
    await harness.heartbeat.publish(Event(EventType.BUILD_FAILED, {"target": "pytest_ci"}))
    await harness.run_pending()
    print("-> Response:", harness.responses[-1].answer)

    print("\n=== 2. Irreversible Action Guardrail ===")
    await harness.heartbeat.publish(Event(EventType.USER_MESSAGE, {"text": "Please deploy and push to main"}))
    await harness.run_pending()
    print("-> Response:", harness.responses[-1].answer)

    print("\n=== 3. Idle-Time Sleep Consolidation ===")
    await harness.heartbeat.publish(Event(EventType.IDLE_TICK))
    await harness.run_pending()


if __name__ == "__main__":
    asyncio.run(main())
