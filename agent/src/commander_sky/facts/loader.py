"""Loader for the curated facts content injected into the persona prompt."""

from pathlib import Path

FACTS_DIR = Path(__file__).parent


class FactsError(Exception):
    """Facts content is missing or unusable — the agent must not start without it."""


def load_facts(facts_dir: Path = FACTS_DIR) -> str:
    """Load and concatenate all curated facts markdown files.

    Args:
        facts_dir: Directory containing ``*.md`` facts files.

    Returns:
        The combined facts text, files concatenated in sorted-name order.

    Raises:
        FactsError: If the directory has no facts files or a file is empty.
    """
    if not facts_dir.is_dir():
        raise FactsError(f"facts directory not found: {facts_dir}")

    files = sorted(facts_dir.glob("*.md"))
    if not files:
        raise FactsError(f"no facts files (*.md) in {facts_dir}")

    sections: list[str] = []
    for file in files:
        text = file.read_text(encoding="utf-8").strip()
        if not text:
            raise FactsError(f"facts file is empty: {file.name}")
        sections.append(text)
    return "\n\n".join(sections)
