import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import src.editorial_rerank as editorial


BOARD = {
    "topic": "intimacy through conversation",
    "evidence": [{
        "id": 10, "title": "Q&A", "evidence_start": 100.0, "evidence_end": 120.0,
        "excerpt": "We are going to ask each other direct questions.",
        "semantic_score": 0.7, "score": 0.7, "angles": ["Core idea"],
        "match_type": "evidence",
    }],
}


class FakeResponses:
    def parse(self, **kwargs):
        valid = editorial.EvidenceAssessment(
            candidate_id=10, keep=True, relevance=5, evidence_strength=5,
            editorial_usefulness=4, distinctiveness=4, clip_potential=5,
            editorial_role="development", reason="Direct questions create disclosure.",
            supported_claim="They use questions to accelerate personal disclosure.",
        )
        invented = valid.model_copy(update={"candidate_id": 999})
        return SimpleNamespace(output_parsed=editorial.EditorialJudgment(
            thesis_direction="Conversation turns vulnerability into a shared game.",
            assessments=[valid, invented],
        ))


class FakeOpenAI:
    def __init__(self, **kwargs):
        self.responses = FakeResponses()


class EditorialRerankTests(unittest.TestCase):
    def test_missing_key_is_clear(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "not configured"):
                editorial.editorial_rerank(None, "topic")

    def test_structured_result_is_validated_against_candidates(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
             patch.object(editorial, "build_evidence_board", return_value=BOARD), \
             patch.object(editorial, "OpenAI", FakeOpenAI):
            result = editorial.editorial_rerank(None, BOARD["topic"])
        self.assertEqual([10], [item["id"] for item in result["evidence"]])
        self.assertEqual("development", result["evidence"][0]["editorial_role"])


if __name__ == "__main__":
    unittest.main()
