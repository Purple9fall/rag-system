"""Human-in-the-loop review helpers for collected document records."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

DECISIONS = {"accepted", "needs_review", "rejected"}


def inspect_record(record: dict, root: Path) -> tuple[str, list[str]]:
    """Return a suggested decision and evidence-based reasons.

    This checks record integrity and provenance only. It deliberately does not
    decide whether a publication is scientifically trustworthy.
    """
    reasons: list[str] = []
    if not record.get("title"):
        reasons.append("missing title")
    if not (record.get("doi") or record.get("arxiv_id") or record.get("url")):
        reasons.append("missing DOI, arXiv ID, and source URL")

    relative = record.get("file_path")
    if not relative:
        reasons.append("no full-text file; metadata-only record")
    else:
        path = (root / relative).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            reasons.append("file path escapes collection root")
        else:
            if not path.is_file():
                reasons.append("full-text file is missing")
            else:
                content = path.read_bytes()
                if len(content) < 500:
                    reasons.append("full-text file is suspiciously small (<500 bytes)")
                if path.suffix.lower() == ".pdf" and not content.startswith(b"%PDF-"):
                    reasons.append("file extension is PDF but content has no PDF signature")

    if record.get("review_required"):
        reasons.append("collection quality score flagged for manual review")
    if record.get("document_type") == "preprint":
        reasons.append("preprint: publication/review status should be checked")
    if not record.get("year"):
        reasons.append("publication year is missing")

    hard_failure = any(
        reason in reasons
        for reason in (
            "file path escapes collection root",
            "full-text file is missing",
            "file extension is PDF but content has no PDF signature",
        )
    )
    return ("rejected" if hard_failure else "needs_review"), reasons


def read_manifest(path: Path) -> list[dict]:
    records: list[dict] = []
    if not path.exists():
        return records
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON on manifest line {line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Manifest line {line_number} is not a JSON object")
        records.append(record)
    return records


def write_manifest(path: Path, records: list[dict]) -> None:
    """Atomically rewrite the JSONL manifest after a review decision."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
