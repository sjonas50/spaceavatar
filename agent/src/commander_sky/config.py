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
    FRONTEND = "frontend"
    NONE = "none"


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

    # Avatar
    avatar_mode: AvatarMode = AvatarMode.LEMONSLICE
    lemonslice_agent_id: str | None = None
    lemonslice_image_url: str | None = None

    # Models (env-overridable so provider model bumps don't need a code change)
    llm_model: str = "claude-sonnet-4-6"
    guard_model: str = "claude-haiku-4-5"
    guard_timeout_s: float = Field(default=2.5, gt=0)
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


def load_settings() -> Settings:
    """Load settings from the environment, failing fast on missing required keys."""
    return Settings()  # type: ignore[call-arg]  # fields come from the environment
