"""Per-session cost tracking.

Accumulates real usage from pipeline metrics events and prices it with the
configured rates. Estimates, not invoices — vendor dashboards are the ground
truth — but close enough to log spend and enforce MAX_SESSION_COST_USD.
Everything emitted is numbers; never conversation content.
"""

import time
from typing import Any

from commander_sky.config import AvatarMode, Settings
from commander_sky.logging import get_logger
from commander_sky.safety import InputGuard

log = get_logger("costs")


class SessionCostTracker:
    """Accumulates usage from ``metrics_collected`` events and prices it."""

    def __init__(self, settings: Settings, guard: InputGuard | None = None):
        self._s = settings
        self._guard = guard
        self._started = time.monotonic()
        self._avatar_active = settings.avatar_mode is AvatarMode.LEMONSLICE
        self.llm_prompt_tokens = 0
        self.llm_cached_tokens = 0
        self.llm_completion_tokens = 0
        self.tts_characters = 0
        self.stt_audio_seconds = 0.0

    def on_metrics(self, event: Any) -> None:
        """metrics_collected handler; dispatches on the metrics type tag."""
        m = getattr(event, "metrics", event)
        kind = getattr(m, "type", "")
        if kind == "llm_metrics":
            self.llm_prompt_tokens += getattr(m, "prompt_tokens", 0) or 0
            self.llm_cached_tokens += getattr(m, "prompt_cached_tokens", 0) or 0
            self.llm_completion_tokens += getattr(m, "completion_tokens", 0) or 0
        elif kind == "tts_metrics":
            self.tts_characters += getattr(m, "characters_count", 0) or 0
        elif kind == "stt_metrics":
            self.stt_audio_seconds += getattr(m, "audio_duration", 0.0) or 0.0

    @property
    def session_minutes(self) -> float:
        return (time.monotonic() - self._started) / 60

    @property
    def guard_calls(self) -> int:
        return self._guard.calls_made if self._guard is not None else 0

    def breakdown(self) -> dict[str, float]:
        """Cost estimate per component (USD), plus the total."""
        s = self._s
        uncached = max(0, self.llm_prompt_tokens - self.llm_cached_tokens)
        llm = (
            uncached * s.cost_llm_in_per_mtok
            + self.llm_cached_tokens * s.cost_llm_cached_in_per_mtok
            + self.llm_completion_tokens * s.cost_llm_out_per_mtok
        ) / 1_000_000
        guard = self.guard_calls * s.cost_guard_per_call
        tts = self.tts_characters / 1_000 * s.cost_tts_per_1k_chars
        stt = self.stt_audio_seconds / 60 * s.cost_stt_per_min
        avatar = self.session_minutes * s.cost_avatar_per_min if self._avatar_active else 0.0
        livekit = self.session_minutes * s.cost_livekit_per_min
        parts = {
            "llm_usd": llm,
            "guard_usd": guard,
            "tts_usd": tts,
            "stt_usd": stt,
            "avatar_usd": avatar,
            "livekit_usd": livekit,
        }
        parts["total_usd"] = sum(parts.values())
        return {k: round(v, 4) for k, v in parts.items()}

    def total(self) -> float:
        return self.breakdown()["total_usd"]

    def log_snapshot(self, event: str = "session_cost") -> None:
        log.info(
            event,
            **self.breakdown(),
            session_minutes=round(self.session_minutes, 2),
            guard_calls=self.guard_calls,
            llm_tokens=self.llm_prompt_tokens + self.llm_completion_tokens,
            tts_chars=self.tts_characters,
        )
