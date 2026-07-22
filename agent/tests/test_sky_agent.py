"""CommanderSkyAgent hook tests: verdicts must translate into pipeline actions."""

from types import SimpleNamespace
from unittest.mock import PropertyMock, patch

import pytest
from livekit.agents import StopResponse

from commander_sky import canned
from commander_sky.safety import InputGuard, OutputGuard
from commander_sky.sky_agent import _DEFLECT_INSTRUCTION, CommanderSkyAgent
from test_safety import _make_guard


def _agent(guard: InputGuard) -> CommanderSkyAgent:
    return CommanderSkyAgent(instructions="test", input_guard=guard, output_guard=OutputGuard())


def _message(text: str) -> SimpleNamespace:
    return SimpleNamespace(text_content=text, content=[text])


class TestOnUserTurnCompleted:
    async def test_fine_passes_message_untouched(self) -> None:
        message = _message("how big is the moon?")
        await _agent(_make_guard("fine")).on_user_turn_completed(None, message)  # type: ignore[arg-type]
        assert message.content == ["how big is the moon?"]

    async def test_guard_latency_logged_without_content(self) -> None:
        """guard_ms must be observable (it's serial reply-path time) — text must not."""
        import structlog

        captured: list[dict] = []

        def sink(logger: object, method: str, event_dict: dict) -> dict:
            captured.append(dict(event_dict))
            return event_dict

        structlog.configure(processors=[sink, structlog.processors.JSONRenderer()])
        secret = "my name is emma and i live on oak street"
        await _agent(_make_guard("fine")).on_user_turn_completed(None, _message(secret))  # type: ignore[arg-type]

        verdicts = [c for c in captured if c.get("event") == "input_guard_verdict"]
        assert verdicts and isinstance(verdicts[0]["guard_ms"], float)
        assert secret not in str(captured)

    async def test_off_topic_keeps_question_and_appends_steering(self) -> None:
        """Deflection must be non-destructive — misclassified space questions
        (e.g. 'satellites') should still be answerable by the LLM."""
        message = _message("what's your favorite video game?")
        await _agent(_make_guard("off_topic")).on_user_turn_completed(None, message)  # type: ignore[arg-type]
        text = message.content[0]
        assert "what's your favorite video game?" in text
        assert _DEFLECT_INSTRUCTION in text

    @pytest.mark.parametrize(
        ("label", "expected_id"),
        [("distress", canned.DISTRESS_DEFAULT), ("sensitive", canned.SENSITIVE_DEFAULT)],
    )
    async def test_canned_says_response_and_stops_llm(self, label: str, expected_id: str) -> None:
        agent = _agent(_make_guard(label))
        said: list[str] = []
        fake_session = SimpleNamespace(say=lambda text, **kw: said.append(text))
        with (
            patch.object(CommanderSkyAgent, "session", new_callable=PropertyMock) as session_prop,
            pytest.raises(StopResponse),
        ):
            session_prop.return_value = fake_session
            await agent.on_user_turn_completed(None, _message("trigger"))  # type: ignore[arg-type]
        assert said == [canned.get_canned(expected_id)]

    async def test_guard_failure_never_reaches_llm(self) -> None:
        """API down => fail closed => canned response, StopResponse raised."""
        agent = _agent(_make_guard(error=RuntimeError("api down")))
        fake_session = SimpleNamespace(say=lambda text, **kw: None)
        with (
            patch.object(CommanderSkyAgent, "session", new_callable=PropertyMock) as session_prop,
            pytest.raises(StopResponse),
        ):
            session_prop.return_value = fake_session
            await agent.on_user_turn_completed(None, _message("anything"))  # type: ignore[arg-type]
