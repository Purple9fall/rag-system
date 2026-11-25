import unittest
from collection.config_loader import load_collection
from collection.relevance_filter import valid_record


class RelevanceFilterTest(unittest.TestCase):
    def test_rejects_unrelated_record(self):
        config = load_collection()
        record = {"title": "Biology", "abstract": "Plant growth", "document_type": "preprint"}
        self.assertFalse(valid_record(record, config["topics"]["sin_platform"], config["constraints"]))
