from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from geoqa import GeoQAScriptBase
from geoqa.runner import ThermalRunner
from geoqa import thermal as thermal_module
from geoqa.thermal import TemperatureSnapshot, ThermalGuard, ThermalLimitExceeded


class ThermalGuardTests(unittest.TestCase):
    def test_warn_threshold_must_be_lower_than_max(self) -> None:
        with self.assertRaises(ValueError):
            ThermalGuard(warn_temp_c=80.0, max_temp_c=80.0)

    def test_check_or_raise_blocks_hot_snapshot(self) -> None:
        guard = ThermalGuard(max_temp_c=80.0)
        guard.snapshot = lambda: TemperatureSnapshot(81.5, 79.0, 4, "test")  # type: ignore[method-assign]
        with self.assertRaises(ThermalLimitExceeded):
            guard.check_or_raise()

    def test_wait_until_safe_returns_when_cool_enough(self) -> None:
        snapshots = iter(
            [
                TemperatureSnapshot(78.0, 77.0, 4, "test"),
                TemperatureSnapshot(75.0, 74.0, 4, "test"),
            ]
        )
        sleep_calls: list[float] = []
        guard = ThermalGuard(
            warn_temp_c=76.0,
            max_temp_c=80.0,
            check_interval_seconds=1.5,
            sleep_fn=sleep_calls.append,
        )
        guard.snapshot = lambda: next(snapshots)  # type: ignore[method-assign]
        snap = guard.wait_until_safe()
        self.assertEqual(snap.max_temp_c, 75.0)
        self.assertEqual(sleep_calls, [1.5])

    def test_runner_processes_sequence(self) -> None:
        snapshots = iter(
            [
                TemperatureSnapshot(70.0, 69.0, 4, "test"),
                TemperatureSnapshot(71.0, 70.0, 4, "test"),
                TemperatureSnapshot(70.0, 69.0, 4, "test"),
                TemperatureSnapshot(71.0, 70.0, 4, "test"),
                TemperatureSnapshot(70.0, 69.0, 4, "test"),
                TemperatureSnapshot(70.0, 69.0, 4, "test"),
                TemperatureSnapshot(70.0, 69.0, 4, "test"),
                TemperatureSnapshot(70.0, 69.0, 4, "test"),
            ]
        )
        guard = ThermalGuard(warn_temp_c=76.0, max_temp_c=80.0, sleep_fn=lambda _: None)
        guard.snapshot = lambda: next(snapshots)  # type: ignore[method-assign]
        runner = ThermalRunner[int](guard=guard)
        results = runner.run_sequence([1, 2], lambda item: item * 10)
        self.assertEqual([r.result for r in results], [10, 20])
        self.assertEqual([r.index for r in results], [1, 2])

    def test_script_base_runs_items(self) -> None:
        snapshots = iter(
            [
                TemperatureSnapshot(70.0, 69.0, 4, "test"),
                TemperatureSnapshot(70.0, 69.0, 4, "test"),
                TemperatureSnapshot(70.0, 69.0, 4, "test"),
                TemperatureSnapshot(70.0, 69.0, 4, "test"),
                TemperatureSnapshot(70.0, 69.0, 4, "test"),
            ]
        )
        guard = ThermalGuard(warn_temp_c=76.0, max_temp_c=80.0, sleep_fn=lambda _: None)
        guard.snapshot = lambda: next(snapshots)  # type: ignore[method-assign]

        class DemoScript(GeoQAScriptBase[int, int]):
            def __init__(self, *, guard: ThermalGuard) -> None:
                super().__init__(guard=guard)
                self.seen: list[tuple[str, int]] = []

            def load_items(self):
                return [2]

            def process_item(self, item: int) -> int:
                self.seen.append(("process", item))
                return item * 5

            def before_run(self) -> None:
                self.seen.append(("before_run", 0))

            def after_run(self, results) -> None:
                self.seen.append(("after_run", len(results)))

        script = DemoScript(guard=guard)
        results = script.run()
        self.assertEqual(results[0].result, 10)
        self.assertEqual(script.seen, [("before_run", 0), ("process", 2), ("after_run", 1)])

    def test_script_base_emits_startup_diagnostic_by_default(self) -> None:
        original_diag = thermal_module.run_temperature_diagnostic
        original_script_diag = GeoQAScriptBase.run.__globals__["run_temperature_diagnostic"]
        try:
            fake_diag = thermal_module.TemperatureDiagnostic(
                ok=True,
                platform="test",
                source="psutil",
                temperatures_c=[55.0],
                message="diagnostic ok",
                options=[],
            )
            thermal_module.run_temperature_diagnostic = lambda: fake_diag  # type: ignore[assignment]
            GeoQAScriptBase.run.__globals__["run_temperature_diagnostic"] = lambda: fake_diag

            snapshots = iter(
                [
                    TemperatureSnapshot(70.0, 69.0, 4, "test"),
                    TemperatureSnapshot(70.0, 69.0, 4, "test"),
                    TemperatureSnapshot(70.0, 69.0, 4, "test"),
                    TemperatureSnapshot(70.0, 69.0, 4, "test"),
                    TemperatureSnapshot(70.0, 69.0, 4, "test"),
                ]
            )
            guard = ThermalGuard(warn_temp_c=76.0, max_temp_c=80.0, sleep_fn=lambda _: None)
            guard.snapshot = lambda: next(snapshots)  # type: ignore[method-assign]

            class DemoScript(GeoQAScriptBase[int, int]):
                def load_items(self):
                    return [1]

                def process_item(self, item: int) -> int:
                    return item

            buf = io.StringIO()
            with redirect_stdout(buf):
                DemoScript(guard=guard).run()
        finally:
            thermal_module.run_temperature_diagnostic = original_diag  # type: ignore[assignment]
            GeoQAScriptBase.run.__globals__["run_temperature_diagnostic"] = original_script_diag

        self.assertIn("diagnostic ok", buf.getvalue())

    def test_script_base_can_disable_startup_diagnostic(self) -> None:
        original_diag = thermal_module.run_temperature_diagnostic
        original_script_diag = GeoQAScriptBase.run.__globals__["run_temperature_diagnostic"]
        try:
            fake_diag = thermal_module.TemperatureDiagnostic(
                ok=True,
                platform="test",
                source="psutil",
                temperatures_c=[55.0],
                message="should not print",
                options=[],
            )
            thermal_module.run_temperature_diagnostic = lambda: fake_diag  # type: ignore[assignment]
            GeoQAScriptBase.run.__globals__["run_temperature_diagnostic"] = lambda: fake_diag

            snapshots = iter(
                [
                    TemperatureSnapshot(70.0, 69.0, 4, "test"),
                    TemperatureSnapshot(70.0, 69.0, 4, "test"),
                    TemperatureSnapshot(70.0, 69.0, 4, "test"),
                    TemperatureSnapshot(70.0, 69.0, 4, "test"),
                    TemperatureSnapshot(70.0, 69.0, 4, "test"),
                ]
            )
            guard = ThermalGuard(warn_temp_c=76.0, max_temp_c=80.0, sleep_fn=lambda _: None)
            guard.snapshot = lambda: next(snapshots)  # type: ignore[method-assign]

            class DemoScript(GeoQAScriptBase[int, int]):
                def load_items(self):
                    return [1]

                def process_item(self, item: int) -> int:
                    return item

            buf = io.StringIO()
            with redirect_stdout(buf):
                DemoScript(guard=guard, emit_thermal_diagnostic=False).run()
        finally:
            thermal_module.run_temperature_diagnostic = original_diag  # type: ignore[assignment]
            GeoQAScriptBase.run.__globals__["run_temperature_diagnostic"] = original_script_diag

        self.assertNotIn("should not print", buf.getvalue())

    def test_temperature_diagnostic_reports_psutil_success(self) -> None:
        original_coretemp = thermal_module._read_coretemp_mapping
        original_psutil = thermal_module._read_psutil_temp
        try:
            thermal_module._read_coretemp_mapping = lambda: []  # type: ignore[assignment]
            thermal_module._read_psutil_temp = lambda: [61.0, 63.0]  # type: ignore[assignment]
            result = thermal_module.run_temperature_diagnostic()
        finally:
            thermal_module._read_coretemp_mapping = original_coretemp  # type: ignore[assignment]
            thermal_module._read_psutil_temp = original_psutil  # type: ignore[assignment]

        self.assertTrue(result.ok)
        self.assertEqual(result.source, "psutil")
        self.assertEqual(result.temperatures_c, [61.0, 63.0])

    def test_temperature_diagnostic_reports_unavailable(self) -> None:
        original_coretemp = thermal_module._read_coretemp_mapping
        original_psutil = thermal_module._read_psutil_temp
        try:
            thermal_module._read_coretemp_mapping = lambda: []  # type: ignore[assignment]
            thermal_module._read_psutil_temp = lambda: []  # type: ignore[assignment]
            result = thermal_module.run_temperature_diagnostic()
        finally:
            thermal_module._read_coretemp_mapping = original_coretemp  # type: ignore[assignment]
            thermal_module._read_psutil_temp = original_psutil  # type: ignore[assignment]

        self.assertFalse(result.ok)
        self.assertEqual(result.source, "unavailable")
        self.assertGreaterEqual(len(result.options), 1)


if __name__ == "__main__":
    unittest.main()
