from __future__ import annotations

from ..models import QueryVectors


class DocVectors:
    __slots__ = ("dense", "sparse_indices", "sparse_values")

    def __init__(self, dense, sparse_indices, sparse_values):
        self.dense = dense
        self.sparse_indices = sparse_indices
        self.sparse_values = sparse_values


class Encoder:
    """Dense (sentence-transformers) + sparse BM25 (fastembed)."""

    def __init__(
        self,
        dense_model: str,
        sparse_model: str,
        batch_size: int = 16,
        device: str | None = None,
    ):
        from fastembed import SparseTextEmbedding
        from sentence_transformers import SentenceTransformer

        self.dense_model = SentenceTransformer(dense_model, device=device)
        self.sparse_model = SparseTextEmbedding(model_name=sparse_model)
        self.batch_size = batch_size

    @property
    def dim(self) -> int:
        return int(self.dense_model.get_sentence_embedding_dimension())

    def encode_documents(self, texts: list[str]) -> list[DocVectors]:
        dense = self.dense_model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()
        sparse = list(self.sparse_model.embed(texts))
        return [
            DocVectors(d, s.indices.tolist(), s.values.tolist())
            for d, s in zip(dense, sparse)
        ]

    def encode_query(self, query: str) -> QueryVectors:
        dense = self.dense_model.encode(
            [query], normalize_embeddings=True, show_progress_bar=False
        )[0].tolist()
        sparse = list(self.sparse_model.query_embed(query))[0]
        return QueryVectors(
            dense=dense,
            sparse_indices=sparse.indices.tolist(),
            sparse_values=sparse.values.tolist(),
        )
