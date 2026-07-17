"""Schema validation tests — especially the safety invariants on GuardVerdict."""

import pytest
from pydantic import ValidationError

from commander_sky.models import (
    GuardAction,
    GuardCategory,
    GuardVerdict,
    SessionLimits,
    TurnMetrics,
)


class TestGuardVerdict:
    @pytest.mark.parametrize(
        ("category", "action"),
        [
            (GuardCategory.FINE, GuardAction.PASS_THROUGH),
            (GuardCategory.OFF_TOPIC, GuardAction.DEFLECT),
            (GuardCategory.OFF_TOPIC, GuardAction.PASS_THROUGH),
        ],
    )
    def test_allowed_combinations(self, category: GuardCategory, action: GuardAction) -> None:
        verdict = GuardVerdict(category=category, action=action)
        assert verdict.category is category

    @pytest.mark.parametrize("category", [GuardCategory.SENSITIVE, GuardCategory.DISTRESS])
    @pytest.mark.parametrize("action", [GuardAction.PASS_THROUGH, GuardAction.DEFLECT])
    def test_sensitive_and_distress_must_be_canned(
        self, category: GuardCategory, action: GuardAction
    ) -> None:
        """The launch-blocking invariant: these categories never reach the freeform LLM."""
        with pytest.raises(ValidationError, match="require action"):
            GuardVerdict(category=category, action=action)

    @pytest.mark.parametrize("category", [GuardCategory.SENSITIVE, GuardCategory.DISTRESS])
    def test_canned_requires_response_id(self, category: GuardCategory) -> None:
        with pytest.raises(ValidationError, match="canned_response_id"):
            GuardVerdict(category=category, action=GuardAction.CANNED)

    def test_valid_canned_verdict(self) -> None:
        verdict = GuardVerdict(
            category=GuardCategory.DISTRESS,
            action=GuardAction.CANNED,
            canned_response_id="distress_default",
        )
        assert verdict.canned_response_id == "distress_default"


class TestTurnMetrics:
    def test_valid_metrics(self) -> None:
        metrics = TurnMetrics(
            stt_final_ms=120, guard_ms=150, llm_ttft_ms=240, tts_first_chunk_ms=90, total_ms=800
        )
        assert metrics.avatar_first_frame_ms is None
        assert metrics.guard_category is GuardCategory.FINE

    @pytest.mark.parametrize(
        "field", ["stt_final_ms", "guard_ms", "llm_ttft_ms", "tts_first_chunk_ms", "total_ms"]
    )
    def test_negative_latency_rejected(self, field: str) -> None:
        values = {
            "stt_final_ms": 1,
            "guard_ms": 1,
            "llm_ttft_ms": 1,
            "tts_first_chunk_ms": 1,
            "total_ms": 1,
        }
        values[field] = -1
        with pytest.raises(ValidationError):
            TurnMetrics(**values)


class TestSessionLimits:
    @pytest.mark.parametrize(("minutes", "cost"), [(0, 5.0), (121, 5.0), (15, 0.0), (15, -1.0)])
    def test_out_of_range_rejected(self, minutes: int, cost: float) -> None:
        with pytest.raises(ValidationError):
            SessionLimits(max_minutes=minutes, max_cost_usd=cost)

    def test_defaults_from_settings_are_valid(self) -> None:
        limits = SessionLimits(max_minutes=15, max_cost_usd=5.0)
        assert limits.max_minutes == 15
