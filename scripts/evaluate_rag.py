"""Evaluate retrieval using JSONL rows with question and relevant file names."""
import argparse
import json
from pathlib import Path

from collection.config_loader import DEFAULT_CONFIG, load_collection
from retrieval.collection import evaluate

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval for the photonic corpus")
    parser.add_argument("dataset", type=Path, help="JSONL: {question, relevant_files, optional topic_id}")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(args.dataset, load_collection(args.config), args.top_k)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
