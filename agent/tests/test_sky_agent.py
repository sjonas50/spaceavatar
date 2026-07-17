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

    async def test_off_topic_rewrites_to_deflection(self) -> None:
        message = _message("what's your favorite video game?")
        await _agent(_make_guard("off_topic")).on_user_turn_completed(None, message)  # type: ignore[arg-type]
        assert message.content == [_DEFLECT_INSTRUCTION]

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
