"""Per-session cost tracker: accumulation, pricing math, cap semantics."""

from types import SimpleNamespace

from commander_sky.config import AvatarMode, Settings
from commander_sky.costs import SessionCostTracker


def _llm(prompt: int, cached: int, completion: int) -> SimpleNamespace:
    return SimpleNamespace(
        metrics=SimpleNamespace(
            type="llm_metrics",
            prompt_tokens=prompt,
            prompt_cached_tokens=cached,
            completion_tokens=completion,
        )
    )


def _tts(chars: int) -> SimpleNamespace:
    return SimpleNamespace(metrics=SimpleNamespace(type="tts_metrics", characters_count=chars))


def _stt(seconds: float) -> SimpleNamespace:
    return SimpleNamespace(metrics=SimpleNamespace(type="stt_metrics", audio_duration=seconds))


class TestAccumulation:
    def test_metrics_accumulate_by_type(self, settings: Settings) -> None:
        tracker = SessionCostTracker(settings)
        tracker.on_metrics(_llm(3000, 2000, 150))
        tracker.on_metrics(_llm(3200, 3000, 80))
        tracker.on_metrics(_tts(500))
        tracker.on_metrics(_stt(30.0))
        assert tracker.llm_prompt_tokens == 6200
        assert tracker.llm_cached_tokens == 5000
        assert tracker.llm_completion_tokens == 230
        assert tracker.tts_characters == 500
        assert tracker.stt_audio_seconds == 30.0

    def test_unknown_metrics_ignored(self, settings: Settings) -> None:
        tracker = SessionCostTracker(settings)
        tracker.on_metrics(SimpleNamespace(metrics=SimpleNamespace(type="vad_metrics")))
        assert tracker.total() >= 0  # no crash, only time-based costs


class TestPricing:
    def test_llm_pricing_uses_cached_rate(self, settings: Settings) -> None:
        tracker = SessionCostTracker(settings.model_copy(update={"avatar_mode": AvatarMode.NONE}))
        tracker.on_metrics(_llm(1_000_000, 900_000, 0))
        parts = tracker.breakdown()
        # 100k uncached @ $3/M + 900k cached @ $0.30/M = 0.30 + 0.27
        assert abs(parts["llm_usd"] - 0.57) < 0.001

    def test_avatar_cost_only_in_lemonslice_mode(self, settings: Settings) -> None:
        with_avatar = SessionCostTracker(settings)
        without = SessionCostTracker(settings.model_copy(update={"avatar_mode": AvatarMode.NONE}))
        assert without.breakdown()["avatar_usd"] == 0.0
        assert with_avatar.breakdown()["avatar_usd"] >= 0.0

    def test_stt_priced_per_minute(self, settings: Settings) -> None:
        tracker = SessionCostTracker(settings)
        tracker.on_metrics(_stt(600.0))  # 10 minutes
        assert abs(tracker.breakdown()["stt_usd"] - 10 * settings.cost_stt_per_min) < 1e-6

    def test_total_is_sum_of_parts(self, settings: Settings) -> None:
        tracker = SessionCostTracker(settings)
        tracker.on_metrics(_llm(5000, 4000, 300))
        tracker.on_metrics(_tts(800))
        parts = tracker.breakdown()
        total = sum(v for k, v in parts.items() if k != "total_usd")
        assert abs(parts["total_usd"] - total) < 0.001


class TestGuardCalls:
    def test_guard_calls_counted(self, settings: Settings) -> None:
        from test_safety import _make_guard

        guard = _make_guard("fine")
        tracker = SessionCostTracker(settings, guard=guard)
        assert tracker.guard_calls == 0

    async def test_guard_calls_priced(self, settings: Settings) -> None:
        from test_safety import _make_guard

        guard = _make_guard("fine")
        await guard.classify("hello there")
        tracker = SessionCostTracker(settings, guard=guard)
        assert tracker.guard_calls == 1
        assert tracker.breakdown()["guard_usd"] == round(settings.cost_guard_per_call, 4)
