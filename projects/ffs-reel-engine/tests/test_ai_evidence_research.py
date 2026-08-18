import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import src.ai_evidence_research as researcher


def call(name, call_id, arguments):
    return SimpleNamespace(
        type="function_call", name=name, call_id=call_id,
        arguments=json.dumps(arguments),
    )


class FakeIndex:
    def semantic_passages(self):
        return [
            {"id": 71, "scene_id": 10, "start": 100.0, "end": 112.0,
             "text": "We are going to ask each other direct questions.", "embedding": b"x"},
            {"id": 83, "scene_id": 29, "start": 200.0, "end": 214.0,
             "text": "I was ready to get off the train with him.", "embedding": b"y"},
            {"id": 95, "scene_id": 40, "start": 300.0, "end": 314.0,
             "text": "I can fall in love when I know everything about someone.", "embedding": b"z"},
        ]

    def scenes(self):
        return [
            {"id": 10, "start": 90.0, "end": 130.0, "title": "Question game"},
            {"id": 29, "start": 190.0, "end": 230.0, "title": "Imaginary call"},
            {"id": 40, "start": 290.0, "end": 330.0, "title": "Being known"},
        ]

    def normalized_transcript(self):
        return [
            {"start": 100.0, "end": 104.0,
             "text": "We are going to ask each other direct questions."},
            {"start": 200.0, "end": 205.0,
             "text": "I was ready to get off the train with him."},
            {"start": 300.0, "end": 305.0,
             "text": "I can fall in love when I know everything about someone."},
        ]


def semantic_results(index, query, limit):
    return [
        {"id": 10, "title": "Question game", "score": .81,
         "evidence_start": 100.0, "evidence_end": 112.0,
         "excerpt": "We are going to ask each other direct questions."},
        {"id": 29, "title": "Imaginary call", "score": .74,
         "evidence_start": 200.0, "evidence_end": 214.0,
         "excerpt": "I was ready to get off the train with him."},
        {"id": 40, "title": "Being known", "score": .69,
         "evidence_start": 300.0, "evidence_end": 314.0,
         "excerpt": "I can fall in love when I know everything about someone."},
    ][:limit]


class FakeResponses:
    def __init__(self, bad_final=False, silent_first=False):
        self.calls = []
        self.bad_final = bad_final
        self.silent_first = silent_first
        self.saw_research_nudge = False

    def create(self, **kwargs):
        self.calls.append(kwargs)
        number = len(self.calls)
        if self.silent_first:
            if number == 1:
                return SimpleNamespace(output=[])
            if number == 2:
                self.saw_research_nudge = any(
                    isinstance(item, dict)
                    and item.get("role") == "user"
                    and "not inspected enough" in item.get("content", "")
                    for item in kwargs["input"]
                )
            number -= 1
        if number == 1:
            return SimpleNamespace(output=[call(
                "semantic_scene_search", "search-1", {"query": "direct personal questions", "limit": 4}
            )])
        if number == 2:
            return SimpleNamespace(output=[call(
                "read_scene_context", "context-1", {"passage_id": 71}
            )])
        if number == 3:
            return SimpleNamespace(output=[call(
                "read_scene_context", "context-2", {"passage_id": 83}
            )])
        if number == 4:
            return SimpleNamespace(output=[call(
                "read_scene_context", "context-3", {"passage_id": 95}
            )])
        if number == 5:
            return SimpleNamespace(output=[])
        selected = [71, 83, 999] if self.bad_final else [71, 83, 95]
        return SimpleNamespace(output=[call("submit_evidence_board", "final-1", {
            "research_summary": "Searched direct questions and inspected the strongest local passage.",
            "thesis_direction": "Direct questions turn vulnerability into shared play.",
            "selected_ids": selected,
            "evidence": [
                {"passage_id": passage_id, "editorial_role": role,
                 "reason": "The inspected exchange directly supports the requested topic.",
                 "supported_claim": "The conversation creates a structure for emotional disclosure.",
                 "warning": ""}
                for passage_id, role in zip(selected, ("setup", "development", "payoff"))
            ],
        })])


class FakeOpenAI:
    responses = None

    def __init__(self, **kwargs):
        self.responses = type(self).responses


class NoToolResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output=[])


class AiEvidenceResearchTests(unittest.TestCase):
    def run_research(self, *, bad_final=False, silent_first=False):
        responses = FakeResponses(bad_final=bad_final, silent_first=silent_first)
        FakeOpenAI.responses = responses
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
             patch.object(researcher, "OpenAI", FakeOpenAI), \
             patch.object(researcher, "semantic_search", side_effect=semantic_results):
            result = researcher.research_evidence(FakeIndex(), "intimacy", limit=3)
        return result, responses

    def test_direct_tool_research_returns_server_validated_stable_passage(self):
        result, responses = self.run_research()
        self.assertEqual([71, 83, 95], result["selected_ids"])
        item = result["evidence"][0]
        self.assertEqual(71, item["id"])
        self.assertEqual(71, item["passage_id"])
        self.assertEqual(10, item["scene_id"])
        self.assertEqual("Question game", item["title"])
        self.assertEqual((100.0, 112.0), (item["evidence_start"], item["evidence_end"]))
        self.assertEqual("We are going to ask each other direct questions.", item["excerpt"])
        self.assertEqual(
            "Searched direct questions and inspected the strongest local passage.",
            result["research_summary"],
        )
        self.assertEqual(["direct personal questions"], result["searches"])
        self.assertEqual(result["searches"], result["queries"])
        self.assertEqual(1, result["research"]["search_calls"])
        self.assertEqual(3, result["research"]["context_calls"])
        self.assertTrue(all(request["store"] is False for request in responses.calls))
        self.assertEqual(
            {"type": "function", "name": "submit_evidence_board"},
            responses.calls[-1]["tool_choice"],
        )
        final_schema = responses.calls[-1]["tools"][0]["parameters"]
        self.assertEqual(3, final_schema["properties"]["selected_ids"]["minItems"])
        self.assertEqual(3, final_schema["properties"]["evidence"]["minItems"])
        self.assertEqual(
            [71, 83, 95],
            final_schema["properties"]["selected_ids"]["items"]["enum"],
        )
        self.assertEqual(
            [71, 83, 95],
            final_schema["properties"]["evidence"]["items"]["properties"]
            ["passage_id"]["enum"],
        )
        self.assertEqual(8, researcher.MAX_RESEARCH_ROUNDS)

    def test_silent_response_is_nudged_until_minimum_context_is_inspected(self):
        result, responses = self.run_research(silent_first=True)
        self.assertEqual([71, 83, 95], result["selected_ids"])
        self.assertTrue(responses.saw_research_nudge)
        self.assertEqual(7, len(responses.calls))

    def test_research_fails_before_submission_when_minimum_was_not_inspected(self):
        responses = NoToolResponses()
        FakeOpenAI.responses = responses
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True), \
             patch.object(researcher, "OpenAI", FakeOpenAI), \
             patch.object(researcher, "semantic_search", side_effect=semantic_results):
            with self.assertRaisesRegex(ValueError, "at least 3 distinct passages"):
                researcher.research_evidence(FakeIndex(), "intimacy", limit=3)
        self.assertEqual(researcher.MAX_RESEARCH_ROUNDS, len(responses.calls))

    def test_model_invented_passage_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "did not inspect"):
            self.run_research(bad_final=True)

    def test_missing_key_uses_existing_configuration_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "not configured"):
                researcher.research_evidence(FakeIndex(), "intimacy")


if __name__ == "__main__":
    unittest.main()
