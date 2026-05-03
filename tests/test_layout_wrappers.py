from __future__ import annotations

import unittest

from geoqa.agents import agentic_crsfix
from geoqa.automation import crs_validation
from geoqa.fix import apply_repair_plan, drop_null_geometries, register_custom_repair, remove_duplicate_vertices
from geoqa.interactive import validate_layer
from geoqa.serialization import available_formats, deserialize, serialize


class FakeLayer:
    def __init__(self, crs: str = "EPSG:3857") -> None:
        self.crs = crs

    def to_crs(self, target: str) -> "FakeLayer":
        return FakeLayer(crs=target)


class WrapperLayoutTests(unittest.TestCase):
    def test_agentic_crsfix_wrapper(self) -> None:
        fixed = agentic_crsfix(FakeLayer(), "EPSG:4326")
        self.assertEqual(fixed.crs, "EPSG:4326")

    def test_fix_wrappers_import(self) -> None:
        self.assertTrue(callable(apply_repair_plan))
        self.assertTrue(callable(drop_null_geometries))
        self.assertTrue(callable(register_custom_repair))
        self.assertTrue(callable(remove_duplicate_vertices))

    def test_interactive_wrapper_import(self) -> None:
        self.assertTrue(callable(validate_layer))

    def test_serialization_wrapper(self) -> None:
        payload = serialize({"ok": True}, format="json")
        restored = deserialize(payload, format="json")
        self.assertEqual(restored["ok"], True)
        self.assertIn("json", available_formats())

    def test_automation_wrapper_import(self) -> None:
        self.assertTrue(callable(crs_validation))


if __name__ == "__main__":
    unittest.main()
