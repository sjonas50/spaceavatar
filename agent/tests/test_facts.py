"""Facts loader tests: happy path plus missing/empty content failure modes."""

from pathlib import Path

import pytest

from commander_sky.facts import FactsError, load_facts


def test_load_bundled_facts() -> None:
    facts = load_facts()
    assert "Neil Armstrong" in facts
    assert "Apollo 11" in facts
    assert "July 20, 1969" in facts


def test_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(FactsError, match="not found"):
        load_facts(tmp_path / "nope")


def test_directory_without_facts_raises(tmp_path: Path) -> None:
    with pytest.raises(FactsError, match="no facts files"):
        load_facts(tmp_path)


def test_empty_facts_file_raises(tmp_path: Path) -> None:
    (tmp_path / "empty.md").write_text("   \n", encoding="utf-8")
    with pytest.raises(FactsError, match="empty"):
        load_facts(tmp_path)


def test_multiple_files_concatenated_in_order(tmp_path: Path) -> None:
    (tmp_path / "b_moon.md").write_text("# Moon", encoding="utf-8")
    (tmp_path / "a_apollo.md").write_text("# Apollo", encoding="utf-8")
    facts = load_facts(tmp_path)
    assert facts.index("# Apollo") < facts.index("# Moon")
