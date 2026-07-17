"""Persona prompt tests: required behavioral rules must survive prompt edits."""

import pytest

from commander_sky.facts import load_facts
from commander_sky.persona import CHARACTER_NAME, build_system_prompt


@pytest.fixture(scope="module")
def prompt() -> str:
    return build_system_prompt(load_facts())


def test_empty_facts_rejected() -> None:
    with pytest.raises(ValueError, match="facts"):
        build_system_prompt("   ")


def test_character_identity(prompt: str) -> None:
    assert CHARACTER_NAME in prompt
    assert "NOT Neil Armstrong" in prompt


@pytest.mark.parametrize(
    "required_rule",
    [
        "one to three sentences",  # voice-length answers
        "Neil Armstrong said",  # attribution rule
        "outside my flight plan",  # off-topic deflection
        "Never ask for personal information",  # no-PII rule
        "voice conversation",  # voice-formatting rule
        "someone they trust",  # distress posture
    ],
)
def test_required_rules_present(prompt: str, required_rule: str) -> None:
    assert required_rule in prompt


def test_facts_embedded(prompt: str) -> None:
    assert "Sea of Tranquility" in prompt
    assert "one small step" in prompt


def test_prompt_is_deterministic_for_caching(prompt: str) -> None:
    """Anthropic prompt caching requires a byte-stable prefix for a given facts file."""
    assert prompt == build_system_prompt(load_facts())
