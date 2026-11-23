from __future__ import annotations

from ..models import Candidate


class CrossEncoderReranker:
    """Tang 3: cross-encoder cham diem lai (query, chunk)."""

    def __init__(self, model_name: str, device: str | None = None):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name, device=device, max_length=512)

    def rerank(
        self, query: str, candidates: list[Candidate], top_k: int
    ) -> list[Candidate]:
        if not candidates:
            return []
        scores = self.model.predict([(query, c.text) for c in candidates])
        for cand, score in zip(candidates, scores):
            cand.rerank_score = float(score)
        ranked = sorted(candidates, key=lambda c: c.rerank_score or 0.0, reverse=True)
        return ranked[:top_k]
