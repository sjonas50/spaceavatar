"""Avatar adapter: the swappable rendering path behind one small interface.

Modes (docs/architecture.md ADRs):
- ``lemonslice``: cloud-rendered stylized avatar publishes synced video+audio.
- ``anam``: cloud-rendered avatar (CARA-4, animated-3D restyle) — same contract.
- ``frontend``: agent publishes audio only; the browser renders the character.
- ``none``: audio only (bake-off baseline / local development).

Both cloud plugins share LiveKit's base ``AvatarSession`` contract, so the
canonical startup order in main.py (avatar.start → wait_for_join →
session.start with room audio disabled) is identical for both.
"""

from livekit.plugins import anam, lemonslice
from livekit.plugins.anam.types import DirectorNotes, PersonaConfig

from commander_sky.config import AvatarMode, Settings

CloudAvatarSession = lemonslice.AvatarSession | anam.AvatarSession


class AvatarConfigError(Exception):
    """Avatar mode is enabled but its required configuration is missing."""


def create_avatar(settings: Settings) -> CloudAvatarSession | None:
    """Build the avatar session for the configured mode, or None for audio-only modes.

    Args:
        settings: Loaded agent settings.

    Returns:
        A cloud ``AvatarSession`` in ``lemonslice``/``anam`` mode, else ``None``.

    Raises:
        AvatarConfigError: If a cloud mode is selected without credentials.
    """
    if settings.avatar_mode is AvatarMode.LEMONSLICE:
        return _create_lemonslice(settings)
    if settings.avatar_mode is AvatarMode.ANAM:
        return _create_anam(settings)
    return None


def _create_lemonslice(settings: Settings) -> lemonslice.AvatarSession:
    if settings.lemonslice_api_key is None:
        raise AvatarConfigError("AVATAR_MODE=lemonslice requires LEMONSLICE_API_KEY")
    return lemonslice.AvatarSession(
        api_key=settings.lemonslice_api_key.get_secret_value(),
        agent_prompt=settings.avatar_prompt,
        agent_idle_prompt=settings.avatar_idle_prompt,
        **character_kwargs(settings),
    )


def _create_anam(settings: Settings) -> anam.AvatarSession:
    if settings.anam_api_key is None:
        raise AvatarConfigError("AVATAR_MODE=anam requires ANAM_API_KEY")
    if not settings.anam_avatar_id:
        raise AvatarConfigError("AVATAR_MODE=anam requires ANAM_AVATAR_ID (from Anam Lab)")
    return anam.AvatarSession(
        api_key=settings.anam_api_key.get_secret_value(),
        persona_config=PersonaConfig(
            name=settings.anam_avatar_name,
            avatarId=settings.anam_avatar_id,
            avatarModel=settings.anam_avatar_model,
            directorNotes=anam_director_notes(settings),
        ),
    )


def anam_director_notes(settings: Settings) -> DirectorNotes | None:
    """Director notes for Anam, or None to use the avatar model's defaults.

    Anam rejects preset_style + style_prompt together (HTTP 400), and
    style_prompt has a persona default — so an explicit ANAM_PRESET_STYLE
    takes precedence over the prompt rather than erroring.
    """
    style = settings.anam_preset_style
    prompt = settings.anam_style_prompt if not style else None
    if style is None and prompt is None and settings.anam_expressivity is None:
        return None
    return DirectorNotes(
        expressivity=settings.anam_expressivity,
        presetStyle=style,
        customStylePrompt=prompt,
    )


def character_kwargs(settings: Settings) -> dict[str, str]:
    """The one character-identity kwarg LemonSlice accepts.

    The plugin rejects the session if more than one of agent_id/agent_image_url/
    agent_image is passed — and an explicit ``None`` counts as passed (its own
    defaults are a NOT_GIVEN sentinel). So: exactly one key, never None values.
    """
    if settings.lemonslice_agent_id:
        return {"agent_id": settings.lemonslice_agent_id}
    if settings.lemonslice_image_url:
        return {"agent_image_url": settings.lemonslice_image_url}
    raise AvatarConfigError(
        "AVATAR_MODE=lemonslice requires LEMONSLICE_AGENT_ID or LEMONSLICE_IMAGE_URL"
    )


def room_audio_enabled(settings: Settings) -> bool:
    """Whether the agent publishes its own audio track.

    False for cloud avatar modes — the avatar provider republishes TTS audio
    synced to video; publishing both causes double audio.
    """
    return not settings.avatar_mode.is_cloud
