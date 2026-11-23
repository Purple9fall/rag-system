"""Nap tai lieu: python scripts/ingest.py data/raw --tags hop-dong 2025 --language vi"""
import argparse
import logging
from pathlib import Path

from rag.config import load_settings
from rag.factory import build_ingestor


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest tai lieu vao RAG")
    p.add_argument("path", type=Path, help="File hoac thu muc")
    p.add_argument("--tags", nargs="*", default=[], help="Nhan gan cho tai lieu")
    p.add_argument("--language", default=None, help="Ma ngon ngu (mac dinh theo .env)")
    p.add_argument("--force", action="store_true", help="Nap lai ke ca file da co")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not args.path.exists():
        raise SystemExit(f"Khong tim thay: {args.path}")

    ingestor = build_ingestor(load_settings())
    summary = ingestor.ingest_path(
        args.path, tags=args.tags, language=args.language, force=args.force
    )
    print(summary)


if __name__ == "__main__":
    main()
