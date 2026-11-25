import unittest
from collection.config_loader import load_collection


class ConfigLoaderTest(unittest.TestCase):
    def test_paths_and_topics(self):
        config = load_collection()
        self.assertEqual(len(config["topics"]), 11)
        self.assertEqual(len(config["topics"]["pic_fundamentals"]["subtopics"]), 5)
        self.assertEqual(config["manifest_file"].name, "documents.jsonl")
        self.assertEqual(config["raw_dir"].name, "raw")
