from __future__ import annotations

import time
from pathlib import Path

from geoqa import GeoQAScriptBase, ThermalGuard, ThermalLimitExceeded


class DemoScript(GeoQAScriptBase[int, str]):
    def __init__(self, *, guard: ThermalGuard) -> None:
        super().__init__(guard=guard)

    def load_items(self) -> list[int]:
        return [1, 2, 3, 4, 5]

    def process_item(self, item: int) -> str:
        print(f"running step {item}")
        time.sleep(1.5)
        return f"finished step {item}"

    def before_step(self, index: int, item: int) -> None:
        print(f"preparing step {index}: item={item}")

    def after_step(self, step) -> None:
        print(f"completed step {step.index}: temp={step.snapshot.max_temp_c}C result={step.result}")


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    log_path = project_root / "data" / "thermal_guard_log.jsonl"
    script = DemoScript(guard=ThermalGuard(log_path=log_path))

    try:
        script.run()
    except ThermalLimitExceeded as exc:
        print(f"stopped: {exc}")


if __name__ == "__main__":
    main()
