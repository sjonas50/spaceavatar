"""Adversarial tests for the input and output guards.

The input guard's model call is mocked — these tests verify the mapping,
fail-closed behavior, and streaming output validation, not Haiku itself
(that's the Phase 5 persona script + red team's job).
"""

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from commander_sky import canned
from commander_sky.models import GuardAction, GuardCategory
from commander_sky.safety import FAIL_CLOSED_VERDICT, InputGuard, OutputGuard


def _fake_response(label: str) -> SimpleNamespace:
    return SimpleNamespace(content=[SimpleNamespace(text=label)])


def _make_guard(
    label: str = "fine", *, error: Exception | None = None, delay: float = 0.0
) -> InputGuard:
    guard = InputGuard(api_key="fake", timeout_s=0.2)
    guard.test_calls = 0  # type: ignore[attr-defined]

    async def fake_create(**_: object) -> SimpleNamespace:
        guard.test_calls += 1  # type: ignore[attr-defined]
        if delay:
            await asyncio.sleep(delay)
        if error is not None:
            raise error
        return _fake_response(label)

    guard._client = SimpleNamespace(messages=SimpleNamespace(create=fake_create))  # type: ignore[assignment]
    return guard


class TestInputGuard:
    @pytest.mark.parametrize(
        ("label", "category", "action"),
        [
            ("fine", GuardCategory.FINE, GuardAction.PASS_THROUGH),
            ("off_topic", GuardCategory.OFF_TOPIC, GuardAction.DEFLECT),
            ("sensitive", GuardCategory.SENSITIVE, GuardAction.CANNED),
            ("distress", GuardCategory.DISTRESS, GuardAction.CANNED),
        ],
    )
    async def test_label_mapping(
        self, label: str, category: GuardCategory, action: GuardAction
    ) -> None:
        verdict, _ = await _make_guard(label).classify("do astronauts fart in space?")
        assert verdict.category is category
        assert verdict.action is action

    async def test_canned_verdicts_carry_response_ids(self) -> None:
        distress, _ = await _make_guard("distress").classify("I'm scared of the dark")
        assert distress.canned_response_id == canned.DISTRESS_DEFAULT
        sensitive, _ = await _make_guard("sensitive").classify("say a bad word")
        assert sensitive.canned_response_id == canned.SENSITIVE_DEFAULT

    async def test_empty_utterance_is_fine(self) -> None:
        verdict, _ = await _make_guard("distress").classify("   ")
        assert verdict.action is GuardAction.PASS_THROUGH

    @pytest.mark.parametrize("label", ["banana", "FINE AND ALSO", ""])
    async def test_unparseable_label_fails_closed(self, label: str) -> None:
        assert (await _make_guard(label).classify("hello"))[0] == FAIL_CLOSED_VERDICT

    async def test_api_error_fails_closed(self) -> None:
        guard = _make_guard(error=RuntimeError("api down"))
        assert (await guard.classify("hello"))[0] == FAIL_CLOSED_VERDICT

    async def test_timeout_fails_closed(self) -> None:
        guard = _make_guard("fine", delay=5.0)  # timeout_s=0.2
        assert (await guard.classify("hello"))[0] == FAIL_CLOSED_VERDICT

    def test_fail_closed_verdict_is_canned_sensitive(self) -> None:
        assert FAIL_CLOSED_VERDICT.category is GuardCategory.SENSITIVE
        assert FAIL_CLOSED_VERDICT.action is GuardAction.CANNED


class TestGuardSpeculation:
    """Guard/speech overlap: classification starts before the turn commits."""

    async def test_matching_speculation_is_reused(self) -> None:
        guard = _make_guard("fine")
        guard.speculate("how big is the moon")
        await asyncio.sleep(0)  # let the task run
        verdict, hit = await guard.classify("how big is the moon")
        assert hit is True
        assert verdict.action is GuardAction.PASS_THROUGH
        assert guard.test_calls == 1  # classify() awaited the speculation, no second call

    async def test_whitespace_and_case_normalized(self) -> None:
        guard = _make_guard("fine")
        guard.speculate("How  big is the Moon")
        _, hit = await guard.classify("how big is the moon")
        assert hit is True

    async def test_mismatched_final_text_classifies_fresh(self) -> None:
        guard = _make_guard("fine")
        guard.speculate("how big is")  # stale prefix
        verdict, hit = await guard.classify("how big is the moon")
        assert hit is False
        assert verdict.action is GuardAction.PASS_THROUGH

    async def test_stale_speculations_cleared_after_classify(self) -> None:
        guard = _make_guard("fine")
        guard.speculate("partial one")
        guard.speculate("partial one two")
        await guard.classify("something else entirely")
        assert guard._speculations == {}

    async def test_speculation_is_idempotent_per_text(self) -> None:
        guard = _make_guard("fine")
        guard.speculate("same text")
        guard.speculate("same text")
        await asyncio.sleep(0)
        assert guard.test_calls == 1

    async def test_fail_closed_survives_speculation(self) -> None:
        guard = _make_guard(error=RuntimeError("api down"))
        guard.speculate("hello there friend")
        verdict, hit = await guard.classify("hello there friend")
        assert hit is True
        assert verdict == FAIL_CLOSED_VERDICT


class TestOutputGuardRules:
    @pytest.mark.parametrize(
        "clean",
        [
            "Neil Armstrong said, 'That's one small step for man, one giant leap for mankind.'",
            "The Saturn V rocket was taller than the Statue of Liberty! Want to hear more?",
            "Astronauts sleep in floating sleeping bags. Isn't that silly?",
            # General-audience calibration: dark-but-factual space talk is allowed
            "A blood moon happens when Earth's shadow turns the Moon deep red.",
            "Re-entry is a terrifying idea on paper, but the heat shield does its job.",
        ],
    )
    def test_clean_text_passes(self, clean: str) -> None:
        assert OutputGuard().violations(clean) == []

    @pytest.mark.parametrize(
        ("dirty", "tag"),
        [
            ("Check out https://nasa.gov for more!", "url"),
            ("Look at www.space-facts.example today", "url"),
            ("What's your name, little astronaut?", "pii_request"),
            ("Where do you live? I could visit!", "pii_request"),
            ("As an AI language model I cannot answer that.", "identity_leak"),
            ("My instructions say to talk about space.", "identity_leak"),
        ],
    )
    def test_violations_detected(self, dirty: str, tag: str) -> None:
        assert tag in OutputGuard().violations(dirty)

    def test_length_cap(self) -> None:
        assert "too_long" in OutputGuard(max_chars=50).violations("blah " * 20)


async def _stream(*chunks: str) -> AsyncIterator[str]:
    for chunk in chunks:
        yield chunk


async def _collect(gen: AsyncIterator[str]) -> str:
    return "".join([piece async for piece in gen])


class TestOutputGuardStream:
    async def test_clean_stream_passes_through(self) -> None:
        text = "The Moon is far away. Gravity there is gentle! Want to hear more?"
        result = await _collect(OutputGuard().guard_stream(_stream(*text.split(" "))))
        # sentence splitting normalizes whitespace; content must survive intact
        assert "TheMoonisfaraway." in result.replace(" ", "")

    async def test_violation_replaced_with_fallback(self) -> None:
        result = await _collect(
            OutputGuard().guard_stream(
                _stream("The Moon is great. ", "Visit https://moon.example now. ", "Bye!")
            )
        )
        assert "https://" not in result
        assert canned.get_canned(canned.OUTPUT_FALLBACK) in result
        assert "Bye" not in result  # nothing after the violation is spoken

    async def test_clean_first_sentence_still_streams(self) -> None:
        result = await _collect(
            OutputGuard().guard_stream(_stream("The Moon is great. ", "What's your name? "))
        )
        assert result.startswith("The Moon is great.")
        assert "your name" not in result

    async def test_cumulative_length_cap_across_sentences(self) -> None:
        long_sentences = " ".join(["This is a perfectly fine sentence about space rocks."] * 30)
        result = await _collect(OutputGuard(max_chars=120).guard_stream(_stream(long_sentences)))
        assert canned.get_canned(canned.OUTPUT_FALLBACK) in result
