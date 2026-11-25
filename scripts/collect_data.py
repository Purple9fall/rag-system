"""Discover and download permitted documents for 01_photonicICfundamental."""
import argparse
import json
import logging
from pathlib import Path

from collection.pipeline import Collector
from collection.config_loader import DEFAULT_CONFIG, load_collection


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect photonic IC documents")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--topic", action="append", dest="topics", help="Repeat to select topics")
    parser.add_argument("--dry-run", action="store_true", help="Search and download in memory, without writing files")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stats = Collector(load_collection(args.config)).run(args.topics, args.dry_run)
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
