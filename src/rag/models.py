from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SearchFilters:
    """Dieu kien loc o tang 1 cua phieu (chay tren PostgreSQL)."""

    file_types: list[str] | None = None
    languages: list[str] | None = None
    tags: list[str] | None = None
    file_names: list[str] | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None

    def is_empty(self) -> bool:
        return not any(
            [
                self.file_types,
                self.languages,
                self.tags,
                self.file_names,
                self.created_after,
                self.created_before,
            ]
        )


@dataclass
class QueryVectors:
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]


@dataclass
class ChunkVectors:
    chunk_id: str
    doc_id: str
    chunk_index: int
    dense: list[float]
    sparse_indices: list[int]
    sparse_values: list[float]


@dataclass
class Candidate:
    chunk_id: str
    doc_id: str
    chunk_index: int
    hybrid_score: float
    text: str = ""
    file_name: str = ""
    rerank_score: float | None = None


@dataclass
class FunnelStats:
    candidate_docs: int | None  # None = khong loc (toan bo kho)
    hybrid_hits: int
    returned: int
    reranked: bool
    timings_ms: dict[str, float] = field(default_factory=dict)


@dataclass
class FunnelResult:
    candidates: list[Candidate]
    stats: FunnelStats
