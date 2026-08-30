from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


DEFAULT_EMBEDDING_REVISIONS: dict[str, str] = {
    "intfloat/multilingual-e5-small": "614241f622f53c4eeff9890bdc4f31cfecc418b3",
}


@dataclass(frozen=True)
class Settings:
    kb_path: Path
    qdrant_url: str
    qdrant_collection: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    embedding_revision: str | None = None


def load_settings(path: str | Path = "config.yaml") -> Settings:
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. Copy config.example.yaml to config.yaml first."
        )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    required = {
        "kb_path",
        "qdrant_url",
        "qdrant_collection",
        "embedding_model",
        "chunk_size",
        "chunk_overlap",
        "top_k",
    }
    missing = sorted(required - raw.keys())
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")

    embedding_model = str(raw["embedding_model"])
    if "embedding_revision" in raw:
        raw_revision = raw["embedding_revision"]
        embedding_revision = (
            str(raw_revision).strip() if raw_revision is not None else None
        )
        if not embedding_revision:
            embedding_revision = None
    else:
        embedding_revision = DEFAULT_EMBEDDING_REVISIONS.get(embedding_model)

    settings = Settings(
        kb_path=Path(str(raw["kb_path"])).expanduser(),
        qdrant_url=str(raw["qdrant_url"]),
        qdrant_collection=str(raw["qdrant_collection"]),
        embedding_model=embedding_model,
        chunk_size=int(raw["chunk_size"]),
        chunk_overlap=int(raw["chunk_overlap"]),
        top_k=int(raw["top_k"]),
        embedding_revision=embedding_revision,
    )

    if settings.chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if settings.chunk_overlap < 0 or settings.chunk_overlap >= settings.chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")
    if settings.top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    return settings
