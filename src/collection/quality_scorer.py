import re
from datetime import date
from .relevance_filter import matches as _matches

def score_record(record: dict, topic: dict, rules: dict) -> int:
    title = record.get("title", "")
    abstract = record.get("abstract", "")
    body = record.get("body", "")
    core = topic["core_terms"]
    if rules["topic_relevance"]["require_core_term"] and not _matches(
        " ".join((title, abstract, body)), core
    ):
        return 0
    relevance = rules["topic_relevance"]
    score = sum(
        points if _matches(text, core + topic["context_terms"]) else 0
        for text, points in (
            (title, relevance["title_match_points"]),
            (abstract, relevance["abstract_match_points"]),
            (body, relevance["body_match_points"]),
        )
    )
    if _matches(" ".join((title, abstract)), topic["exclude_terms"]):
        score -= relevance["negative_term_penalty"]

    authority = rules["source_authority"]
    kind = record["document_type"]
    score += (
        authority["official_documentation_points"] if kind == "technical_documentation"
        else authority["preprint_points"] if kind == "preprint"
        else authority["peer_reviewed_points"]
    )
    depth = rules["technical_depth"]
    text = " ".join((abstract, body)).lower()
    score += depth["has_method_or_equations_points"] if _matches(text, ["method", "simulation", "equation", "solver"]) else 0
    score += depth["has_parameters_or_geometry_points"] if _matches(text, ["width", "length", "geometry", "parameter", "nm", "µm"]) else 0
    score += depth["has_results_or_benchmarks_points"] if _matches(text, ["result", "measured", "loss", "benchmark"]) else 0
    citations = record.get("citation_count")
    if citations is not None:
        score += round(rules["weights"]["citation_signal"] * min(1, max(0, citations) / rules["citation_signal"]["full_points_at_citations"]))
    else:
        score += rules["citation_signal"]["missing_count_points"]
    year = record.get("year")
    recency = rules["recency"]
    if year:
        age = max(0, date.today().year - int(year))
        score += (
            rules["weights"]["recency"] if age <= recency["full_points_within_years"]
            else rules["weights"]["recency"] // 2 if age <= recency["half_points_within_years"]
            else recency["older_points"]
        )
    else:
        score += recency["missing_date_points"]
    return max(0, min(rules["scale"], score))

