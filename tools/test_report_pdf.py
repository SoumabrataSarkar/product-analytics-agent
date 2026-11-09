"""Tests for the fixed-template investigation report PDF generator."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HAVE_DEPS = all(importlib.util.find_spec(m) for m in ("reportlab", "matplotlib"))
EXAMPLE = Path(__file__).resolve().parents[1] / "docs" / "deliverables" / "report-content-example.json"


@unittest.skipUnless(HAVE_DEPS, "reportlab and matplotlib are required")
class ReportPdfTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import report_pdf  # noqa: PLC0415  (imported only when dependencies exist)
        cls.rp = report_pdf
        cls.example = json.loads(EXAMPLE.read_text())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "report.pdf"

    def tearDown(self):
        self.tmp.cleanup()

    def test_example_builds_within_page_limit(self):
        pages = self.rp.build(copy.deepcopy(self.example), self.out)
        self.assertTrue(self.out.exists())
        self.assertGreater(self.out.stat().st_size, 10_000)
        self.assertLessEqual(pages, self.rp.MAX_PAGES)

    def test_page_limit_is_enforced_and_output_removed(self):
        content = copy.deepcopy(self.example)
        long_table = {"type": "table", "widths": [0.5, 0.5],
                      "rows": [["Item", "Detail"]] + [[f"Row {i}", "Filler text " * 8] for i in range(400)]}
        content["sections"]["appendix"]["blocks"].append(long_table)
        with self.assertRaises(self.rp.PageLimitError):
            self.rp.build(content, self.out)
        self.assertFalse(self.out.exists())

    def test_unknown_section_is_refused(self):
        content = copy.deepcopy(self.example)
        content["sections"]["surprise"] = {"blocks": []}
        with self.assertRaises(ValueError):
            self.rp.build(content, self.out)

    def test_unknown_block_type_is_refused(self):
        content = copy.deepcopy(self.example)
        content["sections"]["limitations"]["blocks"].append({"type": "poem", "text": "x"})
        with self.assertRaises(ValueError):
            self.rp.build(content, self.out)

    def test_chapter_order_is_fixed(self):
        numbers = [c[0] for c in self.rp.CHAPTERS]
        self.assertEqual(numbers, ["01", "02", "03", "04", "05", "06", "A"])


if __name__ == "__main__":
    unittest.main()
