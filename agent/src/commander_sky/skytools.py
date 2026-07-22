"""Interactive tools: on-screen visuals and live space data.

The gallery is a fixed allowlist of local, public-domain NASA images served
from the web app's own /public — the agent never sends external URLs to the
client, and the client renders only /space/ paths. Live data comes from two
keyless public APIs with short timeouts and graceful fallbacks: the avatar
should shrug charmingly, never stall.
"""

import json
import time
from typing import Any

import aiohttp
from livekit.agents import get_job_context

from commander_sky.logging import get_logger

log = get_logger("skytools")

UI_TOPIC = "ui"

GALLERY: dict[str, dict[str, str]] = {
    "saturn": {"src": "/space/saturn.jpg", "caption": "Saturn, seen by Cassini"},
    "jupiter": {"src": "/space/jupiter.jpg", "caption": "Jupiter with the Juno spacecraft"},
    "mars": {"src": "/space/mars.jpg", "caption": "Mars, the red planet"},
    "moon": {"src": "/space/moon.jpg", "caption": "Our Moon"},
    "earthrise": {"src": "/space/earthrise.jpg", "caption": "Earthrise — Apollo 8, 1968"},
    "apollo11_flag": {
        "src": "/space/apollo11.jpg",
        "caption": "Buzz Aldrin and the flag — Apollo 11, 1969",
    },
    "apollo11_crew": {
        "src": "/space/apollo11_crew.jpg",
        "caption": "Armstrong, Collins, and Aldrin — the Apollo 11 crew",
    },
    "saturn_v": {"src": "/space/saturn_v.jpg", "caption": "A Saturn V leaves the pad"},
    "iss": {"src": "/space/iss.jpg", "caption": "The International Space Station"},
    "milky_way": {"src": "/space/milky_way.jpg", "caption": "The Milky Way"},
}

NASA_IMAGES_API = "https://images-api.nasa.gov/search"
NASA_ASSETS_HOST = "https://images-assets.nasa.gov"

ISS_API = "https://api.wheretheiss.at/v1/satellites/25544"
LAUNCH_API = "https://ll.thespacedevs.com/2.2.0/launch/upcoming/?limit=1"
_LAUNCH_CACHE_TTL_S = 30 * 60  # Launch Library rate-limits unauthenticated calls

_launch_cache: dict[str, Any] = {"at": 0.0, "text": None}


async def publish_ui(payload: dict[str, Any]) -> bool:
    """Send a UI event to the browser over the room data channel.

    Returns False (and logs) when there's no active job — e.g. in unit tests
    or dry runs — so tools degrade to voice-only instead of raising.
    """
    try:
        ctx = get_job_context()
        await ctx.room.local_participant.publish_data(
            json.dumps(payload).encode("utf-8"), reliable=True, topic=UI_TOPIC
        )
        return True
    except Exception as exc:  # no job context (tests/dry-run) or transport error
        log.warning("publish_ui_failed", reason=type(exc).__name__)
        return False


async def show_image(image_id: str) -> str:
    """Publish a gallery image to the screen; returns text for the LLM to react to."""
    entry = GALLERY.get(image_id)
    if entry is None:
        return "That picture isn't in the gallery. Continue without it."
    sent = await publish_ui({"type": "show_image", "id": image_id, **entry})
    if not sent:
        return "The screen isn't available right now. Continue without the picture."
    return (
        f"On screen now: {entry['caption']}. Keep answering the visitor's actual "
        "question — the picture just illustrates it."
    )


async def search_nasa_image(query: str, http: aiohttp.ClientSession | None = None) -> str:
    """Search NASA's public image library and push the best hit to the screen.

    Only images-assets.nasa.gov URLs are ever published (the client enforces
    the same allowlist). Prefers results whose title matches the query terms —
    NASA search's first hit is unreliable (concert photos of costumed
    astronauts are real search results).
    """
    owned = http is None
    session = http or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6))
    try:
        params = {"media_type": "image", "q": query}
        async with session.get(NASA_IMAGES_API, params=params) as resp:
            data = await resp.json()
        items = data.get("collection", {}).get("items", [])[:8]
        if not items:
            return "No archive imagery found for that. Continue without a picture."

        terms = set(query.lower().split())

        def score(item: dict) -> int:
            title = (item.get("data") or [{}])[0].get("title", "").lower()
            return sum(1 for t in terms if t in title)

        best = max(items, key=score)
        meta = (best.get("data") or [{}])[0]
        nasa_id = meta.get("nasa_id", "")
        title = meta.get("title", "From the NASA archive")[:120]
        if not nasa_id:
            return "No archive imagery found for that. Continue without a picture."

        src = f"{NASA_ASSETS_HOST}/image/{nasa_id}/{nasa_id}~medium.jpg"
        sent = await publish_ui(
            {"type": "show_image", "id": f"nasa:{nasa_id}", "src": src, "caption": title}
        )
        if not sent:
            return "The screen isn't available right now. Continue without the picture."
        return (
            f"On screen now: {title}. Keep answering the visitor's actual question — "
            "the picture just illustrates it."
        )
    except Exception as exc:
        log.warning("nasa_search_failed", reason=type(exc).__name__)
        return "The image archive isn't reachable right now. Continue without a picture."
    finally:
        if owned:
            await session.close()


async def fetch_iss_position(http: aiohttp.ClientSession | None = None) -> str:
    """Live ISS position as a sentence the persona can build on."""
    owned = http is None
    session = http or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4))
    try:
        async with session.get(ISS_API) as resp:
            data = await resp.json()
        lat, lon = float(data["latitude"]), float(data["longitude"])
        alt = float(data.get("altitude", 420))
        vel = float(data.get("velocity", 27500))
        ns = "north" if lat >= 0 else "south"
        ew = "east" if lon >= 0 else "west"
        return (
            f"Right now the ISS is at latitude {abs(lat):.1f} degrees {ns}, longitude "
            f"{abs(lon):.1f} degrees {ew}, about {alt:.0f} km up, moving at {vel:.0f} km/h. "
            "Describe roughly where on Earth that is in everyday terms."
        )
    except Exception as exc:
        log.warning("iss_fetch_failed", reason=type(exc).__name__)
        return "Live ISS data isn't reachable right now — say so with charm and move on."
    finally:
        if owned:
            await session.close()


async def fetch_next_launch(http: aiohttp.ClientSession | None = None) -> str:
    """Next real-world rocket launch, cached to respect the API's rate limits."""
    now = time.monotonic()
    if _launch_cache["text"] and now - _launch_cache["at"] < _LAUNCH_CACHE_TTL_S:
        return _launch_cache["text"]

    owned = http is None
    session = http or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6))
    try:
        async with session.get(LAUNCH_API) as resp:
            data = await resp.json()
        launch = data["results"][0]
        name = launch.get("name", "an upcoming launch")
        when = (launch.get("net") or "")[:16].replace("T", " at ")
        pad = (launch.get("pad") or {}).get("location", {}).get("name", "")
        text = (
            f"The next scheduled rocket launch is {name}"
            + (f", from {pad}" if pad else "")
            + (f", around {when} UTC" if when else "")
            + ". Share it with excitement, converting the time to something relatable."
        )
        _launch_cache.update(at=now, text=text)
        return text
    except Exception as exc:
        log.warning("launch_fetch_failed", reason=type(exc).__name__)
        return "Launch schedule data isn't reachable right now — say so with charm and move on."
    finally:
        if owned:
            await session.close()
