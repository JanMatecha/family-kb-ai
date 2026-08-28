from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .embeddings import LocalEmbedder
from .qdrant_store import QdrantStore


@dataclass(frozen=True)
class SearchResult:
    score: float
    source_path: str
    section_path: tuple[str, ...]
    text: str


def search(
    settings: Settings,
    query: str,
    *,
    top_k: int | None = None,
    category: str | None = None,
) -> list[SearchResult]:
    limit = top_k if top_k is not None else settings.top_k
    if limit <= 0:
        raise ValueError("top_k must be greater than 0")

    embedder = LocalEmbedder(settings.embedding_model)
    store = QdrantStore(settings.qdrant_url, settings.qdrant_collection)
    points = store.search(embedder.embed_query(query), limit=limit, category=category)

    results: list[SearchResult] = []
    for point in points:
        payload = point.payload or {}
        results.append(
            SearchResult(
                score=float(point.score),
                source_path=str(payload.get("source_path", "")),
                section_path=tuple(payload.get("section_path", []) or []),
                text=str(payload.get("text", "")),
            )
        )
    return results
