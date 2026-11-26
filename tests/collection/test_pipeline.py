import copy
import json
import tempfile
import unittest
from pathlib import Path
from collection.config_loader import load_collection
from collection.pipeline import Collector


class FakeCollector(Collector):
    def _discover_arxiv(self, source, query, limit):
        return [{"title": "Silicon nitride SiN integrated photonics platform", "abstract": "Waveguide simulation results with geometry and width parameters", "url": "https://arxiv.org/abs/1234.5678", "download_url": "https://arxiv.org/pdf/1234.5678", "arxiv_id": "1234.5678", "year": 2025, "document_type": "preprint"}]

    def _fetch(self, url, source):
        return b"%PDF-1.7\n" + b"x" * 600, "application/pdf", url


class PipelineTest(unittest.TestCase):
    def test_unrelated_page_source_is_not_crawled(self):
        config = copy.deepcopy(load_collection())
        config["sources"] = [next(s for s in config["sources"] if s["id"] == "ansys_optics")]
        collector = Collector(config)
        collector._discover_pages = lambda source: self.fail("Ansys should not be crawled for pic_fundamentals")
        result = collector.run(["pic_fundamentals"], dry_run=True)
        self.assertEqual(result["discovered"], 0)

    def test_writes_topic_file_and_metadata_once(self):
        config = copy.deepcopy(load_collection())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config.update(root=root, raw_dir=root / "raw", manifest_file=root / "metadata/documents.jsonl", collection_log_file=root / "metadata/collection_log.jsonl")
            config["sources"] = [config["sources"][1]]
            collector = FakeCollector(config)
            self.assertEqual(collector.run(["sin_platform"])["saved"], 1)
            entry = json.loads(config["manifest_file"].read_text().splitlines()[0])
            self.assertTrue((root / entry["file_path"]).is_file())
            self.assertEqual(Path(entry["file_path"]).parts[:2], ("raw", "sin_platform"))
            self.assertTrue(config["collection_log_file"].is_file())
            self.assertEqual(collector.run(["sin_platform"])["saved"], 0)

    def test_shared_record_is_available_in_each_topic_folder(self):
        config = copy.deepcopy(load_collection())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config.update(root=root, raw_dir=root / "raw", manifest_file=root / "metadata/documents.jsonl", collection_log_file=root / "metadata/collection_log.jsonl")
            config["sources"] = [config["sources"][1]]
            collector = FakeCollector(config)
            collector.run(["pic_fundamentals", "sin_platform"])
            self.assertTrue(any((root / "raw/pic_fundamentals").rglob("*.pdf")))
            self.assertTrue(any((root / "raw/sin_platform").rglob("*.pdf")))
