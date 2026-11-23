from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path

from ..embeddings.encoders import Encoder
from ..models import ChunkVectors
from ..storage.relational import PostgresStore
from ..storage.vector import QdrantStore
from .chunker import chunk_text
from .parsers import parse_file

log = logging.getLogger(__name__)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


class Ingestor:
    def __init__(
        self,
        metadata: PostgresStore,
        vectors: QdrantStore,
        encoder: Encoder,
        chunk_size: int,
        chunk_overlap: int,
        default_language: str = "vi",
    ):
        self.metadata = metadata
        self.vectors = vectors
        self.encoder = encoder
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.default_language = default_language

    def ingest_file(
        self,
        path: Path,
        tags: list[str] | None = None,
        language: str | None = None,
        force: bool = False,
    ) -> str:
        """Tra ve 'ingested' | 'skipped' | 'failed'."""
        digest = sha256_of(path)
        existing = self.metadata.get_document_by_hash(digest)
        if existing is not None:
            if not force:
                log.info("Bo qua (da co): %s", path.name)
                return "skipped"
            old_id = str(existing["id"])
            self.vectors.delete_by_doc(old_id)
            self.metadata.delete_document(old_id)

        try:
            parsed = parse_file(path)
            chunks = chunk_text(parsed.text, self.chunk_size, self.chunk_overlap)
            if not chunks:
                raise ValueError("Khong tao duoc chunk nao")
        except Exception as exc:  # noqa: BLE001
            log.error("Loi doc %s: %s", path.name, exc)
            return "failed"

        vecs = self.encoder.encode_documents(chunks)
        doc_id = str(uuid.uuid4())
        chunk_ids = [str(uuid.uuid4()) for _ in chunks]

        self.metadata.add_document(
            doc_id=doc_id,
            file_name=path.name,
            source_path=str(path),
            file_type=path.suffix.lower().lstrip("."),
            sha256=digest,
            parser=parsed.parser,
            language=language or self.default_language,
            tags=tags or [],
            char_count=len(parsed.text),
            chunks=[(cid, i, text) for i, (cid, text) in enumerate(zip(chunk_ids, chunks))],
        )
        try:
            self.vectors.upsert(
                [
                    ChunkVectors(
                        chunk_id=cid,
                        doc_id=doc_id,
                        chunk_index=i,
                        dense=v.dense,
                        sparse_indices=v.sparse_indices,
                        sparse_values=v.sparse_values,
                    )
                    for i, (cid, v) in enumerate(zip(chunk_ids, vecs))
                ]
            )
        except Exception:
            # Giu hai DB dong bo: xoa ban ghi PostgreSQL neu ghi Qdrant that bai
            self.metadata.delete_document(doc_id)
            raise

        log.info("OK: %s (%d chunk, parser=%s)", path.name, len(chunks), parsed.parser)
        return "ingested"

    def ingest_path(
        self,
        path: Path,
        tags: list[str] | None = None,
        language: str | None = None,
        force: bool = False,
    ) -> dict[str, int]:
        files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        summary = {"ingested": 0, "skipped": 0, "failed": 0}
        for f in files:
            if f.name == ".gitkeep":
                continue
            summary[self.ingest_file(f, tags=tags, language=language, force=force)] += 1
        return summary
