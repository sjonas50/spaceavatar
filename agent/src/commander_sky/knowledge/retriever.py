"""Local retrieval over the extended mission archive.

BM25 keyword search over heading-level chunks of the curated markdown corpus.
Runs entirely in-process: no vendor, no network, ~1ms per query. Voice
questions are short and keyword-rich, which BM25 handles well; if recall ever
disappoints, the swap point for embeddings is search() — nothing else changes.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

KNOWLEDGE_DIR = Path(__file__).parent

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_HEADING_RE = re.compile(r"^#{1,3} ", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    """One heading-level section of the archive."""

    source: str  # file stem, e.g. "apollo_missions"
    title: str  # the heading line
    text: str  # heading + body


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class KnowledgeBase:
    """Loads the archive once and answers keyword queries."""

    def __init__(self, knowledge_dir: Path = KNOWLEDGE_DIR):
        self.chunks: list[Chunk] = []
        for path in sorted(knowledge_dir.glob("*.md")):
            self.chunks.extend(_chunk_file(path))
        if not self.chunks:
            raise ValueError(f"no knowledge content found in {knowledge_dir}")
        self._bm25 = BM25Okapi([_tokenize(c.text) for c in self.chunks])

    def search(self, query: str, k: int = 3) -> list[Chunk]:
        """Top-k chunks for the query; empty list when nothing scores at all."""
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self.chunks[i] for i in ranked[:k] if scores[i] > 0]


def _chunk_file(path: Path) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    # Strip HTML comments (review headers) before chunking
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()
    chunks: list[Chunk] = []
    positions = [m.start() for m in _HEADING_RE.finditer(text)]
    if not positions:
        return [Chunk(source=path.stem, title=path.stem, text=text)] if text else []
    for start, end in zip(positions, [*positions[1:], len(text)], strict=True):
        section = text[start:end].strip()
        if len(section.splitlines()) < 2:
            continue  # heading with no body
        title = section.splitlines()[0].lstrip("# ").strip()
        chunks.append(Chunk(source=path.stem, title=title, text=section))
    return chunks
