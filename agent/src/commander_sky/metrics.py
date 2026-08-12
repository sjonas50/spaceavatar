"""Latency observability for the voice pipeline.

COPPA constraint: everything emitted here is numbers and enum-like labels.
No transcripts, no utterances, no child-identifying data — ever.
"""

import statistics
from typing import Any

from commander_sky.logging import get_logger

log = get_logger("pipeline.metrics")

# Attributes we allow into log lines. Anything else on a metrics event
# (e.g. transcript text) is dropped by construction.
_NUMERIC_FIELDS = (
    "ttft",
    "ttfb",
    "duration",
    "audio_duration",
    "end_of_utterance_delay",
    "transcription_delay",
    "tokens_per_second",
    "input_tokens",
    "output_tokens",
    "characters_count",
)


def log_pipeline_metrics(event: Any) -> None:
    """Log the numeric fields of a livekit-agents metrics event, content-free.

    Args:
        event: A ``MetricsCollectedEvent`` (or any object with a ``metrics`` attr).
    """
    metrics = getattr(event, "metrics", event)
    fields: dict[str, float] = {}
    for name in _NUMERIC_FIELDS:
        value = getattr(metrics, name, None)
        if isinstance(value, int | float):
            fields[name] = round(float(value), 4)
    log.info("pipeline_metrics", stage=type(metrics).__name__, **fields)


class TurnLatencyTracker:
    """Per-turn serial reply latency: eou_delay + guard + LLM TTFT + TTS TTFB.

    Correlates the framework's EOU/LLM/TTS metric events by ``speech_id`` and
    emits one ``turn_latency`` line per completed turn plus a p50/p95
    ``turn_latency_summary`` at session end. The total is the serial
    approximation of utterance-end → first synthesized audio; avatar transport
    adds a roughly constant tail on top.

    Guard time has no speech_id — it is reported via :meth:`on_guard_ms` from
    the agent's turn hook and attached to the next turn that completes.
    """

    def __init__(self) -> None:
        self._turns: dict[str, dict[str, float]] = {}
        self._pending_guard_ms: float | None = None
        self.totals_ms: list[float] = []

    def on_guard_ms(self, guard_ms: float) -> None:
        """Record the input-guard await time for the turn now being answered."""
        self._pending_guard_ms = guard_ms

    def on_metrics(self, event: Any) -> None:
        """Fold one metrics event into its turn; emit when the turn is complete."""
        metrics = getattr(event, "metrics", event)
        speech_id = getattr(metrics, "speech_id", None)
        if not speech_id:
            return
        stage = type(metrics).__name__
        turn = self._turns.setdefault(speech_id, {})
        if stage == "EOUMetrics":
            turn["eou_ms"] = float(metrics.end_of_utterance_delay) * 1000
        elif stage == "LLMMetrics" and "ttft_ms" not in turn:
            turn["ttft_ms"] = float(metrics.ttft) * 1000
        elif stage == "TTSMetrics" and "ttfb_ms" not in turn:
            turn["ttfb_ms"] = float(metrics.ttfb) * 1000
        # Complete once utterance-end and first audio are both known; the LLM
        # stage is optional (canned/say responses never touch the LLM).
        if "eou_ms" in turn and "ttfb_ms" in turn:
            self._complete(speech_id, turn)

    def _complete(self, speech_id: str, turn: dict[str, float]) -> None:
        del self._turns[speech_id]
        if self._pending_guard_ms is not None:
            turn["guard_ms"] = self._pending_guard_ms
            self._pending_guard_ms = None
        total_ms = round(sum(turn.values()), 1)
        self.totals_ms.append(total_ms)
        log.info(
            "turn_latency",
            total_ms=total_ms,
            **{name: round(value, 1) for name, value in turn.items()},
        )

    def summary(self) -> dict[str, float] | None:
        """p50/p95 across the session's completed turns, or None if there were none."""
        if not self.totals_ms:
            return None
        if len(self.totals_ms) == 1:
            p50 = p95 = self.totals_ms[0]
        else:
            quantiles = statistics.quantiles(self.totals_ms, n=20, method="inclusive")
            p50, p95 = quantiles[9], quantiles[18]
        return {"turns": len(self.totals_ms), "p50_ms": round(p50, 1), "p95_ms": round(p95, 1)}

    def log_summary(self) -> None:
        """Emit the session-end summary line (no-op for turnless sessions)."""
        if stats := self.summary():
            log.info("turn_latency_summary", **stats)
