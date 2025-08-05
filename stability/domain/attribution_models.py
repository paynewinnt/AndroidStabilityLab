from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .enums import IssueType


@dataclass(frozen=True)
class AttributionHit:
    """One matched attribution clue that explains why one rule was selected."""

    field: str
    keyword: str
    evidence: str
    score: int = 0


@dataclass(frozen=True)
class IssueAttribution:
    """Rule-based preliminary attribution result for one aggregated issue group."""

    fingerprint: str
    issue_type: IssueType
    title: str
    direction: str
    direction_label: str
    confidence: str
    summary: str
    rule_version: str = "v1"
    matched_rule_id: str = ""
    matched_rule_name: str = ""
    matched_rule_ids: Sequence[str] = field(default_factory=tuple)
    confidence_score: float = 0.0
    score: int = 0
    evidence_summary: Sequence[str] = field(default_factory=tuple)
    recommended_next_steps: Sequence[str] = field(default_factory=tuple)
    review_notes: Sequence[str] = field(default_factory=tuple)
    sample_event_ids: Sequence[str] = field(default_factory=tuple)
    hits: Sequence[AttributionHit] = field(default_factory=tuple)
    notes: Sequence[str] = field(default_factory=tuple)
