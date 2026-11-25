import unittest
import urllib.error
import urllib.robotparser
from unittest.mock import patch
from collection.downloader import Downloader, SourceAccessDenied


class DownloaderTest(unittest.TestCase):
    def test_rejects_non_https(self):
        self.assertFalse(Downloader()._allowed("http://example.org/file.pdf"))

    def test_stops_requesting_host_after_forbidden(self):
        downloader = Downloader()
        downloader.constraints["download"]["respect_robots_txt"] = False
        source = {"id": "test", "min_interval_seconds": 0}
        error = urllib.error.HTTPError("https://example.org/x", 403, "Forbidden", {}, None)
        with patch("urllib.request.urlopen", side_effect=error) as fetch:
            with self.assertRaises(SourceAccessDenied):
                downloader._fetch("https://example.org/x", source)
            with self.assertRaises(SourceAccessDenied):
                downloader._fetch("https://example.org/y", source)
            self.assertEqual(fetch.call_count, 1)

    def test_documented_api_exception_is_scoped_to_endpoint(self):
        downloader = Downloader()
        source = next(s for s in downloader.config["sources"] if s["id"] == "arxiv")
        self.assertTrue(downloader._allowed(source["endpoint"] + "?search_query=all:photonics", source))
        robots = urllib.robotparser.RobotFileParser()
        robots.parse(["User-agent: *", "Disallow: /"])
        downloader._robots["https://export.arxiv.org"] = robots
        self.assertFalse(downloader._allowed("https://export.arxiv.org/other", source))
        self.assertFalse(downloader._allowed("https://export.arxiv.org/api/query/other", source))
