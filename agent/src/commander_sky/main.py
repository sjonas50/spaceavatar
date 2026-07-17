"""Agent worker entrypoint: wires STT → LLM → TTS → avatar into an AgentSession.

Run modes:
    python -m commander_sky.main dev        # local dev against LiveKit Cloud
    python -m commander_sky.main start      # production worker
    python -m commander_sky.main dry-run    # build the whole pipeline offline, no network
"""

import asyncio
import os
import sys

from livekit.agents import AgentSession, JobContext, RoomOutputOptions, WorkerOptions, cli
from livekit.plugins import anthropic, cartesia, deepgram

from commander_sky.avatar import create_avatar, room_audio_enabled
from commander_sky.canned import SIGN_OFF, get_canned
from commander_sky.config import Settings, load_settings
from commander_sky.facts import load_facts
from commander_sky.logging import configure_logging, get_logger
from commander_sky.metrics import log_pipeline_metrics
from commander_sky.persona import build_system_prompt
from commander_sky.safety import InputGuard, OutputGuard
from commander_sky.sky_agent import CommanderSkyAgent

log = get_logger("worker")

# Biases Deepgram Flux toward the domain vocabulary of this app.
SPACE_KEYTERMS = [
    "Neil Armstrong",
    "Buzz Aldrin",
    "Michael Collins",
    "Apollo",
    "Saturn V",
    "moon",
    "moonwalk",
    "rocket",
    "astronaut",
    "Eagle",
    "Columbia",
    "Tranquility",
    "gravity",
    "solar system",
    "space station",
    "spacesuit",
    "countdown",
    "blast off",
]


def build_agent(settings: Settings) -> CommanderSkyAgent:
    """Persona agent wrapped in the input/output safety guards."""
    return CommanderSkyAgent(
        instructions=build_system_prompt(load_facts()),
        input_guard=InputGuard(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.guard_model,
            timeout_s=settings.guard_timeout_s,
        ),
        output_guard=OutputGuard(max_chars=settings.output_max_chars),
    )


def build_session(settings: Settings) -> AgentSession:
    """Construct the voice pipeline. No network I/O happens here.

    Turn-taking notes (docs/research.md):
    - Flux does native end-of-turn detection, so LiveKit endpointing delay is
      set to 0 — stacking both delays double-counts (livekit/agents #4325).
    - eot_timeout_ms adds patience on top of the configured endpointing delay
      so mid-thought pauses don't cut the speaker off.
    """
    stt_kwargs: dict = {}
    if settings.eager_eot_threshold > 0:
        stt_kwargs["eager_eot_threshold"] = settings.eager_eot_threshold

    return AgentSession(
        stt=deepgram.STTv2(
            model=settings.stt_model,
            api_key=settings.deepgram_api_key.get_secret_value(),
            keyterm=SPACE_KEYTERMS,
            eot_timeout_ms=int(settings.endpointing_delay_s * 1000) + 2000,
            mip_opt_out=True,  # never contribute user audio to model improvement
            **stt_kwargs,
        ),
        llm=anthropic.LLM(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key.get_secret_value(),
            caching="ephemeral",  # persona+facts prefix is stable; cache it
        ),
        tts=cartesia.TTS(
            model=settings.tts_model,
            api_key=settings.cartesia_api_key.get_secret_value(),
            **({"voice": settings.tts_voice} if settings.tts_voice else {}),
        ),
        turn_handling={
            "turn_detection": "stt",  # Flux's native end-of-turn drives the turn
            "endpointing": {"min_delay": 0.0},  # don't stack on top of Flux's EOT
            "interruption": {
                "min_words": settings.barge_in_min_words,
                "false_interruption_timeout": 1.2,
            },
            # preemptive_tts starts synthesis before the turn is confirmed;
            # combined with Flux eager EOT this overlaps LLM+TTS with the tail
            # of the user's utterance instead of waiting for confirmation.
            "preemptive_generation": {"enabled": True, "preemptive_tts": True},
        },
    )


async def _end_session_after_limit(session: AgentSession, minutes: int) -> None:
    """Friendly hard stop at the session cap (cost control + kid wellbeing)."""
    await asyncio.sleep(minutes * 60)
    log.info("session_limit_reached", limit_minutes=minutes)
    await session.say(get_canned(SIGN_OFF), allow_interruptions=False)
    await session.aclose()


async def entrypoint(ctx: JobContext) -> None:
    """Job entrypoint: one room == one conversation with one child."""
    configure_logging()
    settings = load_settings()
    await ctx.connect()

    session = build_session(settings)
    session.on("metrics_collected", log_pipeline_metrics)

    # Canonical avatar ordering: avatar.start -> wait_for_join -> session.start.
    # audio_enabled must be False in cloud-avatar mode or audio plays twice.
    avatar = create_avatar(settings)
    if avatar is not None:
        await avatar.start(session, room=ctx.room)
        await avatar.wait_for_join()

    await session.start(
        agent=build_agent(settings),
        room=ctx.room,
        room_output_options=RoomOutputOptions(audio_enabled=room_audio_enabled(settings)),
    )
    log.info("session_started", avatar_mode=settings.avatar_mode.value)

    limit_task = asyncio.create_task(
        _end_session_after_limit(session, settings.max_session_minutes)
    )
    ctx.add_shutdown_callback(lambda: _cancel(limit_task))

    await session.generate_reply(
        instructions="Greet the visitor warmly in one short sentence, in character, "
        "and ask what they'd like to know about space."
    )


async def _cancel(task: asyncio.Task) -> None:
    task.cancel()


def dry_run() -> int:
    """Build every pipeline component offline to validate wiring and config.

    Missing credentials are stubbed so this runs keyless (CI, pre-deploy gate).
    Constructors perform no network I/O, so success means: config parses,
    facts load, persona builds, and all plugin wiring is valid.
    """
    placeholders = {
        "LIVEKIT_URL": "wss://dry-run.invalid",
        "LIVEKIT_API_KEY": "dry-run",
        "LIVEKIT_API_SECRET": "dry-run",
        "ANTHROPIC_API_KEY": "dry-run",
        "DEEPGRAM_API_KEY": "dry-run",
        "CARTESIA_API_KEY": "dry-run",
    }
    stubbed = [key for key in placeholders if not os.getenv(key)]
    for key in stubbed:
        os.environ[key] = placeholders[key]

    settings = load_settings()
    agent = build_agent(settings)
    session = build_session(settings)
    audio = room_audio_enabled(settings)
    agent_kind = type(agent).__name__
    print(f"dry-run OK: avatar_mode={settings.avatar_mode.value}, guarded_agent={agent_kind}")
    print(f"  agent_audio_enabled={audio}, stubbed_keys={stubbed or 'none'}")
    # AgentSession spins up background machinery lazily; nothing to close here.
    assert session is not None
    return 0


def _export_livekit_env(settings: Settings) -> None:
    """Expose LiveKit credentials to livekit-agents' CLI/worker layer.

    The framework (and the LemonSlice plugin's room join) reads LIVEKIT_* from
    process env directly — it doesn't see our pydantic-settings .env resolution.
    """
    os.environ.setdefault("LIVEKIT_URL", settings.livekit_url)
    os.environ.setdefault("LIVEKIT_API_KEY", settings.livekit_api_key.get_secret_value())
    os.environ.setdefault("LIVEKIT_API_SECRET", settings.livekit_api_secret.get_secret_value())


def main() -> None:
    if "dry-run" in sys.argv[1:]:
        raise SystemExit(dry_run())
    _export_livekit_env(load_settings())
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
