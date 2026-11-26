"""Deterministic acceptance rules for collected documents."""
from __future__ import annotations

import re
from urllib.parse import urlparse


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _trusted_documentation_source(record: dict, source: dict, policy: dict) -> bool:
    source_id = source.get("id", "")
    if source_id not in policy.get("trusted_documentation_sources", []):
        return False
    host = (urlparse(record.get("url", "")).hostname or "").lower()
    allowed = [domain.lower().lstrip(".") for domain in source.get("allowed_domains", [])]
    return any(host == domain or host.endswith("." + domain) for domain in allowed)


def validate_automatically(
    record: dict,
    source: dict,
    score: int,
    constraints: dict,
    has_full_text: bool,
) -> tuple[str, list[str]]:
    """Return accepted/needs_review/rejected and concise machine-readable reasons.

    Uncertain provenance is quarantined as needs_review. Only records that meet
    all configured acceptance conditions are eligible for collection ingestion.
    """
    policy = constraints["automatic_validation"]
    reasons: list[str] = []

    if record.get("is_retracted") and constraints["quality"].get("reject_retracted", True):
        return "rejected", ["document is marked retracted"]
    threshold = (
        policy.get("minimum_documentation_score", policy["minimum_acceptance_score"])
        if record.get("document_type") == "technical_documentation"
        else policy["minimum_acceptance_score"]
    )
    if score < threshold:
        reasons.append("score below automatic acceptance threshold")
    if not has_full_text and policy.get("require_full_text", True):
        reasons.append("full text unavailable")

    document_type = record.get("document_type")
    if document_type == "technical_documentation":
        if not _trusted_documentation_source(record, source, policy):
            reasons.append("documentation source/domain is not allowlisted")
    elif document_type == "preprint":
        reasons.append("preprint publication status is not independently verified")
    else:
        publishers = {_normalize(item) for item in policy.get("trusted_publishers", [])}
        publisher = _normalize(record.get("publisher", ""))
        if not publisher or publisher not in publishers:
            reasons.append("publisher is not in the trusted publisher allowlist")
        if not record.get("container_title"):
            reasons.append("journal or conference venue is missing")
        if policy.get("require_doi_for_scholarly", True) and not record.get("doi"):
            reasons.append("DOI is missing")

    if reasons:
        return "needs_review", reasons
    return "accepted", ["all automatic acceptance rules passed"]
