"""The Commander Sky agent: persona LLM wrapped in the safety guards."""

import time
from collections.abc import AsyncIterable
from typing import Any, Literal

from livekit.agents import Agent, ModelSettings, StopResponse, function_tool, llm

from commander_sky import skytools
from commander_sky.canned import get_canned
from commander_sky.logging import get_logger
from commander_sky.models import GuardAction
from commander_sky.safety import InputGuard, OutputGuard

GalleryImage = Literal[
    "saturn",
    "jupiter",
    "mars",
    "moon",
    "earthrise",
    "apollo11_flag",
    "apollo11_crew",
    "saturn_v",
    "iss",
    "milky_way",
]

log = get_logger("sky_agent")

_DEFLECT_INSTRUCTION = (
    "[safety guard] The user said something off-topic (not about space). Do not answer "
    "it directly. Redirect with charm: acknowledge briefly, then offer a space fact or "
    "question, per your rules."
)


def enable_guard_speculation(session: Any, agent: "CommanderSkyAgent") -> None:
    """Overlap guard classification with the user's speech.

    On every final transcript chunk we speculatively classify the
    accumulated utterance; by end-of-turn the verdict is usually ready and
    on_user_turn_completed's await is near-instant. Safety is unchanged —
    the persona LLM still waits for the verdict.
    """
    buffer: list[str] = []

    def _on_transcribed(ev: Any) -> None:
        if getattr(ev, "is_final", False) and ev.transcript.strip():
            buffer.append(ev.transcript)
            agent._input_guard.speculate(" ".join(buffer))

    def _on_item_added(ev: Any) -> None:
        if getattr(getattr(ev, "item", None), "role", None) == "user":
            buffer.clear()

    session.on("user_input_transcribed", _on_transcribed)
    session.on("conversation_item_added", _on_item_added)


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
        verdict, speculative_hit = await self._input_guard.classify(text)
        guard_ms = round((time.perf_counter() - started) * 1000, 1)
        # tags + timing only, never text — this is serial time on the reply path
        log.info(
            "input_guard_verdict",
            category=verdict.category.value,
            guard_ms=guard_ms,
            speculative_hit=speculative_hit,
        )

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

    # --- Interactive tools -------------------------------------------------

    @function_tool
    async def show_picture(self, image_id: GalleryImage) -> str:
        """Show a picture on the visitor's screen while you talk about it.

        Use when you START talking about something in the gallery — the planet,
        mission, or object at hand. Show at most one picture per topic; never
        call repeatedly for the same subject.
        """
        return await skytools.show_image(image_id)

    @function_tool
    async def get_space_station_location(self) -> str:
        """Get the International Space Station's live position right now.

        Use when the visitor asks where the ISS is, or to make the station feel
        real while discussing it.
        """
        return await skytools.fetch_iss_position()

    @function_tool
    async def get_next_rocket_launch(self) -> str:
        """Get the next real scheduled rocket launch (live data).

        Use when the visitor asks about upcoming launches or what's happening
        in spaceflight right now.
        """
        return await skytools.fetch_next_launch()
