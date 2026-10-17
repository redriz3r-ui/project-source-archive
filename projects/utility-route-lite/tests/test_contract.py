"""Fixture version, shape, identity and regeneration checks independent of QGIS."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.regenerate_fixtures import OUT, benchmark, regenerate


class FixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((Path(__file__).resolve().parents[1] / "docs/contract/v1.json").read_text())
        cls.manifest = json.loads((OUT / "manifest.json").read_text())

    def test_frozen_version_and_named_cases(self):
        self.assertEqual(self.manifest["schema_version"], self.registry["schema_version"])
        self.assertEqual(len(self.manifest["case_ids"]), 17)
        self.assertEqual(len(set(self.manifest["case_ids"])), 17)
        self.assertEqual(self.manifest["benchmark_id"], "benchmark_1000")
        for case_id in self.manifest["case_ids"]:
            case = json.loads((OUT / f"{case_id}.json").read_text())
            with self.subTest(case_id=case_id):
                self.assertTrue(case["synthetic"])
                self.assertEqual(case["case_id"], case_id)
                self.assertEqual(case["schema_version"], self.registry["schema_version"])
                self.assertEqual(case["rule_profile"]["schema_version"], self.registry["schema_version"])
                self.assertIn(case["rule_profile"]["connection_policy"], self.registry["enums"]["connection_policy"])
                self.assertIn(case["expected"]["build_status"], ("OK", "FAILED"))
                self.assertTrue(case["source"]["features"])
                if "junction_document" in case:
                    self.assertTrue(case["junction_document"]["junction_crs_wkt"].startswith("PROJCRS["))

    def test_oracles_use_frozen_codes_and_success_has_metric_expectation(self):
        for case_id in self.manifest["case_ids"]:
            case = json.loads((OUT / f"{case_id}.json").read_text())
            expected = case["expected"]
            with self.subTest(case_id=case_id):
                for code in expected.get("qa_codes_include", []):
                    self.assertIn(code, self.registry["qa_issue_codes"])
                for field in ("build_error", "failure_code"):
                    if field in expected:
                        self.assertIn(expected[field], self.registry["error_codes"])
                if expected.get("route_status") == "SUCCESS":
                    self.assertTrue("length_m" in expected or "length_m_range" in expected)
                if expected.get("route_status") == "FAILED":
                    self.assertIn("failure_code", expected)

    def test_regeneration_is_byte_identical(self):
        with TemporaryDirectory() as temporary:
            destination = Path(temporary)
            regenerate(destination)
            for original in OUT.glob("*.json"):
                with self.subTest(file=original.name):
                    self.assertEqual(original.read_bytes(), (destination / original.name).read_bytes())

    def test_benchmark_and_scaling_are_deterministic(self):
        self.assertEqual(len(benchmark(1000)["source"]["features"]), 1000)
        self.assertEqual(len(benchmark(10000)["source"]["features"]), 10000)
        self.assertEqual(benchmark(50000)["expected"]["physical_edge_count"], 50000)
        self.assertEqual(benchmark(1000), json.loads((OUT / "benchmark_1000.json").read_text()))


if __name__ == "__main__":
    unittest.main()
