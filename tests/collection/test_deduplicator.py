import unittest
from collection.deduplicator import identity


class DeduplicatorTest(unittest.TestCase):
    def test_doi_is_canonical_identity(self):
        self.assertEqual(identity({"doi": "https://doi.org/10.123/ABC"}), "doi:10.123/abc")
