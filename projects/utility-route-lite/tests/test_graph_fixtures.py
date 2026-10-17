"""Red product tests: compare future services with fixed synthetic oracles."""

import json
from pathlib import Path
import unittest

from fixture_adapter import evaluate_fixture


OUT = Path(__file__).resolve().parents[1] / "examples" / "fixtures" / "v1"


class GraphFixtureTests(unittest.TestCase):
    def test_all_expected_graph_qa_route_and_export_results(self):
        manifest = json.loads((OUT / "manifest.json").read_text())
        for case_id in manifest["case_ids"]:
            with self.subTest(case_id=case_id):
                case = json.loads((OUT / f"{case_id}.json").read_text())
                expected = case["expected"]
                actual = evaluate_fixture(case)
                self.assertEqual(actual["build_status"], expected["build_status"])
                for key in ("build_error", "component_count", "route_status", "failure_code",
                            "connection_verification", "route_vertices_xy", "directions",
                            "batch_statuses", "batch_failure_codes", "batch_lengths_m",
                            "physical_edge_count"):
                    if key in expected:
                        self.assertEqual(actual[key], expected[key], f"{case_id}: {key}")
                for code in expected.get("qa_codes_include", []):
                    self.assertIn(code, actual["qa_codes"], f"{case_id}: missing QA {code}")
                if "length_m" in expected:
                    self.assertAlmostEqual(actual["length_m"], expected["length_m"], places=7)
                if "length_m_range" in expected:
                    lower, upper = expected["length_m_range"]
                    self.assertLessEqual(lower, actual["length_m"])
                    self.assertLessEqual(actual["length_m"], upper)
                if "source_parts" in expected:
                    self.assertEqual(actual["source_parts"], expected["source_parts"])
                for key in expected.get("excluded_source_keys", []):
                    self.assertNotIn(key, [part[0] for part in actual["source_parts"]])
                if "forbidden_transition" in expected:
                    self.assertNotIn(expected["forbidden_transition"], actual.get("used_transitions", []))
                if "html_must_contain" in expected:
                    self.assertIn(expected["html_must_contain"], actual["rendered_html"])
                    self.assertNotIn("<script>", actual["rendered_html"])
                if "csv_cell_must_start" in expected:
                    self.assertTrue(actual["escaped_csv_cell"].startswith(expected["csv_cell_must_start"]))

    def test_benchmark_route_and_edge_count(self):
        case = json.loads((OUT / "benchmark_1000.json").read_text())
        actual = evaluate_fixture(case)
        self.assertEqual(actual["build_status"], "OK")
        self.assertEqual(actual["physical_edge_count"], 1000)
        self.assertEqual(actual["component_count"], 1)
        self.assertEqual(actual["route_status"], "SUCCESS")
        self.assertAlmostEqual(actual["length_m"], 1000, places=7)


if __name__ == "__main__":
    unittest.main()
