"""Heading-aware, sentence-boundary chunking with overlap."""

from __future__ import annotations

import re
from dataclasses import dataclass

_SENTENCE_RE = re.compile(r"(?<=[.!?।॥])\s+")  # includes Devanagari danda । ॥
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    heading: str | None
    text: str


def _split_sentences(paragraph: str) -> list[str]:
    parts = [s.strip() for s in _SENTENCE_RE.split(paragraph) if s.strip()]
    return parts or [paragraph]


def _hard_wrap(sentence: str, size: int) -> list[str]:
    if len(sentence) <= size:
        return [sentence]
    words, out, cur = sentence.split(" "), [], ""
    for w in words:
        while len(w) > size:  # pathological unbroken strings
            if cur:
                out.append(cur)
                cur = ""
            out.append(w[:size])
            w = w[size:]
        if len(cur) + len(w) + 1 > size and cur:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return out


def _sections(text: str) -> list[tuple[str | None, list[str]]]:
    sections: list[tuple[str | None, list[str]]] = []
    heading: str | None = None
    paragraphs: list[str] = []
    current: list[str] = []

    def flush_paragraph() -> None:
        if current:
            paragraphs.append(" ".join(current))
            current.clear()

    # Line-based so a heading directly followed by text (no blank line) is still recognised.
    for line in text.splitlines():
        line = line.strip()
        m = _HEADING_RE.match(line)
        if m:
            flush_paragraph()
            if paragraphs:
                sections.append((heading, paragraphs))
            heading, paragraphs = m.group(2).strip(), []
        elif not line:
            flush_paragraph()
        elif line.startswith("- "):
            flush_paragraph()
            paragraphs.append(line)
        else:
            current.append(line)
    flush_paragraph()
    if paragraphs:
        sections.append((heading, paragraphs))
    return sections


def chunk_text(text: str, *, size: int = 900, overlap: int = 150) -> list[TextChunk]:
    """Pack sentences into chunks of at most ``size`` chars, never crossing a heading.

    Consecutive chunks inside one section share up to ``overlap`` chars of trailing
    sentences so facts that straddle a boundary remain retrievable.
    """
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    chunks: list[TextChunk] = []
    for heading, paragraphs in _sections(text):
        units: list[str] = []
        for p in paragraphs:
            for s in _split_sentences(p):
                units.extend(_hard_wrap(s, size))
        current: list[str] = []
        for unit in units:
            candidate = " ".join(current + [unit])
            if current and len(candidate) > size:
                chunks.append(TextChunk(len(chunks), heading, " ".join(current)))
                tail: list[str] = []
                for prev in reversed(current):
                    if sum(len(t) + 1 for t in tail) + len(prev) > overlap:
                        break
                    tail.insert(0, prev)
                current = tail + [unit]
                if len(" ".join(current)) > size:
                    current = [unit]
            else:
                current.append(unit)
        if current:
            chunks.append(TextChunk(len(chunks), heading, " ".join(current)))
    return chunks
