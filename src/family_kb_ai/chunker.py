from __future__ import annotations

from dataclasses import dataclass
import re

from .models import Chunk, make_chunk_id


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class MarkdownSection:
    section_path: tuple[str, ...]
    text: str


def parse_markdown_sections(markdown: str) -> list[MarkdownSection]:
    """Split Markdown by headings while retaining the active heading hierarchy."""
    sections: list[MarkdownSection] = []
    headings: list[str] = []
    body: list[str] = []
    in_fence = False

    def flush() -> None:
        text = "\n".join(body).strip()
        if text:
            sections.append(MarkdownSection(tuple(headings), text))
        body.clear()

    for line in markdown.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            body.append(line)
            continue

        match = None if in_fence else _HEADING_RE.match(line)
        if not match:
            body.append(line)
            continue

        flush()
        level = len(match.group(1))
        title = match.group(2).strip().rstrip("#").strip()
        headings[:] = headings[: level - 1]
        while len(headings) < level - 1:
            headings.append("")
        headings.append(title)

    flush()
    return sections


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        max_end = min(start + chunk_size, length)
        end = max_end

        if max_end < length:
            search_from = start + max(chunk_size // 2, 1)
            candidates = [
                text.rfind("\n\n", search_from, max_end),
                text.rfind("\n", search_from, max_end),
                text.rfind(". ", search_from, max_end),
                text.rfind(" ", search_from, max_end),
            ]
            boundary = max(candidates)
            if boundary > start:
                end = boundary + (2 if text[boundary : boundary + 2] == ". " else 0)

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break

        next_start = max(end - chunk_overlap, start + 1)
        start = next_start

    return chunks


def chunk_markdown(
    markdown: str,
    *,
    source_path: str,
    document_name: str,
    category: str,
    source_modified: str,
    indexed_at: str,
    document_hash: str,
    chunk_size: int,
    chunk_overlap: int,
    language: str = "cs",
) -> list[Chunk]:
    chunks: list[Chunk] = []
    chunk_index = 0

    for section in parse_markdown_sections(markdown):
        for text in split_text(section.text, chunk_size, chunk_overlap):
            chunks.append(
                Chunk(
                    text=text,
                    source_path=source_path,
                    document_name=document_name,
                    section_path=section.section_path,
                    category=category,
                    chunk_index=chunk_index,
                    chunk_id=make_chunk_id(source_path, section.section_path, chunk_index),
                    language=language,
                    source_modified=source_modified,
                    indexed_at=indexed_at,
                    document_hash=document_hash,
                )
            )
            chunk_index += 1

    return chunks
