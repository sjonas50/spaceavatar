"""Typed environment configuration for the agent worker.

All secrets are server-side environment variables — never shipped to the client.
See docs/architecture.md §5 for the full variable reference.
"""

from enum import StrEnum

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AvatarMode(StrEnum):
    """Which avatar rendering path the worker uses (docs/architecture.md ADRs)."""

    LEMONSLICE = "lemonslice"
    ANAM = "anam"
    FRONTEND = "frontend"
    NONE = "none"

    @property
    def is_cloud(self) -> bool:
        """Cloud-rendered modes: the vendor republishes TTS audio synced to video."""
        return self in (AvatarMode.LEMONSLICE, AvatarMode.ANAM)


class Settings(BaseSettings):
    """Agent worker settings, loaded from the environment (or a local .env file)."""

    # Repo-root .env is the canonical local secrets file; agent/.env can override.
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # LiveKit
    livekit_url: str = Field(description="wss:// URL of the LiveKit Cloud project")
    livekit_api_key: SecretStr
    livekit_api_secret: SecretStr

    # Model providers
    anthropic_api_key: SecretStr
    deepgram_api_key: SecretStr
    cartesia_api_key: SecretStr
    lemonslice_api_key: SecretStr | None = None
    anam_api_key: SecretStr | None = None

    # Avatar
    avatar_mode: AvatarMode = AvatarMode.LEMONSLICE
    lemonslice_agent_id: str | None = None
    lemonslice_image_url: str | None = None
    # Motion/demeanor prompts for LemonSlice's video model. These steer energy
    # and expressiveness (not exact gestures) — iterate via env, no code change.
    avatar_prompt: str = (
        "a calm, friendly astronaut telling stories — subtle natural facial "
        "expressions, gentle smile, relaxed natural hand gestures while speaking"
    )
    avatar_idle_prompt: str = (
        "a friendly astronaut listening — still and relaxed with a gentle floating "
        "sway, calm neutral face with a hint of a smile"
    )
    # Anam (CARA-4): avatar built in Anam Lab (animated-3D restyle), referenced
    # by ID. Director notes steer expressive performance; preset_style and
    # style_prompt are mutually exclusive (Anam rejects the pair with HTTP 400).
    anam_avatar_id: str | None = None
    anam_avatar_name: str = "Commander Sky"
    anam_avatar_model: str | None = None
    anam_preset_style: str | None = None
    anam_style_prompt: str | None = (
        "a calm, warm astronaut storyteller — gentle smile, relaxed and friendly"
    )
    anam_expressivity: float | None = Field(default=None, ge=0.0, le=1.0)

    # Models (env-overridable so provider model bumps don't need a code change)
    llm_model: str = "claude-sonnet-4-6"
    guard_model: str = "claude-haiku-4-5"
    # 1.5s (was 2.5): p99 classify is well under 1s; a hung call now fails
    # closed sooner instead of stalling the reply (still canned, never unsafe).
    guard_timeout_s: float = Field(default=1.5, gt=0)
    output_max_chars: int = Field(default=700, gt=0)
    stt_model: str = "flux-general-en"
    tts_model: str = "sonic-3.5"
    tts_voice: str | None = None

    # Session policy
    max_session_minutes: int = Field(default=15, ge=1, le=120)
    max_session_cost_usd: float = Field(default=5.0, gt=0)

    # Turn taking (seconds). General-audience default; raise toward ~0.9 for
    # young kids, who pause mid-thought far longer than adults.
    endpointing_delay_s: float = Field(default=0.5, ge=0.0, le=5.0)
    barge_in_min_words: int = Field(default=3, ge=1)
    # Flux eager end-of-turn confidence (0.3-0.9). Fires a provisional
    # end-of-turn early so the LLM starts before the turn is confirmed —
    # required for preemptive generation in STT mode. <=0 disables.
    eager_eot_threshold: float = Field(default=0.6, ge=0.0, le=0.9)

    # Proactive engagement: after this many quiet seconds the avatar offers a
    # fun fact or the quiz, at most idle_nudge_max times in a row. 0 disables.
    idle_nudge_s: float = Field(default=30.0, ge=0.0)
    idle_nudge_max: int = Field(default=2, ge=0)
    # Cost control: end the session after this many quiet seconds (an open tab
    # otherwise streams avatar + STT until the session cap). 0 disables.
    # 90s = two 30s nudges, then sign-off — tightened from 180s (owner
    # decision 2026-08-12, avatar minutes are the dominant cost).
    idle_shutdown_s: float = Field(default=90.0, ge=0.0)

    # Cost rates (USD) for the per-session estimate — keep in sync with vendor
    # pricing; env-overridable so price changes don't need a code change.
    cost_llm_in_per_mtok: float = Field(default=3.0, ge=0)
    cost_llm_cached_in_per_mtok: float = Field(default=0.30, ge=0)
    cost_llm_out_per_mtok: float = Field(default=15.0, ge=0)
    cost_guard_per_call: float = Field(default=0.0007, ge=0)
    cost_tts_per_1k_chars: float = Field(default=0.03, ge=0)
    cost_stt_per_min: float = Field(default=0.0077, ge=0)
    cost_avatar_per_min: float = Field(default=0.14, ge=0)  # Anam Explorer overage rate
    cost_livekit_per_min: float = Field(default=0.01, ge=0)


def load_settings() -> Settings:
    """Load settings from the environment, failing fast on missing required keys."""
    return Settings()  # type: ignore[call-arg]  # fields come from the environment
