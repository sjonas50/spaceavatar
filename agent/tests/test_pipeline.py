"""Pipeline wiring tests: everything must construct offline with fake credentials."""

import asyncio
from types import SimpleNamespace

import pytest

from commander_sky.avatar import (
    AvatarConfigError,
    anam_director_notes,
    character_kwargs,
    create_avatar,
    room_audio_enabled,
)
from commander_sky.config import AvatarMode, Settings
from commander_sky.main import SPACE_KEYTERMS, build_session


async def test_build_session_constructs_offline(settings: Settings) -> None:
    # async: AgentSession's constructor requires an event loop to exist
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

    def test_anam_mode_builds_avatar(self, settings: Settings) -> None:
        configured = settings.model_copy(
            update={"avatar_mode": AvatarMode.ANAM, "anam_avatar_id": "sky-cara-01"}
        )
        assert create_avatar(configured) is not None
        assert room_audio_enabled(configured) is False

    def test_anam_without_key_fails(self, settings: Settings) -> None:
        broken = settings.model_copy(
            update={
                "avatar_mode": AvatarMode.ANAM,
                "anam_api_key": None,
                "anam_avatar_id": "sky-cara-01",
            }
        )
        with pytest.raises(AvatarConfigError, match="ANAM_API_KEY"):
            create_avatar(broken)

    def test_anam_without_avatar_id_fails(self, settings: Settings) -> None:
        broken = settings.model_copy(update={"avatar_mode": AvatarMode.ANAM})
        with pytest.raises(AvatarConfigError, match="ANAM_AVATAR_ID"):
            create_avatar(broken)

    def test_anam_preset_style_wins_over_default_prompt(self, settings: Settings) -> None:
        """Anam 400s when presetStyle and customStylePrompt are both set — an
        explicit preset must suppress the persona's default style prompt."""
        configured = settings.model_copy(update={"anam_preset_style": "warm"})
        notes = anam_director_notes(configured)
        assert notes is not None
        assert notes.presetStyle == "warm"
        assert notes.customStylePrompt is None

    def test_anam_no_director_notes_when_unset(self, settings: Settings) -> None:
        configured = settings.model_copy(
            update={"anam_preset_style": None, "anam_style_prompt": None}
        )
        assert anam_director_notes(configured) is None

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


async def test_dry_run_exits_zero(fake_env: dict[str, str]) -> None:
    # async: dry_run builds an AgentSession, which needs an event loop
    from commander_sky.main import dry_run

    assert dry_run() == 0


class TestAvatarDeathFallback:
    """Mid-session avatar death must reroute audio, not freeze the session."""

    @staticmethod
    def _fakes(monkeypatch: pytest.MonkeyPatch, visitor_present: bool = True):
        from livekit import rtc

        from commander_sky import main as main_mod

        handlers: dict[str, object] = {}
        visitor = SimpleNamespace(
            kind=rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD, identity="explorer-1234"
        )
        room = SimpleNamespace(
            on=lambda name, cb: handlers.setdefault(name, cb),
            remote_participants={"explorer-1234": visitor} if visitor_present else {},
        )
        ctx = SimpleNamespace(room=room)

        class FakeOutput:
            tail = None

            def replace_audio_tail(self, sink: object) -> None:
                self.tail = sink

        session = SimpleNamespace(
            output=FakeOutput(),
            said=[],
            interrupted=False,
        )
        session.interrupt = lambda: setattr(session, "interrupted", True)
        session.say = lambda text: session.said.append(text)

        class StubParticipantAudioOutput:
            def __init__(self, room: object, **_: object) -> None:
                pass

            async def start(self) -> None:
                pass

        monkeypatch.setattr(main_mod, "_ParticipantAudioOutput", StubParticipantAudioOutput)
        main_mod._watch_avatar_departure(ctx, session, "anam-avatar-agent")
        return session, handlers["participant_disconnected"]

    async def test_avatar_disconnect_reroutes_audio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session, on_disconnect = self._fakes(monkeypatch)
        on_disconnect(SimpleNamespace(identity="anam-avatar-agent"))
        await asyncio.sleep(0.01)
        assert session.output.tail is not None
        assert session.interrupted
        assert session.said, "must acknowledge the video loss in character"

    async def test_human_disconnect_does_not_trigger_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session, on_disconnect = self._fakes(monkeypatch)
        on_disconnect(SimpleNamespace(identity="explorer-1234"))
        await asyncio.sleep(0.01)
        assert session.output.tail is None
        assert not session.said

    async def test_teardown_avatar_exit_stays_silent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Visitor already left: the avatar disconnecting is session teardown,
        # not a mid-session death — no reroute, no canned line to an empty room.
        session, on_disconnect = self._fakes(monkeypatch, visitor_present=False)
        on_disconnect(SimpleNamespace(identity="anam-avatar-agent"))
        await asyncio.sleep(0.01)
        assert session.output.tail is None
        assert not session.said
