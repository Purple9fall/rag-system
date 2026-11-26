import json
import logging
from pathlib import Path

def ingest_collection(config: dict, topic_ids: list[str] | None = None, force: bool = False) -> dict[str, int]:
    from rag.config import load_settings
    from rag.factory import build_ingestor

    manifest = config["manifest_file"]
    if not manifest.exists():
        raise FileNotFoundError(f"Collection manifest not found: {manifest}")
    selected = set(topic_ids or config["topics"])
    unknown = selected - set(config["topics"])
    if unknown:
        raise ValueError(f"Unknown topics: {sorted(unknown)}")
    ingestor = build_ingestor(load_settings())
    result = {"ingested": 0, "skipped": 0, "failed": 0}
    files: dict[Path, set[str]] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry["topic_id"] not in selected or not entry.get("file_path"):
            continue
        path = config["root"] / entry["file_path"]
        files.setdefault(path, set()).add(entry["topic_id"])
    for path, topic_tags in files.items():
        if not path.is_file():
            logging.error("Missing collected file: %s", path)
            result["failed"] += 1
            continue
        status = ingestor.ingest_file(path, tags=[config["settings"]["collection_id"], *sorted(topic_tags)], language="en", force=force)
        result[status] += 1
    return result
