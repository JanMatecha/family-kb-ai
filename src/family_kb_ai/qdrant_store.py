from __future__ import annotations

from collections.abc import Sequence

from qdrant_client import QdrantClient, models

from .models import Chunk


class QdrantStore:
    def __init__(self, url: str, collection_name: str) -> None:
        self.collection_name = collection_name
        self.client = QdrantClient(url=url)

    def recreate_collection(self, vector_size: int) -> None:
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        if not chunks:
            return

        points = [
            models.PointStruct(
                id=chunk.chunk_id,
                vector=list(vector),
                payload=chunk.payload(),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

    def search(
        self,
        query_vector: Sequence[float],
        *,
        limit: int,
        category: str | None = None,
    ) -> list[models.ScoredPoint]:
        query_filter = None
        if category:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="category",
                        match=models.MatchValue(value=category),
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=list(query_vector),
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return list(response.points)
