from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

from family_kb_ai.config import load_settings


PINNED_E5_SMALL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"


def test_load_settings(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        """kb_path: C:/kb
qdrant_url: http://localhost:6333
qdrant_collection: family_kb
embedding_model: intfloat/multilingual-e5-small
chunk_size: 1200
chunk_overlap: 150
top_k: 5
""",
        encoding="utf-8",
    )

    settings = load_settings(config)

    assert settings.qdrant_collection == "family_kb"
    assert settings.embedding_model == "intfloat/multilingual-e5-small"
    assert settings.embedding_revision == PINNED_E5_SMALL_REVISION
    assert settings.chunk_size == 1200
    assert settings.chunk_overlap == 150
    assert settings.top_k == 5


def test_explicit_embedding_revision_overrides_default(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        """kb_path: C:/kb
qdrant_url: http://localhost:6333
qdrant_collection: family_kb
embedding_model: intfloat/multilingual-e5-small
embedding_revision: custom-revision
chunk_size: 1200
chunk_overlap: 150
top_k: 5
""",
        encoding="utf-8",
    )

    settings = load_settings(config)

    assert settings.embedding_revision == "custom-revision"
