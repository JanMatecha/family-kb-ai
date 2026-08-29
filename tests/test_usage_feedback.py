import json
import sqlite3

import pytest

from family_kb_ai.search import SearchResult
from family_kb_ai.usage_feedback import UsageFeedbackStore


def _result() -> SearchResult:
    return SearchResult(
        chunk_id="chunk-1",
        score=0.8123,
        source_path="02_ZAHRADA/example.md",
        section_path=("Zahrada", "Hadice"),
        text="Hadice jde obtížně nasadit na fitinku.",
    )


def test_records_search_feedback_and_exports_jsonl(tmp_path):
    db_path = tmp_path / "usage_feedback.db"
    export_path = tmp_path / "usage_feedback.jsonl"
    store = UsageFeedbackStore(db_path)

    search_id = store.record_search(
        query="co dělat když nejde trubka nasunout na spojku?",
        embedding_model="intfloat/multilingual-e5-small",
        qdrant_collection="family_kb",
        top_k=5,
        category="02_ZAHRADA",
        app_version="0.2.0",
        results=[_result()],
    )
    store.record_feedback(search_id, rating=2, selected_rank=1)

    count = store.export_jsonl(export_path)
    assert count == 1

    payload = json.loads(export_path.read_text(encoding="utf-8").strip())
    assert payload["query"].startswith("co dělat")
    assert payload["feedback"]["rating"] == 2
    assert payload["feedback"]["selected_rank"] == 1
    assert payload["results"][0]["chunk_id"] == "chunk-1"
    assert payload["results"][0]["section_path"] == ["Zahrada", "Hadice"]
    assert "text" not in payload["results"][0]


def test_export_can_include_retrieved_text(tmp_path):
    store = UsageFeedbackStore(tmp_path / "usage_feedback.db")
    store.record_search(
        query="test",
        embedding_model="model",
        qdrant_collection="collection",
        top_k=1,
        category=None,
        app_version="0.2.0",
        results=[_result()],
    )

    output = tmp_path / "with_text.jsonl"
    store.export_jsonl(output, include_text=True)

    payload = json.loads(output.read_text(encoding="utf-8").strip())
    assert payload["results"][0]["text"].startswith("Hadice")


def test_feedback_validation(tmp_path):
    store = UsageFeedbackStore(tmp_path / "usage_feedback.db")
    search_id = store.record_search(
        query="test",
        embedding_model="model",
        qdrant_collection="collection",
        top_k=5,
        category=None,
        app_version="0.2.0",
        results=[_result()],
    )

    with pytest.raises(ValueError, match="rating"):
        store.record_feedback(search_id, rating=3)

    with pytest.raises(ValueError, match="no result"):
        store.record_feedback(search_id, rating=1, selected_rank=2)

    with pytest.raises(ValueError, match="Unknown search_id"):
        store.record_feedback(9999, rating=0)


def test_database_schema_is_created(tmp_path):
    db_path = tmp_path / "usage_feedback.db"
    UsageFeedbackStore(db_path)

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {"searches", "results", "feedback"}.issubset(tables)
