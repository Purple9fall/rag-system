"""Report how many full text records each topic has collected."""
import json
from pathlib import Path

def topic_coverage(manifest: Path, topic_ids: list[str]) -> dict[str, int]:
    counts = dict.fromkeys(topic_ids, 0)
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            topic = entry.get("topic_id")
            if topic in counts and entry.get("file_path"):
                counts[topic] += 1
    return counts
