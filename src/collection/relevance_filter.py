import re

def matches(text: str, terms: list[str]) -> bool:
    return any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I) for term in terms)


def valid_record(record: dict, topic: dict, constraints: dict) -> bool:
    eligibility = constraints["eligibility"]
    if record["document_type"] not in eligibility["document_types"] or not record.get("title"):
        return False
    if not record.get("abstract") and not record.get("body"):
        return False
    if not matches(" ".join((record["title"], record.get("abstract", ""), record.get("body", ""))), topic["core_terms"]):
        return False
    year = record.get("year")
    if year and ((eligibility["published_from_year"] and year < eligibility["published_from_year"]) or (eligibility["published_through_year"] and year > eligibility["published_through_year"])):
        return False
    return True

