from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Iterable, Sequence, TypeVar

from .thermal import TemperatureSnapshot, ThermalGuard


T = TypeVar("T")
R = TypeVar("R")


@dataclass(slots=True)
class StepResult(Generic[T, R]):
    index: int
    item: T
    result: R
    snapshot: TemperatureSnapshot


class ThermalRunner(Generic[T]):
    """
    Base runner for cooperative, thermal-aware script execution.

    Use this for loops or batch workloads where each step is a natural checkpoint.
    """

    def __init__(
        self,
        *,
        guard: ThermalGuard | None = None,
        before_step: Callable[[int, T], None] | None = None,
        after_step: Callable[[StepResult[T, object]], None] | None = None,
    ) -> None:
        self.guard = guard or ThermalGuard()
        self.before_step = before_step
        self.after_step = after_step

    def run_step(self, item: T, func: Callable[[T], R], *, index: int) -> StepResult[T, R]:
        if self.before_step:
            self.before_step(index, item)

        self.guard.wait_until_safe(stage=f"step_{index}_pre")
        result = func(item)
        snapshot = self.guard.check_or_raise(stage=f"step_{index}_post")
        self.guard.cool_down_if_needed(stage=f"step_{index}_cooldown")
        step_result = StepResult(index=index, item=item, result=result, snapshot=snapshot)

        if self.after_step:
            self.after_step(step_result)

        return step_result

    def run_iterable(self, items: Iterable[T], func: Callable[[T], R]) -> list[StepResult[T, R]]:
        results: list[StepResult[T, R]] = []
        with self.guard:
            for index, item in enumerate(items, start=1):
                results.append(self.run_step(item, func, index=index))
        return results

    def run_sequence(self, items: Sequence[T], func: Callable[[T], R]) -> list[StepResult[T, R]]:
        return self.run_iterable(items, func)


__all__ = ["StepResult", "ThermalRunner"]
