"""Pydantic schemas for data crossing component boundaries.

These are the contracts between the safety guards, the pipeline, and
observability. Keep them small and explicit — they are also the test surface.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class GuardCategory(StrEnum):
    """Input-guard classification of a child's utterance."""

    FINE = "fine"
    OFF_TOPIC = "off_topic"
    SENSITIVE = "sensitive"
    DISTRESS = "distress"


class GuardAction(StrEnum):
    """What the pipeline does with an utterance after classification."""

    PASS_THROUGH = "pass_through"  # goes to the persona LLM unchanged
    DEFLECT = "deflect"  # LLM told to redirect warmly to space topics
    CANNED = "canned"  # fixed response only — never the freeform LLM


# Safety invariant (BUILD_PLAN.md §Phase 2): sensitive and distress inputs
# must never reach the freeform LLM.
_REQUIRED_ACTION: dict[GuardCategory, GuardAction] = {
    GuardCategory.SENSITIVE: GuardAction.CANNED,
    GuardCategory.DISTRESS: GuardAction.CANNED,
}


class GuardVerdict(BaseModel):
    """Result of classifying one utterance, with the action the pipeline must take."""

    category: GuardCategory
    action: GuardAction
    canned_response_id: str | None = None

    @model_validator(mode="after")
    def _enforce_safety_invariants(self) -> "GuardVerdict":
        required = _REQUIRED_ACTION.get(self.category)
        if required is not None and self.action != required:
            raise ValueError(
                f"{self.category} utterances require action={required}, got {self.action}"
            )
        if self.action is GuardAction.CANNED and not self.canned_response_id:
            raise ValueError("action=canned requires a canned_response_id")
        return self


class TurnMetrics(BaseModel):
    """Per-stage latency for one conversation turn. Metrics only — never content."""

    stt_final_ms: float = Field(ge=0)
    guard_ms: float = Field(ge=0)
    llm_ttft_ms: float = Field(ge=0)
    tts_first_chunk_ms: float = Field(ge=0)
    avatar_first_frame_ms: float | None = Field(default=None, ge=0)
    total_ms: float = Field(ge=0, description="utterance end to first audible response")
    guard_category: GuardCategory = GuardCategory.FINE


class SessionLimits(BaseModel):
    """Hard per-session caps (cost control + kid wellbeing)."""

    max_minutes: int = Field(ge=1, le=120)
    max_cost_usd: float = Field(gt=0)
