"""Scaffold smoke tests: package imports and config loads from the environment."""

import pytest
from pydantic import ValidationError

import commander_sky
from commander_sky.config import AvatarMode, Settings


def test_package_importable() -> None:
    assert commander_sky.__version__


def test_settings_load_from_env(settings: Settings) -> None:
    assert settings.livekit_url == "wss://fake.livekit.cloud"
    assert settings.avatar_mode is AvatarMode.LEMONSLICE
    assert settings.max_session_minutes == 15


def test_settings_missing_required_key_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_secrets_are_not_exposed_in_repr(settings: Settings) -> None:
    assert "fake-secret" not in repr(settings)
    assert "fake-anthropic" not in repr(settings)
