"""Canonical identity and previously collected topic associations."""
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

def identity(record: dict) -> str:
    if record.get("doi"):
        return "doi:" + record["doi"].lower().removeprefix("https://doi.org/")
    if record.get("arxiv_id"):
        return "arxiv:" + record["arxiv_id"]
    return "url:" + record["url"].split("#", 1)[0]

def load_existing(manifest: Path) -> tuple[dict[str, dict], set[tuple[str, str]]]:
    existing: dict[str, dict] = {}
    pairs: set[tuple[str, str]] = set()
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                existing[entry["identity"]] = entry
                pairs.add((entry["identity"], entry["topic_id"]))
            except (KeyError, json.JSONDecodeError):
                log.warning("Skipping malformed manifest line")
    return existing, pairs
