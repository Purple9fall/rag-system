from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value.strip() == "" else value.strip()


@dataclass(frozen=True)
class Settings:
    database_url: str
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    dense_model: str
    dense_dim: int
    sparse_model: str
    rerank_model: str
    enable_rerank: bool
    device: str | None
    embed_batch_size: int
    chunk_size: int
    chunk_overlap: int
    hybrid_top_k: int
    final_top_k: int
    llm_model: str
    default_language: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        database_url=_str("DATABASE_URL", "postgresql://rag:rag@localhost:5432/rag"),
        qdrant_url=_str("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
        qdrant_collection=_str("QDRANT_COLLECTION", "rag_chunks"),
        dense_model=_str("DENSE_MODEL", "BAAI/bge-m3"),
        dense_dim=int(_str("DENSE_DIM", "1024")),
        sparse_model=_str("SPARSE_MODEL", "Qdrant/bm25"),
        rerank_model=_str("RERANK_MODEL", "BAAI/bge-reranker-v2-m3"),
        enable_rerank=_bool("ENABLE_RERANK", True),
        device=os.getenv("DEVICE") or None,
        embed_batch_size=int(_str("EMBED_BATCH_SIZE", "16")),
        chunk_size=int(_str("CHUNK_SIZE", "512")),
        chunk_overlap=int(_str("CHUNK_OVERLAP", "64")),
        hybrid_top_k=int(_str("HYBRID_TOP_K", "50")),
        final_top_k=int(_str("FINAL_TOP_K", "5")),
        llm_model=_str("LLM_MODEL", "gpt-4o-mini"),
        default_language=_str("DEFAULT_LANGUAGE", "vi"),
    )
