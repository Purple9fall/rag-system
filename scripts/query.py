"""Hoi dap: python scripts/query.py "cau hoi" --file-type pdf --tag hop-dong"""
import argparse
from datetime import datetime

from rag.config import load_settings
from rag.factory import build_funnel
from rag.generation.answer import build_llm, generate_answer
from rag.models import SearchFilters


def main() -> None:
    p = argparse.ArgumentParser(description="Truy van RAG (filter -> hybrid -> rerank)")
    p.add_argument("question")
    p.add_argument("--file-type", nargs="*", dest="file_types")
    p.add_argument("--language", nargs="*", dest="languages")
    p.add_argument("--tag", nargs="*", dest="tags")
    p.add_argument("--file-name", nargs="*", dest="file_names")
    p.add_argument("--after", type=datetime.fromisoformat, help="YYYY-MM-DD")
    p.add_argument("--before", type=datetime.fromisoformat, help="YYYY-MM-DD")
    p.add_argument("--top-k", type=int, default=None)
    p.add_argument("--no-answer", action="store_true", help="Chi in ket qua truy xuat")
    args = p.parse_args()

    settings = load_settings()
    funnel = build_funnel(settings)
    filters = SearchFilters(
        file_types=args.file_types,
        languages=args.languages,
        tags=args.tags,
        file_names=args.file_names,
        created_after=args.after,
        created_before=args.before,
    )
    result = funnel.search(args.question, filters=filters, final_top_k=args.top_k)

    st = result.stats
    print(
        f"[funnel] docs sau filter={st.candidate_docs} | hybrid={st.hybrid_hits} | "
        f"tra ve={st.returned} | rerank={st.reranked} | "
        f"{ {k: round(v) for k, v in st.timings_ms.items()} } ms\n"
    )
    for i, c in enumerate(result.candidates, start=1):
        score = c.rerank_score if c.rerank_score is not None else c.hybrid_score
        print(f"[{i}] {c.file_name} (chunk {c.chunk_index}, score={score:.4f})")
        print(f"    {c.text[:200].replace(chr(10), ' ')}...\n")

    if not args.no_answer:
        llm = build_llm(settings.llm_model)
        print("=== Tra loi ===")
        print(generate_answer(llm, args.question, result.candidates))


if __name__ == "__main__":
    main()
