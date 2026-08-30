import json
import sqlite3

import pytest

from family_kb_ai.search import SearchResult
from family_kb_ai.usage_feedback import UsageFeedbackStore


def _result(number: int = 1) -> SearchResult:
    return SearchResult(
        chunk_id=f"chunk-{number}",
        score=0.8123 - number / 1000,
        source_path=f"02_ZAHRADA/example-{number}.md",
        section_path=("Zahrada", f"Hadice {number}"),
        text=f"Užitečný text číslo {number}.",
    )


def _record_search(store: UsageFeedbackStore, *, result_count: int = 3) -> int:
    return store.record_search(
        query="co dělat když nejde trubka nasunout na spojku?",
        embedding_model="intfloat/multilingual-e5-small",
        qdrant_collection="family_kb",
        top_k=5,
        category="02_ZAHRADA",
        app_version="0.2.3",
        results=[_result(number) for number in range(1, result_count + 1)],
    )


def test_records_multiple_useful_results_and_exports_jsonl(tmp_path):
    db_path = tmp_path / "usage_feedback.db"
    export_path = tmp_path / "usage_feedback.jsonl"
    store = UsageFeedbackStore(db_path)

    search_id = _record_search(store)
    store.record_feedback(search_id, rating=2, useful_ranks=(1, 3))

    count = store.export_jsonl(export_path)
    assert count == 1

    payload = json.loads(export_path.read_text(encoding="utf-8").strip())
    assert payload["query"].startswith("co dělat")
    assert payload["feedback"]["rating"] == 2
    assert payload["feedback"]["useful_ranks"] == [1, 3]
    assert payload["feedback"]["failure_reason"] is None
    assert payload["results"][0]["chunk_id"] == "chunk-1"
    assert payload["results"][0]["section_path"] == ["Zahrada", "Hadice 1"]
    assert "text" not in payload["results"][0]


def test_feedback_stores_failure_reason(tmp_path):
    store = UsageFeedbackStore(tmp_path / "usage_feedback.db")
    search_id = _record_search(store)

    store.record_feedback(
        search_id,
        rating=1,
        useful_ranks=(3,),
        failure_reason="knowledge_gap",
    )

    output = tmp_path / "reason.jsonl"
    store.export_jsonl(output)
    payload = json.loads(output.read_text(encoding="utf-8").strip())

    assert payload["feedback"]["rating"] == 1
    assert payload["feedback"]["useful_ranks"] == [3]
    assert payload["feedback"]["failure_reason"] == "knowledge_gap"


def test_feedback_update_replaces_useful_ranks(tmp_path):
    store = UsageFeedbackStore(tmp_path / "usage_feedback.db")
    search_id = _record_search(store)

    store.record_feedback(search_id, rating=1, useful_ranks=(2,))
    store.record_feedback(search_id, rating=2, useful_ranks=(1, 2, 3))

    output = tmp_path / "updated.jsonl"
    store.export_jsonl(output)
    payload = json.loads(output.read_text(encoding="utf-8").strip())

    assert payload["feedback"]["rating"] == 2
    assert payload["feedback"]["useful_ranks"] == [1, 2, 3]


def test_feedback_update_can_preserve_existing_useful_ranks(tmp_path):
    store = UsageFeedbackStore(tmp_path / "usage_feedback.db")
    search_id = _record_search(store)

    store.record_feedback(search_id, rating=1, useful_ranks=(1, 3))
    store.record_feedback(search_id, rating=2, note="corrected later")

    output = tmp_path / "preserved.jsonl"
    store.export_jsonl(output)
    payload = json.loads(output.read_text(encoding="utf-8").strip())

    assert payload["feedback"]["rating"] == 2
    assert payload["feedback"]["useful_ranks"] == [1, 3]
    assert payload["feedback"]["failure_reason"] is None
    assert payload["feedback"]["note"] == "corrected later"


def test_successful_correction_clears_failure_reason(tmp_path):
    store = UsageFeedbackStore(tmp_path / "usage_feedback.db")
    search_id = _record_search(store)

    store.record_feedback(
        search_id,
        rating=0,
        failure_reason="retrieval_failure",
    )
    store.record_feedback(search_id, rating=2)

    output = tmp_path / "cleared.jsonl"
    store.export_jsonl(output)
    payload = json.loads(output.read_text(encoding="utf-8").strip())

    assert payload["feedback"]["rating"] == 2
    assert payload["feedback"]["failure_reason"] is None


def test_export_can_include_retrieved_text(tmp_path):
    store = UsageFeedbackStore(tmp_path / "usage_feedback.db")
    _record_search(store, result_count=1)

    output = tmp_path / "with_text.jsonl"
    store.export_jsonl(output, include_text=True)

    payload = json.loads(output.read_text(encoding="utf-8").strip())
    assert payload["results"][0]["text"].startswith("Užitečný")


def test_feedback_validation(tmp_path):
    store = UsageFeedbackStore(tmp_path / "usage_feedback.db")
    search_id = _record_search(store, result_count=1)

    with pytest.raises(ValueError, match="rating"):
        store.record_feedback(search_id, rating=3)

    with pytest.raises(ValueError, match="no result"):
        store.record_feedback(search_id, rating=1, useful_ranks=(2,))

    with pytest.raises(ValueError, match="failure_reason"):
        store.record_feedback(search_id, rating=0, failure_reason="other")

    with pytest.raises(ValueError, match="only valid"):
        store.record_feedback(search_id, rating=2, failure_reason="knowledge_gap")

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
        feedback_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(feedback)")
        }

    assert {
        "searches",
        "results",
        "feedback",
        "feedback_results",
    }.issubset(tables)
    assert "failure_reason" in feedback_columns


def test_v12a_selected_rank_is_migrated_to_useful_results(tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                query TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                qdrant_collection TEXT NOT NULL,
                top_k INTEGER NOT NULL,
                category TEXT,
                app_version TEXT NOT NULL
            );
            CREATE TABLE results (
                search_id INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                chunk_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                section_path TEXT NOT NULL,
                score REAL NOT NULL,
                text TEXT NOT NULL,
                PRIMARY KEY (search_id, rank)
            );
            CREATE TABLE feedback (
                search_id INTEGER PRIMARY KEY,
                rating INTEGER NOT NULL,
                selected_rank INTEGER,
                note TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        connection.execute(
            """
            INSERT INTO searches (
                id, created_at, query, embedding_model,
                qdrant_collection, top_k, category, app_version
            )
            VALUES (1, '2026-08-29T09:00:00+02:00', 'žebřík',
                    'model', 'family_kb', 5, NULL, '0.2.0')
            """
        )
        for rank in range(1, 6):
            connection.execute(
                """
                INSERT INTO results (
                    search_id, rank, chunk_id, source_path,
                    section_path, score, text
                )
                VALUES (1, ?, ?, ?, '[]', ?, ?)
                """,
                (
                    rank,
                    f"chunk-{rank}",
                    f"source-{rank}.md",
                    0.9 - rank / 100,
                    f"text-{rank}",
                ),
            )
        connection.execute(
            """
            INSERT INTO feedback (
                search_id, rating, selected_rank, note, created_at
            )
            VALUES (1, 2, 4, NULL, '2026-08-29T09:01:00+02:00')
            """
        )

    store = UsageFeedbackStore(db_path)
    output = tmp_path / "legacy.jsonl"
    store.export_jsonl(output)
    payload = json.loads(output.read_text(encoding="utf-8").strip())

    assert payload["feedback"]["rating"] == 2
    assert payload["feedback"]["useful_ranks"] == [4]
    assert payload["feedback"]["failure_reason"] is None

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(feedback)")}
    assert "failure_reason" in columns
