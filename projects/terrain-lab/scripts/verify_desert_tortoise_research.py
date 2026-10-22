"""Offline checks for the publication-discovery collector."""

import contextlib
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import desert_tortoise_research as research


def paper(title="Mojave desert tortoise habitat", doi="10.1234/example", date="2025-01-02", source="Crossref"):
    return {"title": title, "date": date, "doi": doi, "url": f"https://doi.org/{doi}" if doi else "",
            "authors": "A. Researcher", "journal": "Journal", "abstract": "", "paper_type": "journal-article",
            "open_access_url": "", "retracted": False, "sources": [source]}


class ResearchDiscoveryTests(unittest.TestCase):
    def test_date_filter_is_inclusive_and_rejects_bad_or_future_dates(self):
        candidates = [paper(date=date, doi=f"10.1234/{i}") for i, date in enumerate(
            ["2023-10-17", "2023-10-18", "2024-02-30", "2999-01-01"])]
        found = research.deduplicate(candidates, "2023-10-18")
        self.assertEqual([p["date"] for p in found], ["2023-10-18"])

    def test_duplicate_doi_merges_even_when_titles_differ(self):
        first = paper(title="Mojave desert tortoise habitat analysis", source="Crossref")
        second = paper(title="Desert tortoise habitat analysis: Mojave region",
                       doi="https://doi.org/10.1234/EXAMPLE", source="OpenAlex")
        found = research.deduplicate([first, second], "2023-10-18")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["doi"], "10.1234/example")
        self.assertEqual(found[0]["sources"], ["Crossref", "OpenAlex"])

    def test_title_fallback_and_distinct_dois(self):
        title = "Mojave desert tortoise habitat"
        records = [paper(title=title, doi="", source="Europe PMC"),
                   paper(title=title, doi="10.1234/one", source="Crossref"),
                   paper(title=title, doi="10.1234/two", source="OpenAlex")]
        found = research.deduplicate(records, "2023-10-18")
        self.assertEqual(len(found), 2)
        self.assertEqual({p["doi"] for p in found}, {"10.1234/one", "10.1234/two"})
        self.assertEqual(next(p for p in found if p["doi"] == "10.1234/one")["sources"],
                         ["Crossref", "Europe PMC"])

    def test_export_formats_agree_and_record_source_errors(self):
        records = research.deduplicate([paper()], "2023-10-18")
        with tempfile.TemporaryDirectory() as temp:
            prefix = Path(temp) / "discovery" / "desert_tortoise_papers"
            research.export(records, prefix, "2023-10-18", ["Crossref / desert tortoise: unavailable"])
            data = json.loads(prefix.with_suffix(".json").read_text())
            with prefix.with_suffix(".csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            markdown = prefix.with_suffix(".md").read_text()
            self.assertEqual(data["count"], len(data["papers"]))
            self.assertEqual([p["title"] for p in data["papers"]], [p["title"] for p in rows])
            self.assertIn("1 papers found", markdown)
            self.assertIn(records[0]["title"], markdown)
            self.assertEqual(len(data["source_errors"]), 1)
            self.assertIn("Some sources could not be reached", markdown)

    def test_partial_api_failure_keeps_results_and_reports_warning(self):
        def unavailable(*_args):
            raise research.URLError("unavailable")

        with tempfile.TemporaryDirectory() as temp, \
             patch.object(research, "collect_openalex", return_value=[paper()]), \
             patch.object(research, "collect_crossref", side_effect=unavailable), \
             patch.object(research, "collect_europepmc", return_value=[]), \
             patch.object(research.time, "sleep", return_value=None), \
             contextlib.redirect_stdout(StringIO()), contextlib.redirect_stderr(StringIO()):
            prefix = Path(temp) / "desert_tortoise_papers"
            status = research.main(["--since", "2023-10-18", "--output-prefix", str(prefix)])
            data = json.loads(prefix.with_suffix(".json").read_text())
        self.assertEqual(status, 0)
        self.assertEqual(data["count"], 1)
        self.assertEqual(len(data["source_errors"]), len(research.TERMS))

    def test_complete_api_failure_exits_unsuccessfully(self):
        with tempfile.TemporaryDirectory() as temp, \
             patch.object(research, "collect_openalex", side_effect=research.URLError("offline")), \
             patch.object(research, "collect_crossref", side_effect=research.URLError("offline")), \
             patch.object(research, "collect_europepmc", side_effect=research.URLError("offline")), \
             patch.object(research.time, "sleep", return_value=None), \
             contextlib.redirect_stdout(StringIO()), contextlib.redirect_stderr(StringIO()):
            prefix = Path(temp) / "desert_tortoise_papers"
            status = research.main(["--since", "2023-10-18", "--output-prefix", str(prefix)])
            data = json.loads(prefix.with_suffix(".json").read_text())
        self.assertEqual(status, 1)
        self.assertEqual(data["count"], 0)
        self.assertEqual(len(data["source_errors"]), 3 * len(research.TERMS))


if __name__ == "__main__":
    unittest.main()
