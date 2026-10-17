"""Focused negative tests for contract drift detection, using stdlib only."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from check_contract import validate_contract, validate_docs  # noqa: E402


class ContractRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((ROOT / "docs" / "contract" / "v1.json").read_text())

    def test_frozen_contract_and_docs_validate(self):
        self.assertEqual(validate_contract(self.contract), [])
        self.assertEqual(validate_docs(ROOT, self.contract), [])

    def test_removing_provenance_field_is_rejected(self):
        modified = deepcopy(self.contract)
        modified["gpkg_layers"]["route_segments"]["fields"] = [
            f for f in modified["gpkg_layers"]["route_segments"]["fields"]
            if f["name"] != "source_feature_key"
        ]
        self.assertTrue(any("source_feature_key" in p for p in validate_contract(modified)))

    def test_duplicate_processing_parameter_is_rejected(self):
        modified = deepcopy(self.contract)
        modified["algorithms"]["utilityroutelite:find_route"]["required_inputs"].append("ROUTE_ID")
        self.assertTrue(any("duplicate parameter" in p for p in validate_contract(modified)))

    def test_major_schema_drift_is_rejected(self):
        modified = deepcopy(self.contract)
        modified["schema_version"] = "2.0.0"
        self.assertTrue(any("schema_version" in p for p in validate_contract(modified)))


if __name__ == "__main__":
    unittest.main()
