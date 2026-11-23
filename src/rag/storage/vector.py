from __future__ import annotations

from qdrant_client import QdrantClient, models

from ..models import Candidate, ChunkVectors, QueryVectors

DENSE = "dense"
SPARSE = "sparse"


class QdrantStore:
    """Tang vector: dense + sparse trong cung mot collection."""

    def __init__(self, url: str, collection: str, api_key: str | None = None):
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection = collection

    def ensure_collection(self, dense_dim: int) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config={
                    DENSE: models.VectorParams(
                        size=dense_dim, distance=models.Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)
                },
            )
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="doc_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    def upsert(self, items: list[ChunkVectors], batch_size: int = 128) -> None:
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            self.client.upsert(
                collection_name=self.collection,
                points=[
                    models.PointStruct(
                        id=it.chunk_id,
                        vector={
                            DENSE: it.dense,
                            SPARSE: models.SparseVector(
                                indices=it.sparse_indices, values=it.sparse_values
                            ),
                        },
                        payload={"doc_id": it.doc_id, "chunk_index": it.chunk_index},
                    )
                    for it in batch
                ],
                wait=True,
            )

    def delete_by_doc(self, doc_id: str) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="doc_id", match=models.MatchValue(value=doc_id)
                        )
                    ]
                )
            ),
            wait=True,
        )

    # ---------- retrieval: tang 2 (hybrid) ----------
    def hybrid_search(
        self,
        qv: QueryVectors,
        doc_ids: list[str] | None,
        limit: int,
    ) -> list[Candidate]:
        flt = None
        if doc_ids is not None:
            flt = models.Filter(
                must=[
                    models.FieldCondition(
                        key="doc_id", match=models.MatchAny(any=doc_ids)
                    )
                ]
            )
        prefetch_limit = max(limit * 2, limit)
        response = self.client.query_points(
            collection_name=self.collection,
            prefetch=[
                models.Prefetch(
                    query=qv.dense, using=DENSE, limit=prefetch_limit, filter=flt
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=qv.sparse_indices, values=qv.sparse_values
                    ),
                    using=SPARSE,
                    limit=prefetch_limit,
                    filter=flt,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return [
            Candidate(
                chunk_id=str(p.id),
                doc_id=str((p.payload or {}).get("doc_id", "")),
                chunk_index=int((p.payload or {}).get("chunk_index", 0)),
                hybrid_score=float(p.score),
            )
            for p in response.points
        ]
