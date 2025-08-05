from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RuleValidationResult:
    """Structured validation result for one analysis-rule file."""

    path: str
    source_exists: bool
    valid: bool
    errors: Sequence[str] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class RuleInspectionResult:
    """Current effective rule view plus optional source file details."""

    path: str
    source_exists: bool
    effective_rules: Mapping[str, Any]
    validation: RuleValidationResult
    source_rules: Mapping[str, Any] = field(default_factory=dict)
    default_rules: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleExportResult:
    """Describe one exported effective rule bundle."""

    source_path: str
    output_path: str
    bytes_written: int
    rule_versions: Mapping[str, str]


@dataclass(frozen=True)
class RuleDiffEntry:
    """One field-level rule difference."""

    path: str
    change_type: str
    left_value: Any
    right_value: Any


@dataclass(frozen=True)
class RuleDiffResult:
    """Structured rule diff output between two rule views."""

    left_label: str
    right_label: str
    left_path: str
    right_path: str
    left_validation: RuleValidationResult
    right_validation: RuleValidationResult
    diff_count: int
    diffs: Sequence[RuleDiffEntry] = field(default_factory=tuple)


@dataclass(frozen=True)
class RuleSectionEntrypoint:
    """Consumer-facing summary for one editable rule section."""

    name: str
    present: bool
    version: str
    editable_fields: Sequence[str] = field(default_factory=tuple)
    risky_fields: Sequence[str] = field(default_factory=tuple)
    field_count: int = 0
    rule_count: int = 0


@dataclass(frozen=True)
class RuleEntrypointDescription:
    """Stable Web/CLI contract for the local rule configuration entrypoint."""

    rule_path: str
    source_exists: bool
    config_versions: Mapping[str, str]
    sections: Mapping[str, RuleSectionEntrypoint]
    validation_summary: Mapping[str, Any]
    editable_fields: Mapping[str, Sequence[str]]
    risky_fields: Mapping[str, Sequence[str]]
    suggested_workflow: Sequence[str]
    audit_hint: str
    related_policy_paths: Mapping[str, str]


@dataclass(frozen=True)
class RuleEditPlan:
    """Dry-run edit plan for a proposed rule configuration change."""

    rule_path: str
    valid: bool
    errors: Sequence[str] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)
    patch: Mapping[str, Any] = field(default_factory=dict)
    validation: RuleValidationResult | None = None
    diff_count: int = 0
    diffs: Sequence[RuleDiffEntry] = field(default_factory=tuple)
    preview_rules: Mapping[str, Any] = field(default_factory=dict)
    requires_manual_save: bool = True
    suggested_workflow: Sequence[str] = field(default_factory=tuple)
    audit_hint: str = ""
    related_policy_paths: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RulePermissionBinding:
    """Permission grant for one actor on the local rule-governance surface."""

    actor_id: str
    role: str
    permissions: Sequence[str] = field(default_factory=tuple)
    scope: str = "analysis_rules"
    bound_by: str = ""
    bound_at: str = ""


@dataclass(frozen=True)
class RuleApprovalRecord:
    """One approval or rejection action for a candidate rule change."""

    approval_id: str
    candidate_id: str
    actor_id: str
    decision: str
    comment: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class RuleChangeCandidate:
    """Persisted candidate rule change awaiting review and publication."""

    candidate_id: str
    rule_path: str
    status: str
    created_by: str
    created_at: str
    title: str = ""
    reason: str = ""
    patch: Mapping[str, Any] = field(default_factory=dict)
    preview_rules: Mapping[str, Any] = field(default_factory=dict)
    validation: RuleValidationResult | None = None
    diff_count: int = 0
    diffs: Sequence[RuleDiffEntry] = field(default_factory=tuple)
    approvals: Sequence[RuleApprovalRecord] = field(default_factory=tuple)
    required_approvals: int = 1


@dataclass(frozen=True)
class RuleVersionRecord:
    """Published analysis-rule version record with rollback material."""

    version_id: str
    candidate_id: str
    rule_path: str
    published_by: str
    published_at: str
    checksum: str
    rule_versions: Mapping[str, str] = field(default_factory=dict)
    previous_version_id: str = ""
    rollback_of_version_id: str = ""
    rule_content: Mapping[str, Any] = field(default_factory=dict)
    previous_rule_content: Mapping[str, Any] = field(default_factory=dict)
    diff_count: int = 0


@dataclass(frozen=True)
class RuleRollbackResult:
    """Result of restoring a published rule version's previous content."""

    rollback_version: RuleVersionRecord
    restored_from_version_id: str
    restored_rule_path: str
    rolled_back_by: str
