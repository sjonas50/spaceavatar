"""Interactive tools: gallery integrity, publish fallback, live-data caching."""

from pathlib import Path

import pytest

from commander_sky import skytools
from commander_sky.sky_agent import GalleryImage

WEB_SPACE_DIR = Path(__file__).parents[2] / "web" / "public" / "space"


class TestGallery:
    @pytest.mark.parametrize("image_id", list(skytools.GALLERY))
    def test_every_gallery_file_exists_in_web_public(self, image_id: str) -> None:
        src = skytools.GALLERY[image_id]["src"]
        assert src.startswith("/space/"), "client only renders /space/ paths"
        assert (WEB_SPACE_DIR / src.removeprefix("/space/")).is_file()

    def test_tool_enum_matches_gallery(self) -> None:
        assert set(GalleryImage.__args__) == set(skytools.GALLERY)

    @pytest.mark.parametrize("image_id", list(skytools.GALLERY))
    def test_captions_present(self, image_id: str) -> None:
        assert len(skytools.GALLERY[image_id]["caption"]) > 5


class TestShowImage:
    async def test_unknown_id_degrades_gracefully(self) -> None:
        result = await skytools.show_image("not_a_real_id")
        assert "Continue without" in result

    async def test_publishes_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sent: list[dict] = []

        async def fake_publish(payload: dict) -> bool:
            sent.append(payload)
            return True

        monkeypatch.setattr(skytools, "publish_ui", fake_publish)
        result = await skytools.show_image("saturn")
        assert sent == [
            {
                "type": "show_image",
                "id": "saturn",
                "src": "/space/saturn.jpg",
                "caption": "Saturn, seen by Cassini",
            }
        ]
        assert "On screen now" in result
        # the tool must steer the LLM back to the question, not to the image
        assert "Keep answering the visitor's actual question" in result

    async def test_no_job_context_degrades_to_voice_only(self) -> None:
        """Outside a LiveKit job (tests, dry-run) publishing fails softly."""
        result = await skytools.show_image("saturn")
        assert "Continue without the picture" in result


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status = status

    async def json(self) -> dict:
        return self._payload

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeHttp:
    def __init__(self, payload: dict, dead_assets: set[str] | None = None):
        self._payload = payload
        self._dead = dead_assets or set()
        self.calls = 0

    def get(self, url: str, params: dict | None = None) -> _FakeResponse:
        self.calls += 1
        return _FakeResponse(self._payload)

    def head(self, url: str, allow_redirects: bool = True) -> _FakeResponse:
        status = 404 if any(d in url for d in self._dead) else 200
        return _FakeResponse({}, status=status)


class TestNasaImageSearch:
    def _payload(self) -> dict:
        return {
            "collection": {
                "items": [
                    {"data": [{"nasa_id": "concert-astronaut", "title": "Orchestra performance"}]},
                    {"data": [{"nasa_id": "PIA18182", "title": "Uranus as seen by Voyager 2"}]},
                ]
            }
        }

    async def test_prefers_title_matching_query(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sent: list[dict] = []

        async def fake_publish(payload: dict) -> bool:
            sent.append(payload)
            return True

        monkeypatch.setattr(skytools, "publish_ui", fake_publish)
        result = await skytools.search_nasa_image("uranus voyager", _FakeHttp(self._payload()))  # type: ignore[arg-type]
        assert sent and sent[0]["id"] == "nasa:PIA18182"
        assert sent[0]["src"].startswith("https://images-assets.nasa.gov/image/")
        assert "Uranus" in result

    async def test_no_results_degrades(self) -> None:
        result = await skytools.search_nasa_image("x", _FakeHttp({"collection": {"items": []}}))  # type: ignore[arg-type]
        assert "Continue without" in result

    async def test_api_failure_degrades(self) -> None:
        class _Boom:
            def get(self, url: str, params: dict | None = None):
                raise OSError("down")

        result = await skytools.search_nasa_image("uranus", _Boom())  # type: ignore[arg-type]
        assert "Continue without" in result

    async def test_dead_asset_falls_back_to_next_candidate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Best-scored hit has no downloadable file -> next candidate is used."""
        sent: list[dict] = []

        async def fake_publish(payload: dict) -> bool:
            sent.append(payload)
            return True

        monkeypatch.setattr(skytools, "publish_ui", fake_publish)
        payload = {
            "collection": {
                "items": [
                    {"data": [{"nasa_id": "webb-dead", "title": "James Webb Space Telescope art"}]},
                    {"data": [{"nasa_id": "webb-good", "title": "James Webb Space Telescope"}]},
                ]
            }
        }
        http = _FakeHttp(payload, dead_assets={"webb-dead"})
        result = await skytools.search_nasa_image("james webb space telescope", http)  # type: ignore[arg-type]
        assert sent and sent[0]["id"] == "nasa:webb-good"
        assert "On screen now" in result

    async def test_all_assets_dead_degrades(self) -> None:
        payload = {"collection": {"items": [{"data": [{"nasa_id": "x1", "title": "a"}]}]}}
        http = _FakeHttp(payload, dead_assets={"x1"})
        result = await skytools.search_nasa_image("anything", http)  # type: ignore[arg-type]
        assert "Continue without" in result


class TestLiveData:
    async def test_iss_position_formats_sentence(self) -> None:
        http = _FakeHttp({"latitude": -12.3, "longitude": 45.6, "altitude": 421, "velocity": 27571})
        text = await skytools.fetch_iss_position(http)  # type: ignore[arg-type]
        assert "12.3 degrees south" in text
        assert "45.6 degrees east" in text

    async def test_iss_failure_returns_in_character_fallback(self) -> None:
        class _Boom:
            def get(self, url: str):
                raise OSError("network down")

        text = await skytools.fetch_iss_position(_Boom())  # type: ignore[arg-type]
        assert "isn't reachable" in text

    async def test_launch_is_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(skytools._launch_cache, "text", None)
        monkeypatch.setitem(skytools._launch_cache, "at", 0.0)
        http = _FakeHttp(
            {
                "results": [
                    {
                        "name": "Artemis IV",
                        "net": "2026-09-01T12:00:00Z",
                        "pad": {"location": {"name": "Kennedy Space Center, FL, USA"}},
                    }
                ]
            }
        )
        first = await skytools.fetch_next_launch(http)  # type: ignore[arg-type]
        second = await skytools.fetch_next_launch(http)  # type: ignore[arg-type]
        assert "Artemis IV" in first
        assert "Kennedy Space Center" in first
        assert second == first
        assert http.calls == 1  # second call served from cache


def test_agent_exposes_interactive_tools() -> None:
    from commander_sky.safety import InputGuard, OutputGuard
    from commander_sky.sky_agent import CommanderSkyAgent

    agent = CommanderSkyAgent(
        instructions="test",
        input_guard=InputGuard(api_key="fake"),
        output_guard=OutputGuard(),
    )
    tool_names = {getattr(t, "name", getattr(t, "__name__", "")) for t in agent.tools}
    joined = " ".join(str(n) for n in tool_names) + " " + str(agent.tools)
    for expected in (
        "show_picture",
        "get_space_station_location",
        "get_next_rocket_launch",
        "lookup_mission_archive",
    ):
        assert expected in joined
