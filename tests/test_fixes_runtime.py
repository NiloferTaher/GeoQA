from __future__ import annotations

import unittest

import pandas as pd

from geoqa.fixes import (
    RepairProfile,
    apply_repair_plan,
    clear_custom_repairs,
    list_custom_repairs,
    register_custom_repair,
)


class SimpleLayer:
    def __init__(self, records):
        self._frame = pd.DataFrame(records)

    def copy(self):
        copied = SimpleLayer([])
        copied._frame = self._frame.copy()
        return copied

    def __getitem__(self, key):
        return self._frame.__getitem__(key)

    def __setitem__(self, key, value):
        self._frame.loc[:, key] = value

    @property
    def columns(self):
        return self._frame.columns

    def loc(self, *args, **kwargs):
        return self._frame.loc(*args, **kwargs)


class TestRepairRuntime(unittest.TestCase):
    def setUp(self) -> None:
        clear_custom_repairs()

    def tearDown(self) -> None:
        clear_custom_repairs()

    def test_custom_repair_registration_and_plan_execution(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": None, "status": "raw"}])

        def mark_review(current_layer, **_options):
            updated = current_layer.copy()
            updated._frame.loc[:, "status"] = "reviewed"
            return updated

        register_custom_repair("mark_review", mark_review)
        fixed = apply_repair_plan(layer, profile=RepairProfile(name="custom_only", enabled_repairs=("mark_review",)), include_builtin=False)

        self.assertEqual(list_custom_repairs(), ["mark_review"])
        self.assertEqual(fixed["status"].iloc[0], "reviewed")

    def test_repair_profile_can_disable_builtin_step(self) -> None:
        layer = SimpleLayer([{"ID": 1, "geometry": None}])
        fixed = apply_repair_plan(
            layer,
            profile=RepairProfile(name="no_drop", disabled_repairs=("drop_null_geometries",)),
            include_builtin=True,
        )
        self.assertEqual(len(fixed["geometry"]), 1)


if __name__ == "__main__":
    unittest.main()
