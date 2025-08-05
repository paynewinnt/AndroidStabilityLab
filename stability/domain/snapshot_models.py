from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class AnalysisSnapshotSummary:
    """Lightweight index entry for one persisted analysis snapshot."""

    snapshot_id: str
    snapshot_type: str
    name: str
    created_at: datetime
    created_by: str
    detail_path: str
    markdown_path: str = ""
    summary: Mapping[str, Any] = field(default_factory=dict)
    filters: Mapping[str, Any] = field(default_factory=dict)
    rule_versions: Mapping[str, Any] = field(default_factory=dict)
    source_summary: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisSnapshotRecord:
    """Full persisted analysis snapshot payload."""

    snapshot_id: str
    snapshot_type: str
    name: str
    created_at: datetime
    created_by: str
    scope: Mapping[str, Any] = field(default_factory=dict)
    filters: Mapping[str, Any] = field(default_factory=dict)
    data_range: Mapping[str, Any] = field(default_factory=dict)
    rule_versions: Mapping[str, Any] = field(default_factory=dict)
    summary: Mapping[str, Any] = field(default_factory=dict)
    source_refs: Mapping[str, Any] = field(default_factory=dict)
    detail_path: str = ""
    markdown_path: str = ""
    payload: Mapping[str, Any] = field(default_factory=dict)
    tags: Sequence[str] = field(default_factory=tuple)

    def to_summary(self) -> AnalysisSnapshotSummary:
        return AnalysisSnapshotSummary(
            snapshot_id=self.snapshot_id,
            snapshot_type=self.snapshot_type,
            name=self.name,
            created_at=self.created_at,
            created_by=self.created_by,
            detail_path=self.detail_path,
            markdown_path=self.markdown_path,
            summary=self.summary,
            filters=self.filters,
            rule_versions=self.rule_versions,
            source_summary=self.source_refs.get("summary", {}) if isinstance(self.source_refs, Mapping) else {},
        )
