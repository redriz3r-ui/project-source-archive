import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

import src.concept_generator as generator


def concept(format_name):
    return generator.ReelConcept(
        title=f"A {format_name} concept", format=format_name,
        hook="A concise hook about conversation.",
        thesis="Conversation lets the characters make vulnerability feel safer.",
        tone="clear and intimate", evidence_ids=[10, 29], estimated_duration=30,
        warnings=[], beats=[
            generator.ConceptBeat(order=1, card_type="hook", evidence_id=0, text="Hook", duration_seconds=2),
            generator.ConceptBeat(order=2, card_type="clip", evidence_id=10, text="Q&A",
                                  anchor_quote="TRANSCRIPT, evidence one!", duration_seconds=6),
            generator.ConceptBeat(order=3, card_type="observation", evidence_id=0, text="Observation", duration_seconds=4),
            generator.ConceptBeat(order=4, card_type="clip", evidence_id=29, text="Phone call",
                                  anchor_quote="Transcript evidence two", duration_seconds=7),
            generator.ConceptBeat(order=5, card_type="interpretation", evidence_id=0, text="Payoff", duration_seconds=7),
            generator.ConceptBeat(order=6, card_type="end_card", evidence_id=0, text="FFS", duration_seconds=4),
        ],
    )


BOARD = {"topic": "intimacy", "evidence": [
    {"id": 10, "title": "Scene 10", "evidence_start": 100,
     "evidence_end": 120, "excerpt": "We share transcript evidence one tonight.",
     "semantic_score": .7, "score": .7, "angles": [], "match_type": "evidence"},
    {"id": 29, "title": "Scene 29", "evidence_start": 290,
     "evidence_end": 310, "excerpt": "Then comes transcript evidence two later.",
     "semantic_score": .7, "score": .7, "angles": [], "match_type": "evidence"},
    {"id": 40, "title": "Scene 40", "evidence_start": 400,
     "evidence_end": 420, "excerpt": "A third transcript evidence moment arrives.",
     "semantic_score": .7, "score": .7, "angles": [], "match_type": "evidence"},
]}


class FakeResponses:
    def parse(self, **kwargs):
        return SimpleNamespace(output_parsed=generator.ConceptSet(concepts=[
            concept("analytical_argument"), concept("detail_missed"), concept("poetic_ffs")
        ]))


class FakeOpenAI:
    last_kwargs = None

    def __init__(self, **kwargs):
        type(self).last_kwargs = kwargs
        self.responses = FakeResponses()


class ConceptGeneratorTests(unittest.TestCase):
    def test_three_validated_formats_are_returned(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
             patch.object(generator, "build_evidence_board", return_value=BOARD), \
             patch.object(generator, "OpenAI", FakeOpenAI):
            result = generator.generate_concepts(None, "intimacy", [10, 29, 40])
        self.assertEqual(3, len(result["concepts"]))
        self.assertEqual({"analytical_argument", "detail_missed", "poetic_ffs"},
                         {item["format"] for item in result["concepts"]})
        self.assertEqual(180.0, FakeOpenAI.last_kwargs["timeout"])

    def test_unapproved_evidence_id_is_rejected(self):
        bad = concept("analytical_argument")
        bad.beats[1].evidence_id = 999
        class BadResponses:
            def parse(self, **kwargs):
                return SimpleNamespace(output_parsed=generator.ConceptSet(concepts=[
                    bad, concept("detail_missed"), concept("poetic_ffs")
                ]))
        class BadClient:
            def __init__(self, **kwargs): self.responses = BadResponses()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
             patch.object(generator, "build_evidence_board", return_value=BOARD), \
             patch.object(generator, "OpenAI", BadClient):
            with self.assertRaisesRegex(ValueError, "evidence validation"):
                generator.generate_concepts(None, "intimacy", [10, 29, 40])

    def assert_bad_concept_rejected(self, bad):
        class BadResponses:
            def parse(self, **kwargs):
                return SimpleNamespace(output_parsed=generator.ConceptSet(concepts=[
                    bad, concept("detail_missed"), concept("poetic_ffs")
                ]))

        class BadClient:
            def __init__(self, **kwargs):
                self.responses = BadResponses()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
             patch.object(generator, "build_evidence_board", return_value=BOARD), \
             patch.object(generator, "OpenAI", BadClient):
            with self.assertRaisesRegex(ValueError, "evidence validation"):
                generator.generate_concepts(None, "intimacy", [10, 29, 40])

    def test_clip_with_zero_evidence_id_is_rejected(self):
        bad = concept("analytical_argument")
        bad.beats[1].evidence_id = 0
        self.assert_bad_concept_rejected(bad)

    def test_clip_with_invented_anchor_quote_is_rejected(self):
        bad = concept("analytical_argument")
        bad.beats[1].anchor_quote = "This dialogue was invented"
        self.assert_bad_concept_rejected(bad)

    def test_single_token_anchor_quote_is_rejected(self):
        bad = concept("analytical_argument")
        bad.beats[1].anchor_quote = "evidence"
        self.assert_bad_concept_rejected(bad)

    def test_quote_must_belong_to_that_specific_evidence_transcript(self):
        bad = concept("analytical_argument")
        bad.beats[1].evidence_id = 29
        bad.beats[1].anchor_quote = "Transcript evidence one"
        self.assert_bad_concept_rejected(bad)

    def test_timeout_has_clear_error(self):
        class TimeoutResponses:
            def parse(self, **kwargs):
                raise generator.APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))

        class TimeoutClient:
            def __init__(self, **kwargs):
                self.responses = TimeoutResponses()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
             patch.object(generator, "build_evidence_board", return_value=BOARD), \
             patch.object(generator, "OpenAI", TimeoutClient):
            with self.assertRaisesRegex(
                ValueError, r"^Concept generation took too long\. Try again\.$"
            ):
                generator.generate_concepts(None, "intimacy", [10, 29, 40])


if __name__ == "__main__":
    unittest.main()
