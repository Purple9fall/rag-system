from __future__ import annotations

from datetime import datetime
from functools import lru_cache

from fastapi import FastAPI
from pydantic import BaseModel

from ..config import load_settings
from ..factory import build_funnel
from ..generation.answer import build_llm, generate_answer
from ..models import SearchFilters

app = FastAPI(title="RAG API", version="0.1.0")


class FiltersIn(BaseModel):
    file_types: list[str] | None = None
    languages: list[str] | None = None
    tags: list[str] | None = None
    file_names: list[str] | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


class QueryIn(BaseModel):
    question: str
    filters: FiltersIn | None = None
    top_k: int | None = None
    generate: bool = True


@lru_cache(maxsize=1)
def _settings():
    return load_settings()


@lru_cache(maxsize=1)
def _funnel():
    return build_funnel(_settings())


@lru_cache(maxsize=1)
def _llm():
    return build_llm(_settings().llm_model)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/query")
def query(body: QueryIn) -> dict:
    filters = SearchFilters(**body.filters.model_dump()) if body.filters else None
    result = _funnel().search(body.question, filters=filters, final_top_k=body.top_k)
    answer = (
        generate_answer(_llm(), body.question, result.candidates)
        if body.generate
        else None
    )
    return {
        "answer": answer,
        "stats": {
            "candidate_docs": result.stats.candidate_docs,
            "hybrid_hits": result.stats.hybrid_hits,
            "returned": result.stats.returned,
            "reranked": result.stats.reranked,
            "timings_ms": {k: round(v, 1) for k, v in result.stats.timings_ms.items()},
        },
        "sources": [
            {
                "chunk_id": c.chunk_id,
                "doc_id": c.doc_id,
                "file_name": c.file_name,
                "chunk_index": c.chunk_index,
                "hybrid_score": c.hybrid_score,
                "rerank_score": c.rerank_score,
                "text": c.text,
            }
            for c in result.candidates
        ],
    }
