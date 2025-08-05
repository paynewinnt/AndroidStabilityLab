from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Protocol, Sequence


@dataclass(frozen=True)
class ScenarioExecutionResult:
    """Describe the outcome of one concrete template execution."""

    success: bool
    note: str = ""
    exit_reason: str = "completed"
    result_level: str = "passed"
    highlights: Sequence[str] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ScenarioRunner(Protocol):
    """Contract for template-specific execution implementations."""

    def execute(self, task, run, instance, layout, log_path) -> ScenarioExecutionResult:
        """Execute one task instance with a concrete template implementation."""
        ...
