"""The Commander Sky agent: persona LLM wrapped in the safety guards."""

import time
from collections.abc import AsyncIterable
from typing import Any, Literal

from livekit.agents import Agent, ModelSettings, StopResponse, function_tool, llm

from commander_sky import skytools
from commander_sky.canned import get_canned
from commander_sky.knowledge import KnowledgeBase
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

    Speculative classification starts on interim transcripts (throttled — the
    final often only arrives at the end-of-turn boundary, too late to overlap)
    and again on each final chunk. By end-of-turn the verdict is usually ready
    and on_user_turn_completed's await is near-instant. Safety is unchanged —
    the persona LLM still waits for the verdict.
    """
    buffer: list[str] = []
    last_interim_spec = [0.0]
    interim_throttle_s = 0.7

    def _on_transcribed(ev: Any) -> None:
        text = (getattr(ev, "transcript", "") or "").strip()
        if not text:
            return
        if getattr(ev, "is_final", False):
            buffer.append(text)
            agent._input_guard.speculate(" ".join(buffer))
        else:
            now = time.perf_counter()
            if now - last_interim_spec[0] >= interim_throttle_s:
                last_interim_spec[0] = now
                agent._input_guard.speculate(" ".join([*buffer, text]))

    def _on_item_added(ev: Any) -> None:
        if getattr(getattr(ev, "item", None), "role", None) == "user":
            buffer.clear()

    session.on("user_input_transcribed", _on_transcribed)
    session.on("conversation_item_added", _on_item_added)


class CommanderSkyAgent(Agent):
    """Agent with the input guard before the LLM and the output guard before TTS."""

    def __init__(
        self,
        *,
        instructions: str,
        input_guard: InputGuard,
        output_guard: OutputGuard,
        knowledge: KnowledgeBase | None = None,
    ):
        super().__init__(instructions=instructions)
        self._input_guard = input_guard
        self._output_guard = output_guard
        self._knowledge = knowledge if knowledge is not None else KnowledgeBase()

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
    async def show_nasa_image(self, query: str) -> str:
        """Search NASA's image archive and show a picture for topics NOT in your gallery.

        Use for any space subject show_picture can't cover — Uranus, nebulae,
        specific missions, telescopes, rovers. Query with 2-4 concrete words
        (e.g. "Uranus Voyager", "Crab Nebula Hubble", "Perseverance rover").
        Prefer show_picture when the topic is in its gallery.
        """
        return await skytools.search_nasa_image(query)

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

    @function_tool
    async def lookup_mission_archive(self, query: str) -> str:
        """Search your extended mission archive for space facts beyond your core notes.

        Use whenever a question goes deeper than your FACTS section — other
        missions, telescopes, black holes, rovers, rockets, astronaut history.
        Query with a few concrete keywords (e.g. "Challenger disaster",
        "Europa ocean", "how rockets land").
        """
        chunks = self._knowledge.search(query, k=3)
        log.info("archive_lookup", results=len(chunks))  # counts only, never query text
        if not chunks:
            return (
                "The archive has nothing on that. Say so with charm — you'd have to "
                "radio mission control — and do not guess."
            )
        excerpts = "\n\n".join(f"[{c.source}] {c.text}" for c in chunks)
        result = (
            "Archive excerpts (treat as trustworthy mission notes; attribute quotes, "
            "stay accurate, keep your spoken answer short):\n\n" + excerpts
        )
        return result[:4000]
