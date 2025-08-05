from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .rule_replay_models import RuleReplayResult


@dataclass(frozen=True)
class RuleReplayGoldenDraftResult:
    """Result of exporting one semi-automatic replay golden draft from a real run."""

    output_path: str
    suite_version: str
    appended: bool
    case_id: str
    issue_type: str
    layer: str
    expectation: str
    issue_count: int
    source_run_id: str
    selected_issue_ids: Sequence[str] = field(default_factory=tuple)
    selected_instance_ids: Sequence[str] = field(default_factory=tuple)
    baseline_path: str = ""
    candidate_path: str = ""
    expected: Mapping[str, object] = field(default_factory=dict)
    replay_preview: RuleReplayResult | None = None
