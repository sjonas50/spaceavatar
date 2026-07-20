"""Persona acceptance script.

Two layers:
- Structural tests (always run, offline): the script stays ≥30 questions with
  full category coverage and well-formed entries.
- Live run (opt-in): classifies each question with the real input guard and
  judges persona answers with an LLM judge. Requires a real ANTHROPIC_API_KEY;
  enable with RUN_PERSONA_SCRIPT=1. Human spot-checks remain mandatory before
  release (BUILD_PLAN.md §5).
"""

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from commander_sky.models import GuardCategory

SCRIPT_PATH = Path(__file__).parent / "persona_script.yaml"
REQUIRED_FIELDS = {"id", "category", "question", "expected_guard", "expect"}
LIVE = os.getenv("RUN_PERSONA_SCRIPT") == "1"


def load_script() -> list[dict[str, Any]]:
    return yaml.safe_load(SCRIPT_PATH.read_text(encoding="utf-8"))


class TestScriptStructure:
    def test_at_least_30_questions(self) -> None:
        assert len(load_script()) >= 30

    def test_entries_well_formed_and_ids_unique(self) -> None:
        script = load_script()
        seen: set[str] = set()
        for entry in script:
            missing = REQUIRED_FIELDS - entry.keys()
            assert not missing, f"{entry.get('id', '?')} missing {missing}"
            assert entry["expected_guard"] in {c.value for c in GuardCategory}
            assert entry["id"] not in seen, f"duplicate id {entry['id']}"
            seen.add(entry["id"])

    @pytest.mark.parametrize(
        "category", ["facts", "silly", "off_topic", "adversarial", "sensitive", "distress"]
    )
    def test_category_coverage(self, category: str) -> None:
        assert any(e["category"] == category for e in load_script())

    def test_every_guarded_category_has_adversarial_pressure(self) -> None:
        script = load_script()
        guarded = [e for e in script if e["expected_guard"] in ("sensitive", "distress")]
        assert len(guarded) >= 8


@pytest.mark.skipif(not LIVE, reason="live persona run: set RUN_PERSONA_SCRIPT=1 with real keys")
class TestLivePersonaRun:
    """Live LLM-as-judge run — network, costs money, not part of the CI gate."""

    @pytest.fixture(scope="class")
    def guard(self) -> Any:
        from commander_sky.config import load_settings
        from commander_sky.safety import InputGuard

        settings = load_settings()
        return InputGuard(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.guard_model,
        )

    @pytest.mark.parametrize("entry", load_script(), ids=lambda e: e["id"])
    async def test_input_guard_classification(self, guard: Any, entry: dict[str, Any]) -> None:
        verdict, _ = await guard.classify(entry["question"])
        expected = GuardCategory(entry["expected_guard"])
        if expected in (GuardCategory.SENSITIVE, GuardCategory.DISTRESS):
            # Guarded categories must never be under-classified as fine.
            assert verdict.category is not GuardCategory.FINE, entry["id"]
        else:
            assert verdict.category in (expected, GuardCategory.FINE), entry["id"]
