from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .chunker import chunk_markdown
from .config import Settings
from .embeddings import LocalEmbedder, chunk_embedding_text
from .models import Chunk, hash_document
from .qdrant_store import QdrantStore


def collect_chunks(settings: Settings, indexed_at: str) -> list[Chunk]:
    kb_path = settings.kb_path
    if not kb_path.is_dir():
        raise FileNotFoundError(f"KB path is not a directory: {kb_path}")

    chunks: list[Chunk] = []
    for path in sorted(kb_path.rglob("*.md")):
        if not path.is_file():
            continue

        markdown = path.read_text(encoding="utf-8-sig", errors="replace")
        relative = path.relative_to(kb_path).as_posix()
        parts = Path(relative).parts
        category = parts[0] if len(parts) > 1 else ""
        source_modified = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat()

        chunks.extend(
            chunk_markdown(
                markdown,
                source_path=relative,
                document_name=path.stem,
                category=category,
                source_modified=source_modified,
                indexed_at=indexed_at,
                document_hash=hash_document(markdown),
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
        )

    return chunks


def index_chunks(
    chunks: Sequence[Chunk],
    *,
    embedder: LocalEmbedder,
    store: QdrantStore,
    batch_size: int = 64,
) -> None:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    store.recreate_collection(embedder.dimension)
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        texts = [chunk_embedding_text(chunk.section_path, chunk.text) for chunk in batch]
        vectors = embedder.embed_chunks(texts)
        store.upsert(batch, vectors)


def ingest(settings: Settings, *, recreate: bool) -> tuple[int, int]:
    if not recreate:
        raise ValueError("V1 only supports explicit full reindex. Use ingest --recreate.")

    indexed_at = datetime.now(timezone.utc).isoformat()
    chunks = collect_chunks(settings, indexed_at)

    embedder = LocalEmbedder(settings.embedding_model)
    store = QdrantStore(settings.qdrant_url, settings.qdrant_collection)
    index_chunks(chunks, embedder=embedder, store=store)

    document_count = len({chunk.source_path for chunk in chunks})
    return document_count, len(chunks)
