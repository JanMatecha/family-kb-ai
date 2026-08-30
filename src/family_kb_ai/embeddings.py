from __future__ import annotations

from collections.abc import Sequence

from .config import DEFAULT_EMBEDDING_REVISIONS


def resolve_model_revision(model_name: str, revision: str | None = None) -> str | None:
    if revision is not None:
        return revision
    return DEFAULT_EMBEDDING_REVISIONS.get(model_name)


class LocalEmbedder:
    """Small wrapper that keeps model revision and E5 formatting in one place."""

    def __init__(self, model_name: str, revision: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.revision = resolve_model_revision(model_name, revision)
        self._uses_e5_prefixes = "e5" in model_name.lower()
        self._model = SentenceTransformer(model_name, revision=self.revision)

    @property
    def dimension(self) -> int:
        get_dimension = getattr(self._model, "get_embedding_dimension", None)
        if callable(get_dimension):
            dimension = get_dimension()
        else:
            dimension = self._model.get_sentence_embedding_dimension()
        if dimension is None:
            raise RuntimeError("Embedding model did not report its vector dimension")
        return int(dimension)

    def embed_chunks(self, texts: Sequence[str]) -> list[list[float]]:
        prepared = [self._format_passage(text) for text in texts]
        vectors = self._model.encode(
            prepared,
            normalize_embeddings=True,
            show_progress_bar=len(prepared) > 32,
        )
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode(
            self._format_query(text),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector.tolist()

    def _format_passage(self, text: str) -> str:
        return f"passage: {text}" if self._uses_e5_prefixes else text

    def _format_query(self, text: str) -> str:
        return f"query: {text}" if self._uses_e5_prefixes else text


def chunk_embedding_text(section_path: tuple[str, ...], text: str) -> str:
    context = " > ".join(part for part in section_path if part)
    return f"{context}\n\n{text}" if context else text
