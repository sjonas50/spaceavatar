"""The Commander Sky agent: persona LLM wrapped in the safety guards."""

import time
from collections.abc import AsyncIterable
from typing import Any

from livekit.agents import Agent, ModelSettings, StopResponse, llm

from commander_sky.canned import get_canned
from commander_sky.logging import get_logger
from commander_sky.models import GuardAction
from commander_sky.safety import InputGuard, OutputGuard

log = get_logger("sky_agent")

_DEFLECT_INSTRUCTION = (
    "[safety guard] The user said something off-topic (not about space). Do not answer "
    "it directly. Redirect with charm: acknowledge briefly, then offer a space fact or "
    "question, per your rules."
)


class CommanderSkyAgent(Agent):
    """Agent with the input guard before the LLM and the output guard before TTS."""

    def __init__(self, *, instructions: str, input_guard: InputGuard, output_guard: OutputGuard):
        super().__init__(instructions=instructions)
        self._input_guard = input_guard
        self._output_guard = output_guard

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        """Classify the utterance before it can reach the persona LLM."""
        text = new_message.text_content or ""
        started = time.perf_counter()
        verdict = await self._input_guard.classify(text)
        guard_ms = round((time.perf_counter() - started) * 1000, 1)
        # tags + timing only, never text — this is serial time on the reply path
        log.info("input_guard_verdict", category=verdict.category.value, guard_ms=guard_ms)

        if verdict.action is GuardAction.CANNED:
            assert verdict.canned_response_id is not None  # enforced by GuardVerdict
            self.session.say(get_canned(verdict.canned_response_id))
            raise StopResponse()  # the freeform LLM never sees this turn

        if verdict.action is GuardAction.DEFLECT:
            # Replace the raw utterance with a bounded instruction; the child's
            # exact words don't need to reach the LLM for a redirect.
            new_message.content = [_DEFLECT_INSTRUCTION]

    async def tts_node(self, text: AsyncIterable[str], model_settings: ModelSettings) -> Any:
        """Every generated sentence passes the output guard before synthesis."""
        return Agent.default.tts_node(self, self._output_guard.guard_stream(text), model_settings)
