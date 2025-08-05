from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .rule_replay_acceptance_models import RuleReplayGoldenSuiteResult


@dataclass(frozen=True)
class RuleReplayGoldenPromotionResult:
    """Describe one validated promotion from draft suite into target golden suite."""

    source_path: str
    target_path: str
    selected_case_ids: Sequence[str] = field(default_factory=tuple)
    promoted_case_ids: Sequence[str] = field(default_factory=tuple)
    replaced_case_ids: Sequence[str] = field(default_factory=tuple)
    skipped_case_ids: Sequence[str] = field(default_factory=tuple)
    target_suite_version: str = ""
    source_suite_version: str = ""
    promoted_case_count: int = 0
    replace_existing: bool = False
    acceptance: RuleReplayGoldenSuiteResult | None = None
