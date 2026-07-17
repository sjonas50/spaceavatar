"""Pipeline wiring tests: everything must construct offline with fake credentials."""

import pytest

from commander_sky.avatar import (
    AvatarConfigError,
    character_kwargs,
    create_avatar,
    room_audio_enabled,
)
from commander_sky.config import AvatarMode, Settings
from commander_sky.main import SPACE_KEYTERMS, build_session


def test_build_session_constructs_offline(settings: Settings) -> None:
    session = build_session(settings)
    assert session is not None


def test_keyterms_cover_core_curriculum() -> None:
    assert "Neil Armstrong" in SPACE_KEYTERMS
    assert "Apollo" in SPACE_KEYTERMS


class TestAvatarAdapter:
    def test_lemonslice_mode_builds_avatar(self, settings: Settings) -> None:
        configured = settings.model_copy(update={"lemonslice_agent_id": "sky-01"})
        assert create_avatar(configured) is not None
        assert room_audio_enabled(configured) is False

    @pytest.mark.parametrize("mode", [AvatarMode.FRONTEND, AvatarMode.NONE])
    def test_audio_only_modes_have_no_avatar(self, settings: Settings, mode: AvatarMode) -> None:
        configured = settings.model_copy(update={"avatar_mode": mode})
        assert create_avatar(configured) is None
        assert room_audio_enabled(configured) is True

    def test_lemonslice_without_key_fails(self, settings: Settings) -> None:
        broken = settings.model_copy(
            update={"lemonslice_api_key": None, "lemonslice_agent_id": "sky-01"}
        )
        with pytest.raises(AvatarConfigError, match="LEMONSLICE_API_KEY"):
            create_avatar(broken)

    def test_lemonslice_without_character_fails(self, settings: Settings) -> None:
        with pytest.raises(AvatarConfigError, match="AGENT_ID"):
            create_avatar(settings)

    def test_exactly_one_character_kwarg_never_none(self, settings: Settings) -> None:
        """LemonSlice rejects sessions when >1 identity kwarg is passed — an
        explicit None counts as passed (regression: crashed live jobs)."""
        by_id = settings.model_copy(update={"lemonslice_agent_id": "sky-01"})
        assert character_kwargs(by_id) == {"agent_id": "sky-01"}

        by_image = settings.model_copy(update={"lemonslice_image_url": "https://x/img.png"})
        assert character_kwargs(by_image) == {"agent_image_url": "https://x/img.png"}

        both = settings.model_copy(
            update={"lemonslice_agent_id": "sky-01", "lemonslice_image_url": "https://x/img.png"}
        )
        assert character_kwargs(both) == {"agent_id": "sky-01"}
        for kwargs in (character_kwargs(by_id), character_kwargs(by_image)):
            assert len(kwargs) == 1
            assert None not in kwargs.values()


def test_dry_run_exits_zero(fake_env: dict[str, str]) -> None:
    from commander_sky.main import dry_run

    assert dry_run() == 0
