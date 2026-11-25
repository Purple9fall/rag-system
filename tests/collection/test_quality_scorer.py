import unittest
from collection.config_loader import load_collection
from collection.quality_scorer import score_record


class QualityScorerTest(unittest.TestCase):
    def test_strong_topic_match_scores_above_threshold(self):
        config = load_collection()
        record = {"title": "Silicon nitride SiN integrated photonics platform", "abstract": "Waveguide loss simulation results with geometry and width parameters", "body": "", "year": 2025, "document_type": "journal_article", "citation_count": 20}
        score = score_record(record, config["topics"]["sin_platform"], config["scoring"])
        self.assertGreaterEqual(score, config["scoring"]["selection"]["minimum_score"])
