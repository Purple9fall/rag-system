from __future__ import annotations

from pathlib import Path

import yaml


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "configs/collection/settings.yaml"


def load_collection(config_path: Path = DEFAULT_CONFIG) -> dict:
    """Load the shared configuration and topic files relative to the project root."""
    config_path = config_path.resolve()
    root = config_path.parents[2]
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if settings.get("version") != 1 or not settings.get("enabled"):
        raise ValueError("Collection config must be enabled and version 1")
    paths = settings["paths"]

    def read(name: str) -> dict:
        return yaml.safe_load((root / paths[name]).read_text(encoding="utf-8"))

    topics_dir = root / paths["topics_dir"]
    topics = {
        item["id"]: item
        for path in sorted(topics_dir.glob("*.yaml"))
        if (item := yaml.safe_load(path.read_text(encoding="utf-8"))).get("enabled")
    }
    if any(t["collection_id"] != settings["collection_id"] for t in topics.values()):
        raise ValueError("Topic collection_id mismatch")
    scoring = read("scoring_file")
    if sum(scoring["weights"].values()) != scoring["scale"]:
        raise ValueError("Scoring weights must sum to scale")
    return {
        "root": root,
        "settings": settings,
        "sources": read("sources_file")["sources"],
        "constraints": read("constraints_file"),
        "scoring": scoring,
        "topics": topics,
        "raw_dir": root / paths["raw_dir"],
        "manifest_file": root / paths["manifest_file"],
        "collection_log_file": root / paths["collection_log_file"],
        "temp_dir": root / paths["temp_dir"],
    }
