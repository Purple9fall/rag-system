import json
from dataclasses import asdict
from pathlib import Path

def retrieve(question: str, config: dict, topic_id: str | None = None, top_k: int | None = None, answer: bool = False, funnel=None) -> dict:
    from rag.config import load_settings
    from rag.factory import build_funnel
    from rag.generation.answer import build_llm, generate_answer
    from rag.models import SearchFilters

    if topic_id and topic_id not in config["topics"]:
        raise ValueError(f"Unknown topic: {topic_id}")
    settings = load_settings()
    tags = [config["settings"]["collection_id"]]
    if topic_id:
        tags.append(topic_id)
    result = (funnel or build_funnel(settings)).search(question, filters=SearchFilters(tags=tags), final_top_k=top_k)
    output = {"question": question, "stats": asdict(result.stats), "candidates": [asdict(candidate) for candidate in result.candidates]}
    if answer:
        output["answer"] = generate_answer(build_llm(settings.llm_model), question, result.candidates) if result.candidates else "Không tìm thấy tài liệu phù hợp với câu hỏi và bộ lọc đã chọn."
    return output

def evaluate(dataset: Path, config: dict, top_k: int = 5) -> dict:
    from rag.config import load_settings
    from rag.factory import build_funnel

    if top_k < 1:
        raise ValueError("top_k must be positive")
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("Evaluation dataset is empty")
    funnel = build_funnel(load_settings())
    details = []
    for index, row in enumerate(rows, 1):
        if not row.get("question") or not row.get("relevant_files"):
            raise ValueError(f"Row {index} needs question and nonempty relevant_files")
        output = retrieve(row["question"], config, row.get("topic_id"), top_k=top_k, funnel=funnel)
        gold = set(row["relevant_files"])
        ranks = [rank for rank, item in enumerate(output["candidates"], 1) if item["file_name"] in gold]
        details.append({"question": row["question"], "topic_id": row.get("topic_id"), "hit": bool(ranks), "reciprocal_rank": 1 / min(ranks) if ranks else 0, "retrieved_files": [item["file_name"] for item in output["candidates"]]})
    return {"queries": len(details), f"hit_rate_at_{top_k}": sum(x["hit"] for x in details) / len(details), f"mrr_at_{top_k}": sum(x["reciprocal_rank"] for x in details) / len(details), "details": details}
