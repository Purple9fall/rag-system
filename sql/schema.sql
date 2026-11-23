-- Relational layer: metadata cua tai lieu + noi dung chunk.
-- Vector nam o Qdrant, point id == chunks.id.

CREATE TABLE IF NOT EXISTS documents (
    id          UUID PRIMARY KEY,
    file_name   TEXT        NOT NULL,
    source_path TEXT        NOT NULL,
    file_type   TEXT        NOT NULL,
    sha256      CHAR(64)    NOT NULL UNIQUE,
    parser      TEXT        NOT NULL,
    language    TEXT        NOT NULL DEFAULT 'vi',
    tags        TEXT[]      NOT NULL DEFAULT '{}',
    char_count  INTEGER     NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_file_type  ON documents (file_type);
CREATE INDEX IF NOT EXISTS idx_documents_language   ON documents (language);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at);
CREATE INDEX IF NOT EXISTS idx_documents_tags       ON documents USING GIN (tags);

CREATE TABLE IF NOT EXISTS chunks (
    id          UUID PRIMARY KEY,
    doc_id      UUID    NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text        TEXT    NOT NULL,
    char_count  INTEGER NOT NULL,
    UNIQUE (doc_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks (doc_id);
