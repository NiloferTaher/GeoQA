from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.validate_problem_catalog import validate_catalog


class ProblemCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path(__file__).resolve().parents[1] / "raw_problems_with_sources.json"
        self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def test_catalog_validates(self) -> None:
        self.assertEqual(validate_catalog(self.path), [])

    def test_problem_names_are_unique(self) -> None:
        names = [item["problem_name"] for item in self.data]
        self.assertEqual(len(names), len(set(names)))

    def test_all_entries_have_new_fields(self) -> None:
        for item in self.data:
            self.assertIn("severity", item)
            self.assertIn("repair_hint", item)
            self.assertIsInstance(item["severity"], str)
            self.assertIsInstance(item["repair_hint"], str)
            self.assertTrue(item["repair_hint"].strip())


if __name__ == "__main__":
    unittest.main()
