import asyncio
import time
import unittest

from harness import (
    ActionRisk,
    ElasticTrustGate,
    Event,
    EventType,
    EvolvingMemory,
    FutureHarness,
    MindObserver,
    TraceKind,
)
from harness.core import ToolSpec


class TestFutureHarness(unittest.TestCase):
    def test_memory_decay_and_supersede(self) -> None:
        mem = EvolvingMemory(db_path=":memory:", decay_half_life_days=7.0)
        now = time.time()
        old_id = mem.record_lesson(
            topic="auth_strategy",
            lesson="Use session cookies",
            rationale="Initial prototype",
            keywords=["auth", "cookies"],
            now=now - 10 * 86400,
        )
        new_id = mem.record_lesson(
            topic="auth_strategy",
            lesson="Use short-lived JWT + refresh token",
            rationale="Upgraded for stateless API",
            keywords=["auth", "jwt"],
            supersede_topic=True,
            now=now,
        )
        self.assertNotEqual(old_id, new_id)
        recalled = mem.recall("auth", now=now)
        self.assertEqual(len(recalled), 1)
        self.assertEqual(recalled[0].id, new_id)
        self.assertIn("JWT", recalled[0].lesson)

    def test_elastic_trust_gate(self) -> None:
        gate = ElasticTrustGate(initial_trust=0.40, promotion_threshold=0.70)
        self.assertTrue(gate.evaluate("read_file", ActionRisk.READ_ONLY).allowed)
        self.assertTrue(gate.evaluate("run_tests", ActionRisk.LOCAL_SANDBOX).allowed)

        # External mutation initially requires confirmation
        d1 = gate.evaluate("create_pr", ActionRisk.EXTERNAL_MUTATION)
        self.assertTrue(d1.requires_confirmation)

        # Earn trust over 3 successful runs
        for _ in range(3):
            gate.record_outcome("create_pr", success=True)
        d2 = gate.evaluate("create_pr", ActionRisk.EXTERNAL_MUTATION)
        self.assertTrue(d2.allowed)
        self.assertFalse(d2.requires_confirmation)

        # Irreversible action ALWAYS requires confirmation
        for _ in range(5):
            gate.record_outcome("delete_prod_db", success=True)
        d3 = gate.evaluate("delete_prod_db", ActionRisk.IRREVERSIBLE)
        self.assertFalse(d3.allowed)
        self.assertTrue(d3.requires_confirmation)

    def test_heartbeat_triage_and_full_loop(self) -> None:
        observer = MindObserver()
        harness = FutureHarness(observer=observer)
        harness.register_tool(
            ToolSpec(
                name="run_diagnostics",
                risk=ActionRisk.LOCAL_SANDBOX,
                handler=lambda args: f"ok:{args.get('target')}",
            )
        )

        async def _run() -> None:
            await harness.heartbeat.publish(Event(EventType.FILE_CHANGED, {"path": "build/__pycache__/a.pyc"}))
            await harness.heartbeat.publish(Event(EventType.BUILD_FAILED, {"target": "unit"}))
            await harness.heartbeat.publish(Event(EventType.IDLE_TICK))
            await harness.run_pending()

        asyncio.run(_run())
        kinds = [e.kind for e in observer.events]
        self.assertIn(TraceKind.HEARTBEAT_TRIAGE, kinds)
        self.assertIn(TraceKind.ACTION, kinds)
        self.assertIn(TraceKind.SLEEP_CONSOLIDATION, kinds)


if __name__ == "__main__":
    unittest.main()
