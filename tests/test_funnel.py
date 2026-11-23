from rag.models import Candidate, QueryVectors, SearchFilters
from rag.retrieval.funnel import RetrievalFunnel


class FakeMetadata:
    def __init__(self, doc_ids, chunks):
        self._doc_ids = doc_ids
        self._chunks = chunks
        self.filter_calls = 0

    def filter_doc_ids(self, f):
        self.filter_calls += 1
        return self._doc_ids

    def get_chunks(self, chunk_ids):
        return {c: self._chunks[c] for c in chunk_ids if c in self._chunks}


class FakeVectors:
    def __init__(self, hits):
        self._hits = hits
        self.calls = []

    def hybrid_search(self, qv, doc_ids, limit):
        self.calls.append((doc_ids, limit))
        return [
            Candidate(h.chunk_id, h.doc_id, h.chunk_index, h.hybrid_score)
            for h in self._hits
        ]


class FakeEncoder:
    def encode_query(self, query):
        return QueryVectors([0.0], [1], [1.0])


class ReverseReranker:
    def rerank(self, query, candidates, top_k):
        for i, c in enumerate(candidates):
            c.rerank_score = float(i)
        return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)[:top_k]


def _chunks(*ids):
    return {i: {"text": f"text-{i}", "file_name": f"{i}.pdf"} for i in ids}


def _hits(*ids):
    return [Candidate(i, "d1", n, 1.0 - n * 0.1) for n, i in enumerate(ids)]


def test_empty_filter_result_skips_vector_search():
    vectors = FakeVectors(_hits("a"))
    funnel = RetrievalFunnel(FakeMetadata([], _chunks("a")), vectors, FakeEncoder(), None)
    result = funnel.search("q", SearchFilters(file_types=["pdf"]))
    assert result.candidates == []
    assert result.stats.candidate_docs == 0
    assert vectors.calls == []


def test_no_filters_searches_whole_corpus():
    meta = FakeMetadata(["d1"], _chunks("a", "b"))
    vectors = FakeVectors(_hits("a", "b"))
    funnel = RetrievalFunnel(meta, vectors, FakeEncoder(), None, hybrid_top_k=10)
    result = funnel.search("q", filters=None)
    assert meta.filter_calls == 0
    assert vectors.calls == [(None, 10)]
    assert result.stats.candidate_docs is None


def test_filter_doc_ids_are_passed_to_hybrid_stage():
    meta = FakeMetadata(["d1", "d2"], _chunks("a"))
    vectors = FakeVectors(_hits("a"))
    funnel = RetrievalFunnel(meta, vectors, FakeEncoder(), None)
    result = funnel.search("q", SearchFilters(tags=["x"]))
    assert vectors.calls[0][0] == ["d1", "d2"]
    assert result.stats.candidate_docs == 2


def test_rerank_reorders_and_truncates():
    meta = FakeMetadata(["d1"], _chunks("a", "b", "c"))
    vectors = FakeVectors(_hits("a", "b", "c"))
    funnel = RetrievalFunnel(meta, vectors, FakeEncoder(), ReverseReranker(), final_top_k=2)
    result = funnel.search("q")
    assert [c.chunk_id for c in result.candidates] == ["c", "b"]
    assert result.stats.reranked is True


def test_orphan_chunks_missing_in_postgres_are_dropped():
    meta = FakeMetadata(["d1"], _chunks("a"))
    vectors = FakeVectors(_hits("a", "ghost"))
    funnel = RetrievalFunnel(meta, vectors, FakeEncoder(), None)
    result = funnel.search("q")
    assert [c.chunk_id for c in result.candidates] == ["a"]
    assert result.candidates[0].text == "text-a"
