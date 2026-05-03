# GeoQA Codex Prompt

This file contains instructions and rules for coding assistants when generating or modifying GeoQA library code. It ensures best practices, thermal safety, cross-platform compatibility, and Python version compliance.

## Working Instruction Block

You are a coding assistant for the GeoQA library. Follow these rules strictly:

1. Thermal Safety:
   - Use ThermalGuard and ThermalRunner for CPU-intensive loops.
   - Run optional thermal diagnostics at script startup via GeoQAScriptBase.
   - On platforms without temperature sensors, explain why readings may be unavailable and suggest alternatives.

2. Cross-Platform Compatibility:
   - Windows + Core Temp preferred when available.
   - Fallback to psutil for Windows, macOS, and Linux.
   - Avoid import-time errors on non-Windows platforms.

3. Python Version:
   - Code must run on Python 3.12 or higher.

4. Code Style:
   - Follow existing GeoQA patterns.
   - Use type hints and docstrings consistently.
   - Avoid printing unless emit_thermal_diagnostic=True.

## Task Behavior

When asked to add or modify GeoQA code:
- Generate or modify code according to these rules.
- Ensure compatibility with ThermalGuard, ThermalRunner, GeoQAScriptBase, and skills.md patterns.
- If new rules are introduced, ask: “Do you want to update AGENTS.md with these changes? (yes/no)”.

## Examples

Thermal-safe loop example:

```python
from geoqa import ThermalGuard, ThermalRunner

guard = ThermalGuard(warn_temp_c=76.0, max_temp_c=80.0)
runner = ThermalRunner[int](guard=guard)
results = runner.run_sequence([1, 2, 3], lambda item: item * 10)
```

GeoQAScriptBase usage example:

```python
from geoqa import GeoQAScriptBase


class MyScript(GeoQAScriptBase[str, str]):
    def load_items(self) -> list[str]:
        return ["a", "b", "c"]

    def process_item(self, item: str) -> str:
        return item.upper()


results = MyScript().run()
```
