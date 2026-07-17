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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    # Session policy
    max_session_minutes: int = Field(default=15, ge=1, le=120)
    max_session_cost_usd: float = Field(default=5.0, gt=0)

    # Kid-tuned turn taking (seconds) — kids pause mid-thought; don't cut them off.
    endpointing_delay_s: float = Field(default=0.9, ge=0.0, le=5.0)
    barge_in_min_words: int = Field(default=3, ge=1)


def load_settings() -> Settings:
    """Load settings from the environment, failing fast on missing required keys."""
    return Settings()  # type: ignore[call-arg]  # fields come from the environment
