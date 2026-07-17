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
    if not (settings.lemonslice_agent_id or settings.lemonslice_image_url):
        raise AvatarConfigError(
            "AVATAR_MODE=lemonslice requires LEMONSLICE_AGENT_ID or LEMONSLICE_IMAGE_URL"
        )
    return lemonslice.AvatarSession(
        api_key=settings.lemonslice_api_key.get_secret_value(),
        agent_id=settings.lemonslice_agent_id,
        agent_image_url=settings.lemonslice_image_url,
    )


def room_audio_enabled(settings: Settings) -> bool:
    """Whether the agent publishes its own audio track.

    False for cloud avatar modes — the avatar provider republishes TTS audio
    synced to video; publishing both causes double audio.
    """
    return settings.avatar_mode is not AvatarMode.LEMONSLICE
