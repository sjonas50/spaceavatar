"""Mission archive: corpus integrity, retrieval quality, tool behavior."""

import pytest

from commander_sky.knowledge import KnowledgeBase
from commander_sky.knowledge.retriever import KNOWLEDGE_DIR


@pytest.fixture(scope="module")
def kb() -> KnowledgeBase:
    return KnowledgeBase()


class TestCorpus:
    def test_archive_has_substance(self, kb: KnowledgeBase) -> None:
        assert len(list(KNOWLEDGE_DIR.glob("*.md"))) >= 6
        assert len(kb.chunks) >= 25

    def test_chunks_are_heading_sections(self, kb: KnowledgeBase) -> None:
        for chunk in kb.chunks:
            assert chunk.title, "every chunk needs a heading title"
            assert len(chunk.text) > 80, f"suspiciously thin chunk: {chunk.title}"

    def test_no_review_comments_leak_into_chunks(self, kb: KnowledgeBase) -> None:
        assert all("<!--" not in c.text for c in kb.chunks)


class TestRetrieval:
    @pytest.mark.parametrize(
        ("query", "expected_source", "expected_term"),
        [
            ("what happened to challenger", "shuttle_stations", "O-ring"),
            ("tell me about the ocean on europa", "solar_system_deep", "Europa"),
            ("who was sally ride", "astronaut_life_people", "Sally Ride"),
            ("how do rockets land themselves", "rockets_future", "Falcon 9"),
            ("first spacewalk", "early_spaceflight", "Leonov"),
            ("apollo 13 explosion", "apollo_missions", "oxygen tank"),
            ("black hole picture", "stars_cosmos", "Event Horizon"),
        ],
    )
    def test_finds_relevant_chunk(
        self, kb: KnowledgeBase, query: str, expected_source: str, expected_term: str
    ) -> None:
        results = kb.search(query, k=3)
        assert results, f"no results for {query!r}"
        combined = " ".join(c.source + " " + c.text for c in results)
        assert expected_source in combined
        assert expected_term in combined

    def test_gibberish_returns_empty(self, kb: KnowledgeBase) -> None:
        assert kb.search("qzxv blorptastic frobnicator") == []

    def test_empty_query_returns_empty(self, kb: KnowledgeBase) -> None:
        assert kb.search("   ") == []


class TestArchiveTool:
    @pytest.fixture()
    def agent(self):
        from commander_sky.safety import InputGuard, OutputGuard
        from commander_sky.sky_agent import CommanderSkyAgent

        return CommanderSkyAgent(
            instructions="test",
            input_guard=InputGuard(api_key="fake"),
            output_guard=OutputGuard(),
        )

    async def test_lookup_returns_excerpts(self, agent) -> None:
        result = await agent.lookup_mission_archive(query="challenger disaster")
        assert "Archive excerpts" in result
        assert "O-ring" in result
        assert len(result) <= 4000

    async def test_lookup_miss_instructs_no_guessing(self, agent) -> None:
        result = await agent.lookup_mission_archive(query="qzxv blorptastic")
        assert "do not guess" in result
