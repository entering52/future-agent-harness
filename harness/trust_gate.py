"""Elastic Trust-Tiered Sandbox: dynamic autonomy that scales with collaboration trust."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionRisk(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOCAL_SANDBOX = "LOCAL_SANDBOX"
    EXTERNAL_MUTATION = "EXTERNAL_MUTATION"
    IRREVERSIBLE = "IRREVERSIBLE"


@dataclass(slots=True)
class GateDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str
    trust_score: float


class ElasticTrustGate:
    """Balances autonomous exploration with strict guardrails for irreversible actions."""

    def __init__(self, initial_trust: float = 0.35, promotion_threshold: float = 0.70) -> None:
        self._trust_scores: dict[str, float] = {}
        self.initial_trust = initial_trust
        self.promotion_threshold = promotion_threshold

    def get_trust(self, tool_name: str) -> float:
        return self._trust_scores.get(tool_name, self.initial_trust)

    def record_outcome(self, tool_name: str, *, success: bool) -> float:
        current = self.get_trust(tool_name)
        updated = min(1.0, current + 0.12) if success else max(0.05, current - 0.25)
        self._trust_scores[tool_name] = round(updated, 3)
        return self._trust_scores[tool_name]

    def evaluate(self, tool_name: str, risk: ActionRisk) -> GateDecision:
        trust = self.get_trust(tool_name)

        if risk == ActionRisk.READ_ONLY:
            return GateDecision(
                allowed=True,
                requires_confirmation=False,
                reason="Read-only inspection is always permitted.",
                trust_score=trust,
            )

        if risk == ActionRisk.LOCAL_SANDBOX:
            return GateDecision(
                allowed=True,
                requires_confirmation=False,
                reason="Local sandbox exploration is autonomous by default.",
                trust_score=trust,
            )

        if risk == ActionRisk.IRREVERSIBLE:
            return GateDecision(
                allowed=False,
                requires_confirmation=True,
                reason="Irreversible actions always require explicit human confirmation.",
                trust_score=trust,
            )

        # EXTERNAL_MUTATION scales elastically with earned trust
        if trust >= self.promotion_threshold:
            return GateDecision(
                allowed=True,
                requires_confirmation=False,
                reason=f"Auto-approved: earned trust ({trust:.2f}) meets threshold ({self.promotion_threshold:.2f}).",
                trust_score=trust,
            )

        return GateDecision(
            allowed=False,
            requires_confirmation=True,
            reason=f"Confirmation needed: trust ({trust:.2f}) is below autonomous threshold ({self.promotion_threshold:.2f}).",
            trust_score=trust,
        )
