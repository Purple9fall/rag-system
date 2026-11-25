import json
import unittest
import urllib.parse
from collection.pipeline import Collector


class SearchTest(unittest.TestCase):
    def test_crossref_response_mapping(self):
        collector = Collector()
        collector._fetch = lambda url, source: (json.dumps({"message": {"items": [{"type": "journal-article", "title": ["PIC design"], "abstract": "<p>Optical <b>waveguides</b></p>", "DOI": "10.1/x", "published": {"date-parts": [[2024]]}}]}}).encode(), "application/json", url)
        records = collector._discover_crossref({"endpoint": "https://example.org/works", "search_parameter": "query.bibliographic", "max_results_per_request": 10}, "PIC", 10)
        self.assertEqual(records[0]["doi"], "10.1/x")
        self.assertEqual(records[0]["abstract"], "Optical waveguides")

    def test_arxiv_pdf_link_uses_https(self):
        collector = Collector()
        feed = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1234.5678</id><title>Photonic waveguide</title><summary>Guided modes</summary><published>2024-01-01</published><link title="pdf" href="http://arxiv.org/pdf/1234.5678"/></entry></feed>'
        collector._fetch = lambda url, source: (feed, "application/atom+xml", url)
        source = {"endpoint": "https://export.arxiv.org/api/query", "search_parameter": "search_query", "max_results_per_request": 10}
        records = collector._discover_arxiv(source, "photonic waveguide", 10)
        self.assertEqual(records[0]["download_url"], "https://arxiv.org/pdf/1234.5678")

    def test_arxiv_query_keeps_configured_expression(self):
        collector = Collector()
        requested = []
        collector._fetch = lambda url, source: (requested.append(url) or b'<feed xmlns="http://www.w3.org/2005/Atom"/>', "application/atom+xml", url)
        source = {"endpoint": "https://export.arxiv.org/api/query", "search_parameter": "search_query", "max_results_per_request": 10}
        collector._discover_arxiv(source, "all:photonic AND all:waveguide", 10)
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlparse(requested[0]).query)["search_query"], ["all:photonic AND all:waveguide"])
