from __future__ import annotations

from dataclasses import dataclass
import hashlib
import uuid


_CHUNK_NAMESPACE = uuid.UUID("6d3faeae-fdf5-4d83-8da7-b9d39586fb54")


@dataclass(frozen=True)
class Chunk:
    text: str
    source_path: str
    document_name: str
    section_path: tuple[str, ...]
    category: str
    chunk_index: int
    chunk_id: str
    language: str
    source_modified: str
    indexed_at: str
    document_hash: str

    def payload(self) -> dict[str, object]:
        return {
            "text": self.text,
            "source_path": self.source_path,
            "document_name": self.document_name,
            "section_path": list(self.section_path),
            "category": self.category,
            "chunk_index": self.chunk_index,
            "chunk_id": self.chunk_id,
            "language": self.language,
            "source_modified": self.source_modified,
            "indexed_at": self.indexed_at,
            "document_hash": self.document_hash,
        }


def make_chunk_id(source_path: str, section_path: tuple[str, ...], chunk_index: int) -> str:
    identity = "\n".join((source_path, " > ".join(section_path), str(chunk_index)))
    return str(uuid.uuid5(_CHUNK_NAMESPACE, identity))


def hash_document(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
