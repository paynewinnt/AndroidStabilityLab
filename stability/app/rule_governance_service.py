from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from stability.domain import AnalysisRuleConfig, AttributionRule, IssueType
from stability.infrastructure import FileBackedRuleConfigProvider, default_analysis_rule_config
from .rule_governance_lifecycle import RuleGovernanceLifecycleMixin
from .rule_governance_models import (
    RuleApprovalRecord,
    RuleChangeCandidate,
    RuleDiffEntry,
    RuleDiffResult,
    RuleEditPlan,
    RuleEntrypointDescription,
    RuleExportResult,
    RuleInspectionResult,
    RulePermissionBinding,
    RuleRollbackResult,
    RuleSectionEntrypoint,
    RuleValidationResult,
    RuleVersionRecord,
)


class RuleGovernanceService(RuleGovernanceLifecycleMixin):
    """First-batch governance helpers for local rule inspection, validation, and export."""

    _TOP_LEVEL_KEYS = frozenset({"fingerprint", "regression", "attribution"})
    _FINGERPRINT_KEYS = frozenset({"version", "ignore_raw_key_issue_types"})
    _REGRESSION_KEYS = frozenset(
        {
            "version",
            "min_side_issue_groups",
            "significant_occurrence_delta",
            "significant_affected_run_delta",
            "significant_affected_device_delta",
            "significant_affected_scenario_delta",
            "min_side_metric_sessions",
            "min_side_metric_samples",
            "significant_metric_delta_ratio",
        }
    )
    _ATTRIBUTION_KEYS = frozenset(
        {"version", "fallback_direction", "medium_confidence_score", "high_confidence_score", "rules"}
    )
    _ATTRIBUTION_RULE_KEYS = frozenset(
        {
            "rule_id",
            "name",
            "direction",
            "issue_types",
            "scored_issue_types",
            "issue_type_score",
            "title_keywords",
            "summary_keywords",
            "process_keywords",
            "artifact_keywords",
            "metadata_keywords",
            "evidence_signal_keywords",
            "evidence_source_keywords",
            "matched_fragment_keywords",
            "confirmation_level_scores",
            "recommended_next_steps",
            "review_notes",
            "package_process_match",
        }
    )
    _EDITABLE_FIELDS = {
        "fingerprint": ("version", "ignore_raw_key_issue_types"),
        "regression": tuple(sorted(_REGRESSION_KEYS)),
        "attribution": tuple(sorted(_ATTRIBUTION_KEYS)),
    }
    _RISKY_FIELDS = {
        "fingerprint": ("version", "ignore_raw_key_issue_types"),
        "regression": (
            "min_side_issue_groups",
            "significant_occurrence_delta",
            "significant_affected_run_delta",
            "significant_affected_device_delta",
            "significant_affected_scenario_delta",
            "significant_metric_delta_ratio",
            "version",
        ),
        "attribution": (
            "high_confidence_score",
            "medium_confidence_score",
            "rules",
            "version",
        ),
    }
    _SUGGESTED_WORKFLOW = (
        "Inspect the entrypoint summary and current validation status.",
        "Build a dry-run edit plan for the intended section/key/value or patch payload.",
        "Save a candidate change only after validation and field-level diffs are clean.",
        "Approve the candidate with a reviewer actor that has rule-governance permission.",
        "Publish the approved candidate to create a version record and rollback material.",
        "Run rule review/replay gates against the related policy files before broad promotion.",
    )
    _AUDIT_HINT = (
        "This service persists candidates, approvals, published versions, rollback material, and actor "
        "permission bindings under the local rule_governance directory."
    )

    def __init__(self, *, rule_path: str | Path = "config/stability_rules.json") -> None:
        self._rule_path = Path(rule_path)

    @property
    def rule_path(self) -> Path:
        return self._rule_path

    def inspect_rules(self, path: str | Path | None = None) -> RuleInspectionResult:
        resolved_path = self._resolve_path(path)
        source_exists = resolved_path.exists()
        validation = self.validate_rules(resolved_path)
        source_rules = self._read_source_rules(resolved_path) if source_exists else {}
        return RuleInspectionResult(
            path=str(resolved_path),
            source_exists=source_exists,
            effective_rules=self._effective_rules_payload(resolved_path),
            validation=validation,
            source_rules=source_rules,
            default_rules=self._serialize_rule_config(default_analysis_rule_config()),
        )

    def validate_rules(self, path: str | Path | None = None) -> RuleValidationResult:
        resolved_path = self._resolve_path(path)
        if not resolved_path.exists():
            return RuleValidationResult(
                path=str(resolved_path),
                source_exists=False,
                valid=False,
                errors=(f"Rule file '{resolved_path}' does not exist.",),
                warnings=(),
            )

        try:
            payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return RuleValidationResult(
                path=str(resolved_path),
                source_exists=True,
                valid=False,
                errors=(f"Invalid JSON: {exc}",),
                warnings=(),
            )

        return self._validate_rules_payload(payload, resolved_path, source_exists=True)

    def _validate_rules_payload(
        self,
        payload: Any,
        path: Path,
        *,
        source_exists: bool,
    ) -> RuleValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        if not isinstance(payload, dict):
            errors.append("Rule file root must be a JSON object.")
            return RuleValidationResult(
                path=str(path),
                source_exists=source_exists,
                valid=False,
                errors=tuple(errors),
                warnings=tuple(warnings),
            )

        self._warn_unknown_keys("root", payload, self._TOP_LEVEL_KEYS, warnings)
        self._validate_fingerprint_section(payload.get("fingerprint"), errors, warnings)
        self._validate_regression_section(payload.get("regression"), errors, warnings)
        self._validate_attribution_section(payload.get("attribution"), errors, warnings)
        return RuleValidationResult(
            path=str(path),
            source_exists=source_exists,
            valid=not errors,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    def export_effective_rules(
        self,
        output_path: str | Path,
        *,
        path: str | Path | None = None,
        overwrite: bool = False,
    ) -> RuleExportResult:
        resolved_output = Path(output_path)
        if resolved_output.exists() and not overwrite:
            raise FileExistsError(f"Rule export target '{resolved_output}' already exists.")

        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        payload = self._effective_rules_payload(path)
        content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        resolved_output.write_text(content, encoding="utf-8")
        return RuleExportResult(
            source_path=str(self._resolve_path(path)),
            output_path=str(resolved_output),
            bytes_written=len(content.encode("utf-8")),
            rule_versions={
                "fingerprint": str(payload.get("fingerprint", {}).get("version", "")),
                "regression": str(payload.get("regression", {}).get("version", "")),
                "attribution": str(payload.get("attribution", {}).get("version", "")),
            },
        )

    def diff_rules(
        self,
        *,
        left_path: str | Path | None = None,
        right_path: str | Path | None = None,
        left_view: str = "effective",
        right_view: str = "source",
    ) -> RuleDiffResult:
        resolved_left_path = self._resolve_path(left_path)
        resolved_right_path = self._resolve_path(right_path)
        left_validation = self.validate_rules(resolved_left_path)
        right_validation = self.validate_rules(resolved_right_path)
        left_payload = self._payload_for_view(resolved_left_path, left_view, left_validation)
        right_payload = self._payload_for_view(resolved_right_path, right_view, right_validation)
        diffs = tuple(self._diff_mapping("", left_payload, right_payload))
        return RuleDiffResult(
            left_label=f"{left_view}:{resolved_left_path}",
            right_label=f"{right_view}:{resolved_right_path}",
            left_path=str(resolved_left_path),
            right_path=str(resolved_right_path),
            left_validation=left_validation,
            right_validation=right_validation,
            diff_count=len(diffs),
            diffs=diffs,
        )

    def describe_rule_entrypoint(self, path: str | Path | None = None) -> RuleEntrypointDescription:
        """Return a stable summary contract for Web/CLI rule configuration screens."""

        resolved_path = self._resolve_path(path)
        inspection = self.inspect_rules(resolved_path)
        effective_rules = inspection.effective_rules
        return RuleEntrypointDescription(
            rule_path=str(resolved_path),
            source_exists=inspection.source_exists,
            config_versions=self._config_versions(effective_rules, resolved_path),
            sections=self._section_entrypoints(inspection.source_rules, effective_rules),
            validation_summary=self._validation_summary(inspection.validation),
            editable_fields=self._EDITABLE_FIELDS,
            risky_fields=self._RISKY_FIELDS,
            suggested_workflow=self._SUGGESTED_WORKFLOW,
            audit_hint=self._AUDIT_HINT,
            related_policy_paths=self._related_policy_paths(resolved_path),
        )

    def build_rule_edit_plan(
        self,
        *,
        section: str | None = None,
        key: str | None = None,
        value: Any = None,
        patch: Mapping[str, Any] | None = None,
        path: str | Path | None = None,
    ) -> RuleEditPlan:
        """Validate and diff a proposed rule edit without writing the rule file."""

        resolved_path = self._resolve_path(path)
        source_rules = dict(self._read_source_rules(resolved_path))
        if not source_rules:
            source_rules = self._effective_rules_payload(resolved_path)

        patch_errors: list[str] = []
        normalized_patch = self._normalize_edit_patch(section=section, key=key, value=value, patch=patch, errors=patch_errors)
        if patch_errors:
            return self._invalid_edit_plan(resolved_path, normalized_patch, patch_errors)

        preview_rules = self._merge_rule_patch(source_rules, normalized_patch)
        validation = self._validate_rules_payload(preview_rules, resolved_path, source_exists=resolved_path.exists())
        diffs = tuple(self._diff_mapping("", source_rules, preview_rules))
        plan_errors = list(validation.errors)
        return RuleEditPlan(
            rule_path=str(resolved_path),
            valid=validation.valid,
            errors=tuple(plan_errors),
            warnings=tuple(validation.warnings),
            patch=normalized_patch,
            validation=validation,
            diff_count=len(diffs),
            diffs=diffs,
            preview_rules=preview_rules,
            requires_manual_save=True,
            suggested_workflow=self._SUGGESTED_WORKFLOW,
            audit_hint=self._AUDIT_HINT,
            related_policy_paths=self._related_policy_paths(resolved_path),
        )

    def preview_rule_update(
        self,
        patch: Mapping[str, Any],
        *,
        path: str | Path | None = None,
    ) -> RuleEditPlan:
        """Convenience alias for dry-running a patch payload."""

        return self.build_rule_edit_plan(patch=patch, path=path)

    def _effective_rules_payload(self, path: str | Path | None = None) -> dict[str, Any]:
        provider = FileBackedRuleConfigProvider(self._resolve_path(path))
        return self._serialize_rule_config(provider.load())

    def _payload_for_view(
        self,
        path: Path,
        view: str,
        validation: RuleValidationResult,
    ) -> Mapping[str, Any]:
        normalized_view = view.strip().lower()
        if normalized_view == "default":
            return self._serialize_rule_config(default_analysis_rule_config())
        if normalized_view == "source":
            return self._read_source_rules(path)
        if normalized_view == "effective":
            if not validation.valid and validation.source_exists:
                raise ValueError(f"Cannot load effective rules from invalid file '{path}'.")
            return self._effective_rules_payload(path)
        raise ValueError(f"Unsupported rule view '{view}'. Expected source/effective/default.")

    def _read_source_rules(self, path: Path) -> Mapping[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _config_versions(self, rules: Mapping[str, Any], rule_path: Path) -> Mapping[str, str]:
        versions: dict[str, str] = {}
        for section in sorted(self._TOP_LEVEL_KEYS):
            value = rules.get(section)
            if isinstance(value, Mapping):
                versions[section] = str(value.get("version", ""))
            else:
                versions[section] = ""
        for name, policy_path in self._related_policy_paths(rule_path).items():
            versions[name] = self._read_policy_version(Path(policy_path))
        return versions

    def _section_entrypoints(
        self,
        source_rules: Mapping[str, Any],
        effective_rules: Mapping[str, Any],
    ) -> Mapping[str, RuleSectionEntrypoint]:
        sections: dict[str, RuleSectionEntrypoint] = {}
        for name in ("fingerprint", "regression", "attribution"):
            source_section = source_rules.get(name)
            effective_section = effective_rules.get(name)
            section = source_section if isinstance(source_section, Mapping) else effective_section
            section_mapping = section if isinstance(section, Mapping) else {}
            rules = section_mapping.get("rules")
            sections[name] = RuleSectionEntrypoint(
                name=name,
                present=isinstance(source_section, Mapping),
                version=str(section_mapping.get("version", "")),
                editable_fields=self._EDITABLE_FIELDS[name],
                risky_fields=self._RISKY_FIELDS[name],
                field_count=len(section_mapping),
                rule_count=len(rules) if isinstance(rules, list) else 0,
            )
        return sections

    @staticmethod
    def _validation_summary(validation: RuleValidationResult) -> Mapping[str, Any]:
        return {
            "valid": validation.valid,
            "source_exists": validation.source_exists,
            "error_count": len(validation.errors),
            "warning_count": len(validation.warnings),
            "errors": tuple(validation.errors),
            "warnings": tuple(validation.warnings),
        }

    def _related_policy_paths(self, rule_path: Path) -> Mapping[str, str]:
        config_dir = rule_path.parent if rule_path.parent != Path("") else Path("config")
        return {
            "rule_review_policy": str(config_dir / "rule_review_policy.json"),
            "rule_review_baseline_policy": str(config_dir / "rule_review_baseline_policy.json"),
        }

    @staticmethod
    def _read_policy_version(path: Path) -> str:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        if not isinstance(payload, Mapping):
            return ""
        return str(payload.get("version", ""))

    def _normalize_edit_patch(
        self,
        *,
        section: str | None,
        key: str | None,
        value: Any,
        patch: Mapping[str, Any] | None,
        errors: list[str],
    ) -> Mapping[str, Any]:
        if patch is not None and (section is not None or key is not None):
            errors.append("Use either patch payload or section/key/value, not both.")
            return dict(patch)
        if patch is None:
            if section is None or key is None:
                errors.append("section and key are required when patch payload is not provided.")
                return {}
            patch = {section: {key: value}}
        if not isinstance(patch, Mapping):
            errors.append("patch must be a JSON object keyed by rule section.")
            return {}

        normalized: dict[str, Any] = {}
        for section_name, section_patch in patch.items():
            if not isinstance(section_name, str):
                errors.append("patch section names must be strings.")
                continue
            if section_name not in self._TOP_LEVEL_KEYS:
                errors.append(f"Unsupported rule section '{section_name}'.")
                continue
            if not isinstance(section_patch, Mapping):
                errors.append(f"patch.{section_name} must be a JSON object of field updates.")
                continue
            normalized_section: dict[str, Any] = {}
            for field_name, field_value in section_patch.items():
                if not isinstance(field_name, str):
                    errors.append(f"patch.{section_name} field names must be strings.")
                    continue
                if field_name not in self._EDITABLE_FIELDS[section_name]:
                    errors.append(f"Unsupported editable field '{section_name}.{field_name}'.")
                    continue
                normalized_section[field_name] = field_value
            if normalized_section:
                normalized[section_name] = normalized_section
        if not normalized and not errors:
            errors.append("patch must include at least one editable field.")
        return normalized

    @staticmethod
    def _merge_rule_patch(source_rules: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
        merged = json.loads(json.dumps(source_rules, ensure_ascii=False))
        for section_name, section_patch in patch.items():
            section = merged.get(section_name)
            if not isinstance(section, dict):
                section = {}
                merged[section_name] = section
            for field_name, field_value in section_patch.items():
                section[field_name] = field_value
        return merged

    def _invalid_edit_plan(
        self,
        resolved_path: Path,
        patch: Mapping[str, Any],
        errors: Sequence[str],
    ) -> RuleEditPlan:
        return RuleEditPlan(
            rule_path=str(resolved_path),
            valid=False,
            errors=tuple(errors),
            warnings=(),
            patch=patch,
            validation=None,
            diff_count=0,
            diffs=(),
            preview_rules={},
            requires_manual_save=True,
            suggested_workflow=self._SUGGESTED_WORKFLOW,
            audit_hint=self._AUDIT_HINT,
            related_policy_paths=self._related_policy_paths(resolved_path),
        )

    @classmethod
    def _diff_mapping(cls, prefix: str, left: Any, right: Any) -> list[RuleDiffEntry]:
        if isinstance(left, Mapping) and isinstance(right, Mapping):
            diffs: list[RuleDiffEntry] = []
            keys = sorted(set(left.keys()) | set(right.keys()))
            for key in keys:
                child_prefix = f"{prefix}.{key}" if prefix else str(key)
                if key not in left:
                    diffs.append(
                        RuleDiffEntry(
                            path=child_prefix,
                            change_type="added",
                            left_value=None,
                            right_value=right[key],
                        )
                    )
                    continue
                if key not in right:
                    diffs.append(
                        RuleDiffEntry(
                            path=child_prefix,
                            change_type="removed",
                            left_value=left[key],
                            right_value=None,
                        )
                    )
                    continue
                diffs.extend(cls._diff_mapping(child_prefix, left[key], right[key]))
            return diffs

        if left != right:
            return [
                RuleDiffEntry(
                    path=prefix or "$",
                    change_type="changed",
                    left_value=left,
                    right_value=right,
                )
            ]
        return []

    def _resolve_path(self, path: str | Path | None) -> Path:
        return Path(path) if path is not None else self._rule_path

    @classmethod
    def _serialize_rule_config(cls, config: AnalysisRuleConfig) -> dict[str, Any]:
        return {
            "fingerprint": {
                "version": config.fingerprint.version,
                "ignore_raw_key_issue_types": [item.value for item in config.fingerprint.ignore_raw_key_issue_types],
            },
            "regression": config.regression.as_dict(),
            "attribution": {
                "version": config.attribution.version,
                "fallback_direction": config.attribution.fallback_direction,
                "medium_confidence_score": config.attribution.medium_confidence_score,
                "high_confidence_score": config.attribution.high_confidence_score,
                "rules": [cls._serialize_attribution_rule(item) for item in config.attribution.rules],
            },
        }

    @staticmethod
    def _serialize_attribution_rule(rule: AttributionRule) -> dict[str, Any]:
        return {
            "rule_id": rule.rule_id,
            "name": rule.name,
            "direction": rule.direction,
            "issue_types": [item.value for item in rule.issue_types],
            "scored_issue_types": [item.value for item in rule.scored_issue_types],
            "issue_type_score": rule.issue_type_score,
            "title_keywords": list(rule.title_keywords),
            "summary_keywords": list(rule.summary_keywords),
            "process_keywords": list(rule.process_keywords),
            "artifact_keywords": list(rule.artifact_keywords),
            "metadata_keywords": list(rule.metadata_keywords),
            "evidence_signal_keywords": list(rule.evidence_signal_keywords),
            "evidence_source_keywords": list(rule.evidence_source_keywords),
            "matched_fragment_keywords": list(rule.matched_fragment_keywords),
            "confirmation_level_scores": dict(rule.confirmation_level_scores),
            "recommended_next_steps": list(rule.recommended_next_steps),
            "review_notes": list(rule.review_notes),
            "package_process_match": rule.package_process_match,
        }

    @classmethod
    def _validate_fingerprint_section(cls, value: Any, errors: list[str], warnings: list[str]) -> None:
        section = cls._require_mapping("fingerprint", value, errors)
        if section is None:
            return
        cls._warn_unknown_keys("fingerprint", section, cls._FINGERPRINT_KEYS, warnings)
        cls._require_string("fingerprint.version", section.get("version"), errors, allow_missing=True)
        cls._require_issue_type_list(
            "fingerprint.ignore_raw_key_issue_types",
            section.get("ignore_raw_key_issue_types"),
            errors,
            allow_missing=True,
        )

    @classmethod
    def _validate_regression_section(cls, value: Any, errors: list[str], warnings: list[str]) -> None:
        section = cls._require_mapping("regression", value, errors)
        if section is None:
            return
        cls._warn_unknown_keys("regression", section, cls._REGRESSION_KEYS, warnings)
        cls._require_string("regression.version", section.get("version"), errors, allow_missing=True)
        for key in (
            "min_side_issue_groups",
            "significant_occurrence_delta",
            "significant_affected_run_delta",
            "significant_affected_device_delta",
            "significant_affected_scenario_delta",
            "min_side_metric_sessions",
            "min_side_metric_samples",
        ):
            cls._require_int(f"regression.{key}", section.get(key), errors, allow_missing=True)
        cls._require_float(
            "regression.significant_metric_delta_ratio",
            section.get("significant_metric_delta_ratio"),
            errors,
            allow_missing=True,
        )

    @classmethod
    def _validate_attribution_section(cls, value: Any, errors: list[str], warnings: list[str]) -> None:
        section = cls._require_mapping("attribution", value, errors)
        if section is None:
            return
        cls._warn_unknown_keys("attribution", section, cls._ATTRIBUTION_KEYS, warnings)
        cls._require_string("attribution.version", section.get("version"), errors, allow_missing=True)
        cls._require_string("attribution.fallback_direction", section.get("fallback_direction"), errors, allow_missing=True)
        cls._require_int("attribution.medium_confidence_score", section.get("medium_confidence_score"), errors, allow_missing=True)
        cls._require_int("attribution.high_confidence_score", section.get("high_confidence_score"), errors, allow_missing=True)
        rules = section.get("rules")
        if rules is None:
            return
        if not isinstance(rules, list):
            errors.append("attribution.rules must be a JSON array.")
            return
        for index, item in enumerate(rules):
            if not isinstance(item, dict):
                errors.append(f"attribution.rules[{index}] must be a JSON object.")
                continue
            cls._warn_unknown_keys(f"attribution.rules[{index}]", item, cls._ATTRIBUTION_RULE_KEYS, warnings)
            cls._require_string(f"attribution.rules[{index}].rule_id", item.get("rule_id"), errors)
            cls._require_string(f"attribution.rules[{index}].name", item.get("name"), errors, allow_missing=True)
            cls._require_string(
                f"attribution.rules[{index}].direction",
                item.get("direction"),
                errors,
                allow_missing=True,
            )
            cls._require_issue_type_list(
                f"attribution.rules[{index}].issue_types",
                item.get("issue_types"),
                errors,
                allow_missing=True,
            )
            cls._require_issue_type_list(
                f"attribution.rules[{index}].scored_issue_types",
                item.get("scored_issue_types"),
                errors,
                allow_missing=True,
            )
            cls._require_int(
                f"attribution.rules[{index}].issue_type_score",
                item.get("issue_type_score"),
                errors,
                allow_missing=True,
            )
            for key in (
                "title_keywords",
                "summary_keywords",
                "process_keywords",
                "artifact_keywords",
                "metadata_keywords",
                "evidence_signal_keywords",
                "evidence_source_keywords",
                "matched_fragment_keywords",
                "recommended_next_steps",
                "review_notes",
            ):
                cls._require_string_list(
                    f"attribution.rules[{index}].{key}",
                    item.get(key),
                    errors,
                    allow_missing=True,
                )
            cls._require_score_mapping(
                f"attribution.rules[{index}].confirmation_level_scores",
                item.get("confirmation_level_scores"),
                errors,
                allow_missing=True,
            )
            cls._require_bool(
                f"attribution.rules[{index}].package_process_match",
                item.get("package_process_match"),
                errors,
                allow_missing=True,
            )

    @staticmethod
    def _warn_unknown_keys(
        scope: str,
        payload: Mapping[str, Any],
        allowed_keys: Sequence[str],
        warnings: list[str],
    ) -> None:
        allowed = set(allowed_keys)
        for key in payload:
            if key not in allowed:
                warnings.append(f"Unknown key '{scope}.{key}' will be ignored.")

    @staticmethod
    def _require_mapping(scope: str, value: Any, errors: list[str]) -> Mapping[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            errors.append(f"{scope} must be a JSON object.")
            return None
        return value

    @staticmethod
    def _require_string(scope: str, value: Any, errors: list[str], *, allow_missing: bool = False) -> None:
        if value is None and allow_missing:
            return
        if not isinstance(value, str):
            errors.append(f"{scope} must be a string.")

    @staticmethod
    def _require_int(scope: str, value: Any, errors: list[str], *, allow_missing: bool = False) -> None:
        if value is None and allow_missing:
            return
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{scope} must be an integer.")

    @staticmethod
    def _require_float(scope: str, value: Any, errors: list[str], *, allow_missing: bool = False) -> None:
        if value is None and allow_missing:
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{scope} must be a number.")

    @staticmethod
    def _require_bool(scope: str, value: Any, errors: list[str], *, allow_missing: bool = False) -> None:
        if value is None and allow_missing:
            return
        if not isinstance(value, bool):
            errors.append(f"{scope} must be a boolean.")

    @classmethod
    def _require_string_list(cls, scope: str, value: Any, errors: list[str], *, allow_missing: bool = False) -> None:
        if value is None and allow_missing:
            return
        if not isinstance(value, list):
            errors.append(f"{scope} must be a JSON array of strings.")
            return
        for index, item in enumerate(value):
            if not isinstance(item, str):
                errors.append(f"{scope}[{index}] must be a string.")

    @classmethod
    def _require_issue_type_list(cls, scope: str, value: Any, errors: list[str], *, allow_missing: bool = False) -> None:
        if value is None and allow_missing:
            return
        if not isinstance(value, list):
            errors.append(f"{scope} must be a JSON array of issue-type strings.")
            return
        valid_values = {item.value for item in IssueType}
        for index, item in enumerate(value):
            if not isinstance(item, str):
                errors.append(f"{scope}[{index}] must be a string.")
                continue
            if item not in valid_values:
                errors.append(f"{scope}[{index}] has unsupported issue type '{item}'.")

    @classmethod
    def _require_score_mapping(cls, scope: str, value: Any, errors: list[str], *, allow_missing: bool = False) -> None:
        if value is None and allow_missing:
            return
        if not isinstance(value, dict):
            errors.append(f"{scope} must be a JSON object mapping strings to integer scores.")
            return
        for key, score in value.items():
            if not isinstance(key, str):
                errors.append(f"{scope} keys must be strings.")
            cls._require_int(f"{scope}.{key}", score, errors)
