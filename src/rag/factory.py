from __future__ import annotations

from .config import Settings
from .embeddings.encoders import Encoder
from .ingestion.pipeline import Ingestor
from .retrieval.funnel import RetrievalFunnel
from .retrieval.reranker import CrossEncoderReranker
from .storage.relational import PostgresStore
from .storage.vector import QdrantStore


def build_stores(s: Settings) -> tuple[PostgresStore, QdrantStore]:
    return (
        PostgresStore(s.database_url),
        QdrantStore(s.qdrant_url, s.qdrant_collection, s.qdrant_api_key),
    )


def build_encoder(s: Settings) -> Encoder:
    return Encoder(s.dense_model, s.sparse_model, s.embed_batch_size, s.device)


def build_ingestor(s: Settings) -> Ingestor:
    metadata, vectors = build_stores(s)
    return Ingestor(
        metadata,
        vectors,
        build_encoder(s),
        s.chunk_size,
        s.chunk_overlap,
        s.default_language,
    )


def build_funnel(s: Settings) -> RetrievalFunnel:
    metadata, vectors = build_stores(s)
    reranker = CrossEncoderReranker(s.rerank_model, s.device) if s.enable_rerank else None
    return RetrievalFunnel(
        metadata=metadata,
        vectors=vectors,
        encoder=build_encoder(s),
        reranker=reranker,
        hybrid_top_k=s.hybrid_top_k,
        final_top_k=s.final_top_k,
    )
