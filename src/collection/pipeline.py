from __future__ import annotations
import hashlib
import json
import logging
import os
import shutil
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from .config_loader import load_collection
from .downloader import Downloader, SourceAccessDenied
from .search import SearchMixin
from .deduplicator import identity as record_identity, load_existing
from .relevance_filter import valid_record
from .quality_scorer import score_record
from .auto_validation import validate_automatically
from .metadata import append_jsonl
from .coverage_checker import topic_coverage

log = logging.getLogger(__name__)

class Collector(Downloader, SearchMixin):
    def run(self, topic_ids: list[str] | None = None, dry_run: bool = False) -> dict[str, int]:
        topics = self.config["topics"]
        selected = topic_ids or list(topics)
        unknown = set(selected) - set(topics)
        if unknown:
            raise ValueError(f"Unknown topics: {sorted(unknown)}")
        manifest = self.config["manifest_file"]
        raw_dir = self.config["raw_dir"]
        existing, seen_topic_pairs = load_existing(manifest)
        stats = {"discovered": 0, "selected": 0, "auto_accepted": 0, "needs_review": 0, "rejected": 0, "saved": 0, "downloaded": 0, "skipped": 0, "failed": 0}
        downloaded = 0
        if not dry_run:
            manifest.parent.mkdir(parents=True, exist_ok=True)
            raw_dir.mkdir(parents=True, exist_ok=True)
        for source in self.config["sources"]:
            if not source["enabled"]:
                continue
            allowed_topics = set(source.get("allowed_topics", selected))
            relevant_topics = [topic_id for topic_id in selected if topic_id in allowed_topics]
            if not relevant_topics:
                continue
            page_records = self._discover_pages(source) if source["kind"] == "seed_pages" else None
            source_denied = False
            for topic_id in relevant_topics:
                topic = topics[topic_id]
                queries = [None] if page_records is not None else (
                    topic.get("arxiv_queries", topic["search_queries"])
                    if source["id"] == "arxiv" else topic["search_queries"]
                )
                for query in queries:
                    try:
                        if page_records is not None:
                            records = page_records
                        elif source["id"] == "arxiv":
                            records = self._discover_arxiv(source, query, self.settings["run"]["max_records_per_topic_per_source"])
                        elif source["id"] == "crossref":
                            records = self._discover_crossref(source, query, self.settings["run"]["max_records_per_topic_per_source"])
                        elif source["id"] == "openalex":
                            records = self._discover_openalex(source, query, self.settings["run"]["max_records_per_topic_per_source"])
                        else:
                            raise ValueError(f"Unsupported source: {source['id']}")
                    except SourceAccessDenied as exc:
                        log.warning("Stopping source %s: %s", source["id"], exc)
                        stats["failed"] += 1
                        source_denied = True
                        break
                    except (ValueError, OSError, urllib.error.URLError, ET.ParseError, json.JSONDecodeError) as exc:
                        log.warning("Discovery failed for %s/%s: %s", source["id"], topic_id, exc)
                        stats["failed"] += 1
                        continue
                    for record in records:
                        stats["discovered"] += 1
                        if not valid_record(record, topic, self.constraints):
                            stats["rejected"] += 1
                            continue
                        score = score_record(record, topic, self.config["scoring"])
                        if score < self.config["scoring"]["selection"]["minimum_score"]:
                            stats["rejected"] += 1
                            continue
                        stats["selected"] += 1
                        identity = record_identity(record)
                        if identity in existing:
                            pair = (identity, topic_id)
                            if pair in seen_topic_pairs:
                                previous_file = existing[identity].get("file_path")
                                topic_file = previous_file
                                if previous_file:
                                    source_file = self.config["root"] / previous_file
                                    target_file = raw_dir / topic_id / self._category(topic, record["title"]) / source_file.name
                                    if not dry_run:
                                        self._link_topic_file(source_file, target_file)
                                    topic_file = str(target_file.relative_to(self.config["root"]))
                                has_full_text = bool(previous_file and (self.config["root"] / previous_file).is_file())
                                decision, reasons = validate_automatically(
                                    {**existing[identity], **record}, source, score,
                                    self.constraints, has_full_text,
                                )
                                existing_entry = {
                                    **existing[identity],
                                    "topic_id": topic_id,
                                    "file_path": topic_file,
                                    "score": score,
                                    "review_status": decision,
                                    "review_required": decision != "accepted",
                                    "validation_method": "automatic",
                                    "validation_policy_version": 1,
                                    "validation_reasons": reasons,
                                }
                                if not dry_run:
                                    append_jsonl(manifest, existing_entry)
                                existing[identity] = existing_entry
                                stats["auto_accepted" if decision == "accepted" else "rejected" if decision == "rejected" else "needs_review"] += 1
                                stats["skipped"] += 1
                            else:
                                entry = {**existing[identity], "topic_id": topic_id, "score": score}
                                previous_file = entry.get("file_path")
                                if previous_file:
                                    source_file = self.config["root"] / previous_file
                                    category = self._category(topic, record["title"])
                                    target_file = raw_dir / topic_id / category / source_file.name
                                    if source_file.is_file():
                                        if not dry_run:
                                            self._link_topic_file(source_file, target_file)
                                        entry["file_path"] = str(target_file.relative_to(self.config["root"]))
                                decision, reasons = validate_automatically(
                                    {**entry, **record}, source, score, self.constraints,
                                    bool(entry.get("file_path") and (self.config["root"] / entry["file_path"]).is_file()),
                                )
                                entry.update({
                                    "review_status": decision,
                                    "review_required": decision != "accepted",
                                    "validation_method": "automatic",
                                    "validation_policy_version": 1,
                                    "validation_reasons": reasons,
                                })
                                if not dry_run:
                                    append_jsonl(manifest, entry)
                                seen_topic_pairs.add(pair)
                                stats["saved"] += 1
                                stats["auto_accepted" if decision == "accepted" else "rejected" if decision == "rejected" else "needs_review"] += 1
                            continue
                        if downloaded >= self.settings["run"]["max_downloads_per_run"] and not record.get("metadata_only"):
                            break
                        content = record.pop("content", None)
                        extension = record.pop("extension", ".pdf")
                        if not record.get("metadata_only") and content is None:
                            download_url = record.get("download_url")
                            if not download_url:
                                stats["skipped"] += 1
                                continue
                            try:
                                content, mime, _ = self._fetch(download_url, source)
                                if mime not in self.constraints["download"]["allowed_content_types"] or (mime == "application/pdf" and not content.startswith(b"%PDF-")):
                                    raise ValueError("Invalid or unsupported full text")
                                extension = ".pdf" if mime == "application/pdf" else ".html"
                            except (ValueError, OSError, urllib.error.URLError) as exc:
                                log.warning("Download failed for %s: %s", download_url, exc)
                                stats["failed"] += 1
                                continue
                        if content is not None and len(content) < self.constraints["quality"]["min_body_characters"]:
                            stats["skipped"] += 1
                            continue
                        output = None
                        if content is not None:
                            digest = hashlib.sha256(content).hexdigest()
                            category = self._category(topic, record["title"])
                            output = raw_dir / topic_id / category / f"{digest}{extension}"
                        entry = {k: v for k, v in record.items() if k not in {"content", "extension", "body"}}
                        entry.update({"identity": identity, "topic_id": topic_id, "source_id": source["id"], "score": score, "file_path": str(output.relative_to(self.config["root"])) if output else None})
                        decision, reasons = validate_automatically(
                            entry, source, score, self.constraints, output is not None,
                        )
                        entry.update({
                            "review_status": decision,
                            "review_required": decision != "accepted",
                            "validation_method": "automatic",
                            "validation_policy_version": 1,
                            "validation_reasons": reasons,
                        })
                        if decision == "rejected":
                            stats["rejected"] += 1
                            continue
                        if not dry_run:
                            if output and not output.exists():
                                output.parent.mkdir(parents=True, exist_ok=True)
                                output.write_bytes(content)
                            append_jsonl(manifest, entry)
                        existing[identity] = entry
                        seen_topic_pairs.add((identity, topic_id))
                        stats["saved"] += 1
                        stats["auto_accepted" if decision == "accepted" else "needs_review"] += 1
                        if output:
                            downloaded += 1
                            stats["downloaded"] += 1
                if source_denied:
                    break
        if not dry_run:
            coverage = topic_coverage(manifest, list(topics))
            empty_topics = [topic_id for topic_id in selected if coverage[topic_id] == 0]
            if empty_topics:
                log.warning("No full-text documents for topics: %s", ", ".join(empty_topics))
            append_jsonl(self.config["collection_log_file"], {"timestamp": datetime.now(timezone.utc).isoformat(), "collection_id": self.settings["collection_id"], "topics": selected, "stats": stats, "coverage": coverage})
        return stats

    @staticmethod
    def _category(topic: dict, title: str) -> str:
        if not topic.get("subtopics"):
            return ""
        title = title.lower()
        return next(
            (subtopic["directory"] for subtopic in topic["subtopics"] if any(term.lower() in title for term in subtopic["match_terms"])),
            topic["subtopics"][0]["directory"],
        )

    @staticmethod
    def _link_topic_file(source_file, target_file) -> None:
        if not source_file.is_file() or target_file == source_file or target_file.exists():
            return
        target_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source_file, target_file)
        except OSError:
            shutil.copy2(source_file, target_file)
