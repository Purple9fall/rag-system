from __future__ import annotations

import uuid
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from ..models import SearchFilters


class PostgresStore:
    """Tang relational: metadata tai lieu, noi dung chunk, loc metadata."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def apply_schema(self, schema_path: Path) -> None:
        sql = schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.execute(sql)

    # ---------- ingest ----------
    def get_document_by_hash(self, sha256: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, file_name FROM documents WHERE sha256 = %s", (sha256,)
            ).fetchone()
        return row

    def add_document(
        self,
        *,
        doc_id: str,
        file_name: str,
        source_path: str,
        file_type: str,
        sha256: str,
        parser: str,
        language: str,
        tags: list[str],
        char_count: int,
        chunks: list[tuple[str, int, str]],  # (chunk_id, chunk_index, text)
    ) -> None:
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO documents
                        (id, file_name, source_path, file_type, sha256, parser,
                         language, tags, char_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::text[], %s)
                    """,
                    (
                        uuid.UUID(doc_id),
                        file_name,
                        source_path,
                        file_type,
                        sha256,
                        parser,
                        language,
                        tags,
                        char_count,
                    ),
                )
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO chunks (id, doc_id, chunk_index, text, char_count)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [
                            (uuid.UUID(cid), uuid.UUID(doc_id), idx, text, len(text))
                            for cid, idx, text in chunks
                        ],
                    )

    def delete_document(self, doc_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM documents WHERE id = %s", (uuid.UUID(doc_id),))

    # ---------- retrieval: tang 1 (filter) ----------
    def filter_doc_ids(self, f: SearchFilters) -> list[str]:
        clauses: list[str] = []
        params: list = []
        if f.file_types:
            clauses.append("file_type = ANY(%s::text[])")
            params.append([t.lower().lstrip(".") for t in f.file_types])
        if f.languages:
            clauses.append("language = ANY(%s::text[])")
            params.append(f.languages)
        if f.tags:
            clauses.append("tags && %s::text[]")
            params.append(f.tags)
        if f.file_names:
            clauses.append("file_name = ANY(%s::text[])")
            params.append(f.file_names)
        if f.created_after:
            clauses.append("created_at >= %s")
            params.append(f.created_after)
        if f.created_before:
            clauses.append("created_at <= %s")
            params.append(f.created_before)

        where = " AND ".join(clauses) if clauses else "TRUE"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT id FROM documents WHERE {where}", params
            ).fetchall()
        return [str(r["id"]) for r in rows]

    # ---------- retrieval: lay noi dung chunk ----------
    def get_chunks(self, chunk_ids: list[str]) -> dict[str, dict]:
        if not chunk_ids:
            return {}
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.doc_id, c.chunk_index, c.text, d.file_name
                FROM chunks c
                JOIN documents d ON d.id = c.doc_id
                WHERE c.id = ANY(%s::uuid[])
                """,
                ([uuid.UUID(c) for c in chunk_ids],),
            ).fetchall()
        return {str(r["id"]): r for r in rows}
