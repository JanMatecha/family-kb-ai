from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

from family_kb_ai.config import load_settings


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
    assert settings.chunk_size == 1200
    assert settings.chunk_overlap == 150
    assert settings.top_k == 5
