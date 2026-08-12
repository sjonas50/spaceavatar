"""Per-turn latency aggregation: correlation, completion, summary stats."""

from dataclasses import dataclass

from commander_sky.metrics import TurnLatencyTracker


@dataclass
class EOUMetrics:
    speech_id: str
    end_of_utterance_delay: float


@dataclass
class LLMMetrics:
    speech_id: str
    ttft: float


@dataclass
class TTSMetrics:
    speech_id: str
    ttfb: float


def _drive_turn(
    tracker: TurnLatencyTracker,
    speech_id: str,
    *,
    eou_s: float = 0.6,
    guard_ms: float = 120.0,
    ttft_s: float = 0.9,
    ttfb_s: float = 0.1,
) -> None:
    tracker.on_guard_ms(guard_ms)
    tracker.on_metrics(EOUMetrics(speech_id, eou_s))
    tracker.on_metrics(LLMMetrics(speech_id, ttft_s))
    tracker.on_metrics(TTSMetrics(speech_id, ttfb_s))


class TestTurnCompletion:
    def test_complete_turn_totals_components(self) -> None:
        tracker = TurnLatencyTracker()
        _drive_turn(tracker, "s1", eou_s=0.5, guard_ms=100.0, ttft_s=1.0, ttfb_s=0.2)
        assert tracker.totals_ms == [1800.0]

    def test_out_of_order_events_still_complete(self) -> None:
        """Preemptive generation delivers LLM/TTS metrics before EOU."""
        tracker = TurnLatencyTracker()
        tracker.on_guard_ms(50.0)
        tracker.on_metrics(LLMMetrics("s1", 0.8))
        tracker.on_metrics(TTSMetrics("s1", 0.1))
        assert tracker.totals_ms == []  # incomplete without EOU
        tracker.on_metrics(EOUMetrics("s1", 0.5))
        assert len(tracker.totals_ms) == 1

    def test_turn_without_llm_still_completes(self) -> None:
        """Canned responses (session.say) have no LLM stage."""
        tracker = TurnLatencyTracker()
        tracker.on_metrics(EOUMetrics("s1", 0.5))
        tracker.on_metrics(TTSMetrics("s1", 0.1))
        assert tracker.totals_ms == [600.0]

    def test_guard_ms_consumed_once(self) -> None:
        """A turn's guard time must not leak into the next turn."""
        tracker = TurnLatencyTracker()
        _drive_turn(tracker, "s1", eou_s=0.5, guard_ms=1000.0, ttft_s=0.5, ttfb_s=0.0)
        # next turn: no guard call (e.g. canned path raised StopResponse earlier)
        tracker.on_metrics(EOUMetrics("s2", 0.5))
        tracker.on_metrics(TTSMetrics("s2", 0.1))
        assert tracker.totals_ms == [2000.0, 600.0]

    def test_events_without_speech_id_ignored(self) -> None:
        @dataclass
        class VADMetrics:
            idle_time: float

        tracker = TurnLatencyTracker()
        tracker.on_metrics(VADMetrics(1.0))
        assert tracker.totals_ms == []


class TestSummary:
    def test_summary_percentiles(self) -> None:
        tracker = TurnLatencyTracker()
        for i, total in enumerate([1.0, 2.0, 3.0, 4.0]):
            _drive_turn(tracker, f"s{i}", eou_s=total, guard_ms=0.0, ttft_s=0.0, ttfb_s=0.0)
        summary = tracker.summary()
        assert summary is not None
        assert summary["turns"] == 4
        assert 2000.0 <= summary["p50_ms"] <= 3000.0
        assert summary["p95_ms"] >= 3500.0

    def test_summary_none_without_turns(self) -> None:
        assert TurnLatencyTracker().summary() is None
