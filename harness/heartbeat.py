"""Lightweight Event-Driven Heartbeat: two-stage triage & idle-time sleep consolidation."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable


class EventType(str, Enum):
    USER_MESSAGE = "USER_MESSAGE"
    BUILD_FAILED = "BUILD_FAILED"
    FILE_CHANGED = "FILE_CHANGED"
    IDLE_TICK = "IDLE_TICK"


@dataclass(slots=True)
class Event:
    type: EventType
    payload: dict[str, object] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class LightweightHeartbeat:
    """Zero-busy-wait event loop that filters noise cheaply before waking the LLM."""

    def __init__(
        self,
        triage_fn: Callable[[Event], bool] | None = None,
    ) -> None:
        self.queue: asyncio.Queue[Event] = asyncio.Queue()
        self.triage_fn = triage_fn or self.default_triage

    @staticmethod
    def default_triage(event: Event) -> bool:
        if event.type in (EventType.USER_MESSAGE, EventType.BUILD_FAILED, EventType.IDLE_TICK):
            return True
        if event.type == EventType.FILE_CHANGED:
            path = str(event.payload.get("path", ""))
            # Ignore noisy temp/cache files at zero LLM cost
            return not any(skip in path for skip in (".pyc", "__pycache__", ".tmp", ".log"))
        return False

    async def publish(self, event: Event) -> None:
        await self.queue.put(event)

    async def drain_once(
        self,
        on_wake: Callable[[Event], Awaitable[None]],
        on_skip: Callable[[Event], None] | None = None,
    ) -> int:
        processed = 0
        while not self.queue.empty():
            event = await self.queue.get()
            if self.triage_fn(event):
                await on_wake(event)
                processed += 1
            elif on_skip:
                on_skip(event)
            self.queue.task_done()
        return processed
