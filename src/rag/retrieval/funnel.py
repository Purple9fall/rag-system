from __future__ import annotations

import time
from typing import Protocol

from ..models import (
    Candidate,
    FunnelResult,
    FunnelStats,
    QueryVectors,
    SearchFilters,
)


class MetadataStore(Protocol):
    def filter_doc_ids(self, f: SearchFilters) -> list[str]: ...
    def get_chunks(self, chunk_ids: list[str]) -> dict[str, dict]: ...


class VectorStore(Protocol):
    def hybrid_search(
        self, qv: QueryVectors, doc_ids: list[str] | None, limit: int
    ) -> list[Candidate]: ...


class QueryEncoder(Protocol):
    def encode_query(self, query: str) -> QueryVectors: ...


class Reranker(Protocol):
    def rerank(
        self, query: str, candidates: list[Candidate], top_k: int
    ) -> list[Candidate]: ...


class RetrievalFunnel:
    """Phieu truy xuat: filter -> hybrid search -> rerank.

    1. Filter  : PostgreSQL thu hep tap tai lieu theo metadata.
    2. Hybrid  : Qdrant dense + sparse, hop nhat bang RRF, chi trong tap da loc.
    3. Rerank  : cross-encoder cham lai top-N, lay top-K cuoi.
    """

    def __init__(
        self,
        metadata: MetadataStore,
        vectors: VectorStore,
        encoder: QueryEncoder,
        reranker: Reranker | None,
        hybrid_top_k: int = 50,
        final_top_k: int = 5,
    ):
        self.metadata = metadata
        self.vectors = vectors
        self.encoder = encoder
        self.reranker = reranker
        self.hybrid_top_k = hybrid_top_k
        self.final_top_k = final_top_k

    def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        final_top_k: int | None = None,
    ) -> FunnelResult:
        top_k = final_top_k or self.final_top_k
        timings: dict[str, float] = {}

        # Tang 1: filter
        t0 = time.perf_counter()
        doc_ids: list[str] | None = None
        if filters is not None and not filters.is_empty():
            doc_ids = self.metadata.filter_doc_ids(filters)
        timings["filter"] = (time.perf_counter() - t0) * 1000

        if doc_ids is not None and len(doc_ids) == 0:
            return FunnelResult(
                candidates=[],
                stats=FunnelStats(
                    candidate_docs=0,
                    hybrid_hits=0,
                    returned=0,
                    reranked=False,
                    timings_ms=timings,
                ),
            )

        # Tang 2: hybrid search
        t0 = time.perf_counter()
        qv = self.encoder.encode_query(query)
        hits = self.vectors.hybrid_search(qv, doc_ids, self.hybrid_top_k)
        timings["hybrid"] = (time.perf_counter() - t0) * 1000

        # Lay noi dung chunk tu PostgreSQL (bo qua chunk mo coi)
        chunk_map = self.metadata.get_chunks([h.chunk_id for h in hits])
        candidates: list[Candidate] = []
        for hit in hits:
            row = chunk_map.get(hit.chunk_id)
            if row is None:
                continue
            hit.text = row["text"]
            hit.file_name = row["file_name"]
            candidates.append(hit)

        # Tang 3: rerank
        t0 = time.perf_counter()
        reranked = False
        if self.reranker is not None and candidates:
            final = self.reranker.rerank(query, candidates, top_k)
            reranked = True
        else:
            final = candidates[:top_k]
        timings["rerank"] = (time.perf_counter() - t0) * 1000

        return FunnelResult(
            candidates=final,
            stats=FunnelStats(
                candidate_docs=None if doc_ids is None else len(doc_ids),
                hybrid_hits=len(candidates),
                returned=len(final),
                reranked=reranked,
                timings_ms=timings,
            ),
        )
