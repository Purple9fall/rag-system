"""Inspect collected records and record human review decisions.

Examples:
  python scripts/review_collection.py
  python scripts/review_collection.py --set doi:10.1234/example --decision accepted --reviewer "Your Name"
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from collection.config_loader import DEFAULT_CONFIG, load_collection
from collection.intake_review import DECISIONS, file_sha256, inspect_record, read_manifest, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Review collected RAG documents")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--show-all", action="store_true", help="Include records already reviewed")
    parser.add_argument("--set", dest="identity", help="Record identity from the manifest")
    parser.add_argument("--decision", choices=sorted(DECISIONS))
    parser.add_argument("--reviewer", help="Name/initials of the human reviewer")
    parser.add_argument("--note", default="", help="Short review rationale")
    args = parser.parse_args()

    if args.identity and (not args.decision or not args.reviewer):
        parser.error("--set requires --decision and --reviewer")
    if not args.identity and (args.decision or args.reviewer or args.note):
        parser.error("--decision, --reviewer, and --note require --set")

    config = load_collection(args.config)
    records = read_manifest(config["manifest_file"])
    if args.identity:
        matches = [r for r in records if r.get("identity") == args.identity]
        if len(matches) != 1:
            parser.error(f"Expected one record with identity {args.identity!r}; found {len(matches)}")
        record = matches[0]
        suggestion, reasons = inspect_record(record, config["root"])
        if args.decision == "accepted" and suggestion == "rejected":
            parser.error("Cannot accept a record with a broken/missing/out-of-root file: " + "; ".join(reasons))
        record["review_status"] = args.decision
        record["reviewed_by"] = args.reviewer
        record["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        record["review_note"] = args.note
        write_manifest(config["manifest_file"], records)
        print(f"Saved {args.decision}: {args.identity}")
        return

    root = config["root"]
    hashes: dict[str, str] = {}
    for record in records:
        file_path = record.get("file_path")
        if not file_path:
            continue
        path = (root / file_path).resolve()
        try:
            path.relative_to(root.resolve())
            if path.is_file():
                digest = file_sha256(path)
                if digest in hashes:
                    record.setdefault("_duplicate_of", hashes[digest])
                else:
                    hashes[digest] = record.get("identity", "<unknown identity>")
        except (OSError, ValueError):
            pass

    pending_count = 0
    for record in records:
        status = record.get("review_status")
        if status and not args.show_all:
            continue
        suggested, reasons = inspect_record(record, root)
        if record.get("_duplicate_of"):
            suggested = "rejected"
            reasons.append(f"duplicate file content of {record['_duplicate_of']}")
        if not status:
            pending_count += 1
        print(f"[{status or suggested}] {record.get('identity', '<no identity>')} — {record.get('title', '<no title>')}")
        print(f"  type={record.get('document_type', 'unknown')} year={record.get('year', 'unknown')} source={record.get('source_id', 'unknown')}")
        if reasons:
            for reason in reasons:
                print(f"  - {reason}")
        elif status:
            print(f"  reviewer={record.get('reviewed_by', '?')} note={record.get('review_note', '')}")
    print(f"\n{pending_count} record(s) awaiting human decision. Suggestions do not establish scientific credibility.")


if __name__ == "__main__":
    main()
