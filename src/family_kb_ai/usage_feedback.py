from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .search import SearchResult


DEFAULT_DB_PATH = Path("usage_feedback.db")
DEFAULT_EXPORT_PATH = Path("evaluation/usage_feedback.jsonl")


class UsageFeedbackStore:
    """Local SQLite store for real search queries, results, and user feedback."""

    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    query TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    qdrant_collection TEXT NOT NULL,
                    top_k INTEGER NOT NULL,
                    category TEXT,
                    app_version TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS results (
                    search_id INTEGER NOT NULL,
                    rank INTEGER NOT NULL,
                    chunk_id TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    section_path TEXT NOT NULL,
                    score REAL NOT NULL,
                    text TEXT NOT NULL,
                    PRIMARY KEY (search_id, rank),
                    FOREIGN KEY (search_id) REFERENCES searches(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    search_id INTEGER PRIMARY KEY,
                    rating INTEGER NOT NULL CHECK (rating BETWEEN 0 AND 2),
                    selected_rank INTEGER,
                    note TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (search_id) REFERENCES searches(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_searches_created_at
                ON searches(created_at);
                """
            )

    def record_search(
        self,
        *,
        query: str,
        embedding_model: str,
        qdrant_collection: str,
        top_k: int,
        category: str | None,
        app_version: str,
        results: Sequence["SearchResult"],
    ) -> int:
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")

        created_at = _now()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO searches (
                    created_at,
                    query,
                    embedding_model,
                    qdrant_collection,
                    top_k,
                    category,
                    app_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    query,
                    embedding_model,
                    qdrant_collection,
                    top_k,
                    category,
                    app_version,
                ),
            )
            search_id = int(cursor.lastrowid)

            connection.executemany(
                """
                INSERT INTO results (
                    search_id,
                    rank,
                    chunk_id,
                    source_path,
                    section_path,
                    score,
                    text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        search_id,
                        rank,
                        result.chunk_id,
                        result.source_path,
                        json.dumps(list(result.section_path), ensure_ascii=False),
                        float(result.score),
                        result.text,
                    )
                    for rank, result in enumerate(results, start=1)
                ],
            )

        return search_id

    def record_feedback(
        self,
        search_id: int,
        *,
        rating: int,
        selected_rank: int | None = None,
        note: str | None = None,
    ) -> None:
        if rating not in {0, 1, 2}:
            raise ValueError("rating must be 0, 1, or 2")
        if selected_rank is not None and selected_rank <= 0:
            raise ValueError("selected_rank must be greater than 0")

        with self._connect() as connection:
            search_row = connection.execute(
                "SELECT id FROM searches WHERE id = ?",
                (search_id,),
            ).fetchone()
            if search_row is None:
                raise ValueError(f"Unknown search_id: {search_id}")

            if selected_rank is not None:
                result_row = connection.execute(
                    """
                    SELECT 1
                    FROM results
                    WHERE search_id = ? AND rank = ?
                    """,
                    (search_id, selected_rank),
                ).fetchone()
                if result_row is None:
                    raise ValueError(
                        f"Search {search_id} has no result at rank {selected_rank}"
                    )

            connection.execute(
                """
                INSERT INTO feedback (
                    search_id,
                    rating,
                    selected_rank,
                    note,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(search_id) DO UPDATE SET
                    rating = excluded.rating,
                    selected_rank = excluded.selected_rank,
                    note = excluded.note,
                    created_at = excluded.created_at
                """,
                (search_id, rating, selected_rank, note, _now()),
            )

    def export_jsonl(
        self,
        output_path: str | Path = DEFAULT_EXPORT_PATH,
        *,
        include_text: bool = False,
    ) -> int:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            searches = connection.execute(
                """
                SELECT
                    id,
                    created_at,
                    query,
                    embedding_model,
                    qdrant_collection,
                    top_k,
                    category,
                    app_version
                FROM searches
                ORDER BY id
                """
            ).fetchall()

            with output.open("w", encoding="utf-8", newline="\n") as handle:
                for search_row in searches:
                    search_id = int(search_row["id"])
                    result_rows = connection.execute(
                        """
                        SELECT
                            rank,
                            chunk_id,
                            source_path,
                            section_path,
                            score,
                            text
                        FROM results
                        WHERE search_id = ?
                        ORDER BY rank
                        """,
                        (search_id,),
                    ).fetchall()
                    feedback_row = connection.execute(
                        """
                        SELECT rating, selected_rank, note, created_at
                        FROM feedback
                        WHERE search_id = ?
                        """,
                        (search_id,),
                    ).fetchone()

                    payload = {
                        "search_id": search_id,
                        "timestamp": search_row["created_at"],
                        "query": search_row["query"],
                        "model": search_row["embedding_model"],
                        "collection": search_row["qdrant_collection"],
                        "top_k": int(search_row["top_k"]),
                        "category": search_row["category"],
                        "app_version": search_row["app_version"],
                        "results": [
                            _result_payload(row, include_text=include_text)
                            for row in result_rows
                        ],
                        "feedback": (
                            {
                                "rating": int(feedback_row["rating"]),
                                "selected_rank": feedback_row["selected_rank"],
                                "note": feedback_row["note"],
                                "timestamp": feedback_row["created_at"],
                            }
                            if feedback_row is not None
                            else None
                        ),
                    }
                    handle.write(
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                    )
                    handle.write("\n")

        return len(searches)


def _result_payload(
    row: sqlite3.Row,
    *,
    include_text: bool,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "rank": int(row["rank"]),
        "chunk_id": row["chunk_id"],
        "source_path": row["source_path"],
        "section_path": json.loads(row["section_path"]),
        "score": float(row["score"]),
    }
    if include_text:
        payload["text"] = row["text"]
    return payload


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
