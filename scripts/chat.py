"""Hoi dap lien tuc, chi tai model mot lan: python scripts/chat.py

Lenh trong luc chat:
  /tag a b      loc theo tag (khong tham so = bo loc)
  /type pdf     loc theo loai file (khong tham so = bo loc)
  /clear        bo tat ca bo loc
  /noanswer     bat/tat buoc sinh cau tra loi (chi xem ket qua truy xuat)
  /exit         thoat
"""
from rag.config import load_settings
from rag.factory import build_funnel
from rag.generation.answer import build_llm, generate_answer
from rag.models import SearchFilters


def describe(f: SearchFilters) -> str:
    parts = []
    if f.tags:
        parts.append(f"tag={f.tags}")
    if f.file_types:
        parts.append(f"type={f.file_types}")
    return ", ".join(parts) if parts else "khong loc"


def main() -> None:
    settings = load_settings()
    print("Dang tai model (chi mot lan)...")
    funnel = build_funnel(settings)
    llm = build_llm(settings.llm_model)
    filters = SearchFilters()
    answer_on = True
    print("San sang. Go cau hoi, hoac /exit de thoat.")

    while True:
        try:
            line = input(f"\n[{describe(filters)}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line in {"/exit", "/quit"}:
            break
        if line.startswith("/tag"):
            filters.tags = line.split()[1:] or None
            continue
        if line.startswith("/type"):
            filters.file_types = line.split()[1:] or None
            continue
        if line == "/clear":
            filters = SearchFilters()
            continue
        if line == "/noanswer":
            answer_on = not answer_on
            print("Sinh cau tra loi:", "bat" if answer_on else "tat")
            continue

        result = funnel.search(line, filters=filters)
        st = result.stats
        print(
            f"[funnel] docs sau filter={st.candidate_docs} | hybrid={st.hybrid_hits} | "
            f"tra ve={st.returned} | rerank={st.reranked} | "
            f"{ {k: round(v) for k, v in st.timings_ms.items()} } ms\n"
        )
        for i, c in enumerate(result.candidates, start=1):
            score = c.rerank_score if c.rerank_score is not None else c.hybrid_score
            print(f"[{i}] {c.file_name} (chunk {c.chunk_index}, score={score:.4f})")

        if answer_on:
            try:
                print("\n=== Tra loi ===")
                print(generate_answer(llm, line, result.candidates))
            except Exception as exc:  # noqa: BLE001
                print(f"Loi LLM: {exc}")


if __name__ == "__main__":
    main()