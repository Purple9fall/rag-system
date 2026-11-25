"""Nap tai lieu: python scripts/ingest.py data/raw --tags hop-dong 2025 --language vi"""
import argparse
import logging
from pathlib import Path

from rag.config import load_settings
from rag.factory import build_ingestor


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest tai lieu vao RAG")
    p.add_argument("path", type=Path, nargs="?", help="File hoac thu muc")
    p.add_argument("--collection", action="store_true", help="Nap cac file trong collection manifest")
    p.add_argument("--topic", action="append", help="Loc topic khi dung --collection")
    p.add_argument("--tags", nargs="*", default=[], help="Nhan gan cho tai lieu")
    p.add_argument("--language", default=None, help="Ma ngon ngu (mac dinh theo .env)")
    p.add_argument("--force", action="store_true", help="Nap lai ke ca file da co")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.collection:
        if args.path:
            p.error("Khong truyen path khi dung --collection")
        from collection.config_loader import load_collection
        from ingestion.collection import ingest_collection

        print(ingest_collection(load_collection(), args.topic, args.force))
        return
    if args.topic:
        p.error("--topic chi dung voi --collection")
    if args.path is None:
        p.error("Can path hoac --collection")
    if not args.path.exists():
        raise SystemExit(f"Khong tim thay: {args.path}")

    ingestor = build_ingestor(load_settings())
    summary = ingestor.ingest_path(
        args.path, tags=args.tags, language=args.language, force=args.force
    )
    print(summary)


if __name__ == "__main__":
    main()
