"""Transparent Mind Observability: streams internal state, confidence, and blockers."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable


class TraceKind(str, Enum):
    HEARTBEAT_TRIAGE = "HEARTBEAT_TRIAGE"
    MEMORY_RECALL = "MEMORY_RECALL"
    THOUGHT = "THOUGHT"
    CONFIDENCE = "CONFIDENCE"
    GATE_CHECK = "GATE_CHECK"
    ACTION = "ACTION"
    BLOCKER = "BLOCKER"
    SLEEP_CONSOLIDATION = "SLEEP_CONSOLIDATION"


@dataclass(slots=True)
class TraceEvent:
    kind: TraceKind
    message: str
    confidence: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data


class MindObserver:
    """Records and streams structured cognitive telemetry for human transparency."""

    def __init__(
        self,
        log_path: str | Path | None = None,
        on_event: Callable[[TraceEvent], None] | None = None,
    ) -> None:
        self.log_path = Path(log_path) if log_path else None
        self.on_event = on_event
        self.events: list[TraceEvent] = []
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        kind: TraceKind,
        message: str,
        *,
        confidence: float | None = None,
        **metadata: object,
    ) -> TraceEvent:
        event = TraceEvent(
            kind=kind,
            message=message,
            confidence=confidence,
            metadata=dict(metadata),
        )
        self.events.append(event)
        if self.log_path:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        if self.on_event:
            self.on_event(event)
        return event

    def recent(self, limit: int = 20) -> list[TraceEvent]:
        return self.events[-limit:]
