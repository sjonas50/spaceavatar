"""Avatar adapter: the swappable rendering path behind one small interface.

Modes (docs/architecture.md ADRs):
- ``lemonslice``: cloud-rendered stylized avatar publishes synced video+audio.
- ``frontend``: agent publishes audio only; the browser renders the character.
- ``none``: audio only (bake-off baseline / local development).
"""

from livekit.plugins import lemonslice

from commander_sky.config import AvatarMode, Settings


class AvatarConfigError(Exception):
    """Avatar mode is enabled but its required configuration is missing."""


def create_avatar(settings: Settings) -> lemonslice.AvatarSession | None:
    """Build the avatar session for the configured mode, or None for audio-only modes.

    Args:
        settings: Loaded agent settings.

    Returns:
        A LemonSlice ``AvatarSession`` in ``lemonslice`` mode, else ``None``.

    Raises:
        AvatarConfigError: If ``lemonslice`` mode is selected without credentials.
    """
    if settings.avatar_mode is not AvatarMode.LEMONSLICE:
        return None
    if settings.lemonslice_api_key is None:
        raise AvatarConfigError("AVATAR_MODE=lemonslice requires LEMONSLICE_API_KEY")
    return lemonslice.AvatarSession(
        api_key=settings.lemonslice_api_key.get_secret_value(),
        agent_prompt=settings.avatar_prompt,
        agent_idle_prompt=settings.avatar_idle_prompt,
        **character_kwargs(settings),
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
    return settings.avatar_mode is not AvatarMode.LEMONSLICE
