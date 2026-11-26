import json
import logging
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

from .crawler import parse_page
from .downloader import SourceAccessDenied

log = logging.getLogger(__name__)

class SearchMixin:
    def _discover_crossref(self, source: dict, query: str, limit: int) -> list[dict]:
        url = source["endpoint"] + "?" + urllib.parse.urlencode({source["search_parameter"]: query, "rows": min(limit, source["max_results_per_request"])})
        data, _, _ = self._fetch(url, source)
        items = json.loads(data)["message"]["items"]
        records = []
        for item in items:
            kind = {"journal-article": "journal_article", "proceedings-article": "conference_paper"}.get(item.get("type"))
            if not kind:
                continue
            parts = item.get("published", {}).get("date-parts", [[]])[0]
            retracted = any(update.get("type") == "retraction" for update in item.get("update-to", []))
            records.append({"title": (item.get("title") or [""])[0], "abstract": BeautifulSoup(item.get("abstract", ""), "html.parser").get_text(" ", strip=True), "url": item.get("URL", ""), "doi": item.get("DOI", ""), "year": parts[0] if parts else None, "citation_count": item.get("is-referenced-by-count"), "publisher": item.get("publisher", ""), "container_title": (item.get("container-title") or [""])[0], "document_type": kind, "is_retracted": retracted, "metadata_only": True})
        return records

    def _discover_arxiv(self, source: dict, query: str, limit: int) -> list[dict]:
        expression = query if query.startswith("all:") else " AND ".join("all:" + word for word in query.split())
        url = source["endpoint"] + "?" + urllib.parse.urlencode({source["search_parameter"]: expression, "start": 0, "max_results": min(limit, source["max_results_per_request"])})
        data, _, _ = self._fetch(url, source)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        records = []
        for entry in ET.fromstring(data).findall("a:entry", ns):
            link = next((x.attrib["href"] for x in entry.findall("a:link", ns) if x.attrib.get("title") == "pdf"), None)
            if link:
                pdf_url = urllib.parse.urlparse(link)
                if pdf_url.scheme == "http" and pdf_url.hostname == "arxiv.org":
                    link = urllib.parse.urlunparse(pdf_url._replace(scheme="https"))
            published = entry.findtext("a:published", default="", namespaces=ns)
            paper_url = entry.findtext("a:id", default="", namespaces=ns)
            records.append({"title": entry.findtext("a:title", default="", namespaces=ns).strip(), "abstract": entry.findtext("a:summary", default="", namespaces=ns).strip(), "url": paper_url, "download_url": link, "arxiv_id": paper_url.rstrip("/").split("/")[-1], "year": int(published[:4]) if published[:4].isdigit() else None, "document_type": "preprint"})
        return records

    def _discover_openalex(self, source: dict, query: str, limit: int) -> list[dict]:
        url = source["endpoint"] + "?" + urllib.parse.urlencode({source["search_parameter"]: query, "per-page": min(limit, source["max_results_per_request"])})
        data, _, _ = self._fetch(url, source)
        records = []
        for item in json.loads(data).get("results", []):
            kind = {"article": "journal_article", "proceedings-article": "conference_paper", "preprint": "preprint"}.get(item.get("type"))
            if not kind:
                continue
            inverted = item.get("abstract_inverted_index") or {}
            words = [(position, word) for word, positions in inverted.items() for position in positions]
            abstract = " ".join(word for _, word in sorted(words))
            primary_source = (item.get("primary_location") or {}).get("source") or {}
            records.append({"title": item.get("display_name", ""), "abstract": abstract, "url": item.get("id", ""), "doi": (item.get("doi") or "").removeprefix("https://doi.org/"), "year": item.get("publication_year"), "citation_count": item.get("cited_by_count"), "publisher": primary_source.get("host_organization_name", ""), "container_title": primary_source.get("display_name", ""), "document_type": kind, "is_retracted": item.get("is_retracted", False), "metadata_only": True})
        return records

    def _discover_pages(self, source: dict) -> list[dict]:
        queue = [(url, 0) for url in source["seed_urls"]]
        seen: set[str] = set()
        records = []
        while queue:
            url, depth = queue.pop(0)
            if url in seen or len(records) >= self.settings["run"]["max_records_per_topic_per_source"]:
                continue
            seen.add(url)
            parsed_url = urllib.parse.urlparse(url)
            if parsed_url.hostname not in source["allowed_domains"] or "/articles/" not in parsed_url.path:
                continue
            try:
                data, mime, final_url = self._fetch(url, source)
            except SourceAccessDenied as exc:
                log.warning("Stopping page crawl for %s: %s", parsed_url.hostname, exc)
                break
            except (ValueError, OSError, urllib.error.URLError) as exc:
                log.warning("Skipping page %s: %s", url, exc)
                continue
            if mime != "text/html":
                continue
            page = parse_page(data)
            records.append({"title": page.title, "body": page.text, "url": final_url, "document_type": "technical_documentation", "content": data, "extension": ".html"})
            if source["follow_links"] and depth < source["max_depth"]:
                for href in page.links:
                    target = urllib.parse.urljoin(final_url, href).split("#", 1)[0]
                    if target not in seen:
                        queue.append((target, depth + 1))
        return records
