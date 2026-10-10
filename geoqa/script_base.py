from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Generic, Iterable, TypeVar

from .runner import StepResult, ThermalRunner
from .thermal import ThermalGuard, TemperatureDiagnostic, run_temperature_diagnostic


T = TypeVar("T")
R = TypeVar("R")


class GeoQAScriptBase(ABC, Generic[T, R]):
    """
    Base class for thermal-aware GeoQA scripts.

    Subclasses only need to implement `load_items` and `process_item`.
    """

    def __init__(
        self,
        *,
        guard: ThermalGuard | None = None,
        emit_thermal_diagnostic: bool = True,
        diagnostic_emitter: Callable[[TemperatureDiagnostic], None] | None = None,
    ) -> None:
        self.guard = guard or ThermalGuard()
        self.emit_thermal_diagnostic = bool(emit_thermal_diagnostic)
        self.diagnostic_emitter = diagnostic_emitter or self._default_diagnostic_emitter
        self.runner = ThermalRunner[T](
            guard=self.guard,
            before_step=self.before_step,
            after_step=self.after_step,
        )

    @abstractmethod
    def load_items(self) -> Iterable[T]:
        """Return the units of work for this script."""

    @abstractmethod
    def process_item(self, item: T) -> R:
        """Process one unit of work."""

    def before_run(self) -> None:
        """Optional setup hook before the thermal-aware run begins."""

    def after_run(self, results: list[StepResult[T, R]]) -> None:
        """Optional teardown/reporting hook after the run completes."""

    def before_step(self, index: int, item: T) -> None:
        """Optional hook before each step."""

    def after_step(self, step: StepResult[T, object]) -> None:
        """Optional hook after each step."""

    def emit_diagnostic(self, diagnostic: TemperatureDiagnostic) -> None:
        """Emit startup thermal diagnostic information for this script."""
        self.diagnostic_emitter(diagnostic)

    def _default_diagnostic_emitter(self, diagnostic: TemperatureDiagnostic) -> None:
        print(f"[GeoQA thermal] {diagnostic.message}")
        if diagnostic.ok:
            return
        for option in diagnostic.options:
            print(f"[GeoQA thermal] option: {option}")

    def run(self) -> list[StepResult[T, R]]:
        if self.emit_thermal_diagnostic:
            self.emit_diagnostic(run_temperature_diagnostic())
        self.before_run()
        results = self.runner.run_iterable(self.load_items(), self.process_item)
        self.after_run(results)
        return results


__all__ = ["GeoQAScriptBase"]
