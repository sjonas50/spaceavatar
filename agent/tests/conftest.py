"""Shared fixtures: fake credentials so tests never need real keys or network."""

import pytest

from commander_sky.config import Settings

FAKE_ENV = {
    "LIVEKIT_URL": "wss://fake.livekit.cloud",
    "LIVEKIT_API_KEY": "fake-key",
    "LIVEKIT_API_SECRET": "fake-secret",
    "ANTHROPIC_API_KEY": "fake-anthropic",
    "DEEPGRAM_API_KEY": "fake-deepgram",
    "CARTESIA_API_KEY": "fake-cartesia",
    "LEMONSLICE_API_KEY": "fake-lemonslice",
}


@pytest.fixture
def fake_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Populate the environment with fake credentials."""
    for key, value in FAKE_ENV.items():
        monkeypatch.setenv(key, value)
    return FAKE_ENV


@pytest.fixture
def settings(fake_env: dict[str, str]) -> Settings:
    """Settings built from fake credentials."""
    return Settings(_env_file=None)
