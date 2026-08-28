from __future__ import annotations

import uuid

from family_kb_ai.chunker import chunk_markdown, parse_markdown_sections, split_text
from family_kb_ai.models import make_chunk_id


def test_markdown_sections_preserve_heading_hierarchy() -> None:
    markdown = """# Zavlažování
Úvod.

## Záhon F
Text záhonu.

### Montáž hadice
Černá PE hadice šla obtížně nasadit na spojku.
Pomohlo mírné nahřátí konce hadice.
"""

    sections = parse_markdown_sections(markdown)

    assert [section.section_path for section in sections] == [
        ("Zavlažování",),
        ("Zavlažování", "Záhon F"),
        ("Zavlažování", "Záhon F", "Montáž hadice"),
    ]
    assert "mírné nahřátí" in sections[-1].text


def test_heading_inside_fenced_code_is_not_treated_as_section() -> None:
    markdown = """# Dokument
```text
## Toto není nadpis
```
Po kódu.
"""

    sections = parse_markdown_sections(markdown)

    assert len(sections) == 1
    assert sections[0].section_path == ("Dokument",)
    assert "## Toto není nadpis" in sections[0].text


def test_long_section_is_split_with_configured_limit_and_overlap() -> None:
    text = " ".join(f"slovo{i}" for i in range(150))

    chunks = split_text(text, chunk_size=180, chunk_overlap=30)

    assert len(chunks) > 1
    assert all(len(chunk) <= 180 for chunk in chunks)


def test_chunk_id_is_deterministic_and_qdrant_uuid_compatible() -> None:
    first = make_chunk_id(
        "02_ZAHRADA/ZAVLAHA.md", ("Zavlažování", "Záhon F"), 4
    )
    second = make_chunk_id(
        "02_ZAHRADA/ZAVLAHA.md", ("Zavlažování", "Záhon F"), 4
    )

    assert first == second
    assert str(uuid.UUID(first)) == first


def test_chunk_markdown_keeps_section_path_and_stable_ids() -> None:
    kwargs = dict(
        source_path="02_ZAHRADA/ZAVLAHA.md",
        document_name="ZAVLAHA",
        category="02_ZAHRADA",
        source_modified="2026-08-28T10:00:00+00:00",
        indexed_at="2026-08-28T12:00:00+00:00",
        document_hash="abc",
        chunk_size=1000,
        chunk_overlap=100,
    )
    markdown = "# Zavlažování\n## Záhon F\n### Montáž hadice\nPomohlo nahřátí hadice."

    first = chunk_markdown(markdown, **kwargs)
    second = chunk_markdown(markdown, **kwargs)

    assert first[0].section_path == ("Zavlažování", "Záhon F", "Montáž hadice")
    assert first[0].chunk_id == second[0].chunk_id
