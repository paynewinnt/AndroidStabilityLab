from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from stability.domain import QualityGateRiskItem, RuleReviewFinding, RuleReviewResult

from .rule_replay_acceptance_service import RuleReplayAcceptanceService
from .rule_governance_service import RuleGovernanceService
from .rule_replay_service import RuleReplayService


class RuleReviewService:
    """Turn rule replay output into a minimal rule-admission decision."""

    def __init__(
        self,
        *,
        rule_replay_service: RuleReplayService,
        rule_governance_service: RuleGovernanceService,
        rule_replay_acceptance_service: RuleReplayAcceptanceService | None = None,
        policy_path: str | Path = "config/rule_review_policy.json",
        performance_risk_provider: Callable[..., Sequence[QualityGateRiskItem | Mapping[str, Any]] | Mapping[str, Any]]
        | None = None,
    ) -> None:
        self._rule_replay_service = rule_replay_service
        self._rule_governance_service = rule_governance_service
        self._rule_replay_acceptance_service = rule_replay_acceptance_service or RuleReplayAcceptanceService()
        self._policy_path = Path(policy_path)
        self._performance_risk_provider = performance_risk_provider

    def review_rule_change(self, **filters: Any) -> RuleReviewResult:
        candidate_path = str(filters.get("candidate_path", "") or "").strip()
        baseline_path = str(filters.get("baseline_path", "") or "").strip()
        if not candidate_path:
            raise ValueError("candidate_path is required for rule review.")

        resolved_baseline = baseline_path or str(self._rule_governance_service.rule_path)
        baseline_validation = self._rule_governance_service.validate_rules(resolved_baseline)
        candidate_validation = self._rule_governance_service.validate_rules(candidate_path)
        policy_path = Path(str(filters.get("policy_path", "") or "").strip() or self._policy_path)
        policy = self._load_policy(policy_path)
        findings: list[RuleReviewFinding] = []
        reasons: list[str] = []

        if not baseline_validation.valid:
            findings.append(
                RuleReviewFinding(
                    level="fail",
                    scope="rule_validation",
                    issue_type="",
                    change_type="baseline_invalid",
                    observed_count=len(baseline_validation.errors),
                    threshold=0,
                    message=f"Baseline rule file is invalid: {baseline_validation.errors[0]}",
                )
            )
        if not candidate_validation.valid:
            findings.append(
                RuleReviewFinding(
                    level="fail",
                    scope="rule_validation",
                    issue_type="",
                    change_type="candidate_invalid",
                    observed_count=len(candidate_validation.errors),
                    threshold=0,
                    message=f"Candidate rule file is invalid: {candidate_validation.errors[0]}",
                )
            )

        normalized_filters = self._normalized_filters(filters)
        if findings:
            reasons.append(findings[0].message)
            return RuleReviewResult(
                decision="fail",
                policy_version=str(policy.get("version", "v1") or "v1"),
                policy_path=str(policy_path),
                baseline_path=resolved_baseline,
                candidate_path=candidate_path,
                baseline_rule_version="",
                candidate_rule_version="",
                filters=normalized_filters,
                family_count=0,
                changed_family_count=0,
                findings=tuple(findings),
                reasons=tuple(reasons),
                baseline_valid=baseline_validation.valid,
                candidate_valid=candidate_validation.valid,
                baseline_errors=tuple(baseline_validation.errors),
                candidate_errors=tuple(candidate_validation.errors),
                golden_suite=None,
                performance_summary={},
                performance_risk_items=(),
                families=(),
            )

        replay = self._rule_replay_service.replay_top_issues(**filters)
        issue_type_change_summary = self._issue_type_change_summary(replay.families)
        golden_suite = self._rule_replay_acceptance_service.verify_golden_suite()
        performance_summary, performance_risk_items = self._performance_context(filters)

        minimum_family_count = int(policy.get("minimum_family_count", 1) or 1)
        if replay.family_count < minimum_family_count:
            findings.append(
                RuleReviewFinding(
                    level="warning",
                    scope="coverage",
                    issue_type="",
                    change_type="insufficient_family_count",
                    observed_count=replay.family_count,
                    threshold=minimum_family_count,
                    message=(
                        f"Replay only covered {replay.family_count} issue families, below the minimum "
                        f"required {minimum_family_count}."
                    ),
                )
            )

        findings.extend(
            self._evaluate_change_limits(
                change_summary=dict(replay.change_summary),
                issue_type_change_summary=issue_type_change_summary,
                policy=policy,
            )
        )
        if golden_suite.failed_case_count > 0:
            findings.append(
                RuleReviewFinding(
                    level="fail",
                    scope="golden_suite",
                    issue_type="",
                    change_type="golden_suite_failed",
                    observed_count=golden_suite.failed_case_count,
                    threshold=0,
                    message=(
                        f"Golden replay suite failed {golden_suite.failed_case_count} case(s) out of "
                        f"{golden_suite.case_count}."
                    ),
                )
            )

        fail_findings = [item for item in findings if item.level == "fail"]
        warning_findings = [item for item in findings if item.level == "warning"]
        if fail_findings:
            decision = "fail"
            reasons.append(fail_findings[0].message)
        elif warning_findings:
            decision = "conditional_pass"
            reasons.append(warning_findings[0].message)
        else:
            decision = "pass"
            reasons.append("Replay stayed within configured review thresholds.")
        review_filters = dict(replay.filters)
        for key, value in normalized_filters.items():
            if key not in review_filters or key in {"dimension", "left_value", "right_value"}:
                review_filters[key] = value

        return RuleReviewResult(
            decision=decision,
            policy_version=str(policy.get("version", "v1") or "v1"),
            policy_path=str(policy_path),
            baseline_path=replay.baseline.path,
            candidate_path=replay.candidate.path,
            baseline_rule_version=replay.baseline.fingerprint_rule_version,
            candidate_rule_version=replay.candidate.fingerprint_rule_version,
            filters=review_filters,
            family_count=replay.family_count,
            changed_family_count=replay.changed_family_count,
            change_summary=dict(replay.change_summary),
            issue_type_change_summary=issue_type_change_summary,
            findings=tuple(findings),
            reasons=tuple(reasons),
            baseline_valid=baseline_validation.valid,
            candidate_valid=candidate_validation.valid,
            baseline_errors=tuple(baseline_validation.errors),
            candidate_errors=tuple(candidate_validation.errors),
            golden_suite=golden_suite,
            performance_summary=performance_summary,
            performance_risk_items=performance_risk_items,
            families=tuple(replay.families),
        )

    @staticmethod
    def _normalized_filters(filters: Mapping[str, Any]) -> dict[str, object]:
        allowed = (
            "task_id",
            "run_status",
            "template_type",
            "version",
            "package_name",
            "device_id",
            "issue_type",
            "created_from",
            "created_to",
            "limit",
            "include_unchanged",
            "dimension",
            "left_value",
            "right_value",
        )
        normalized: dict[str, object] = {}
        for key in allowed:
            value = filters.get(key)
            if value in (None, "", (), [], {}):
                continue
            normalized[key] = value
        return normalized

    def _load_policy(self, path: Path) -> Mapping[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Rule review policy '{path}' does not exist.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("Rule review policy root must be a JSON object.")
        return payload

    def _performance_context(
        self,
        filters: Mapping[str, Any],
    ) -> tuple[dict[str, Any], tuple[QualityGateRiskItem, ...]]:
        provider = self._performance_risk_provider
        if provider is None:
            return {}, ()

        raw_payload = provider(**filters)
        summary: dict[str, Any] = {}
        raw_items: Any = raw_payload
        if isinstance(raw_payload, Mapping):
            raw_items = (
                raw_payload.get("items")
                or raw_payload.get("performance_risk_items")
                or raw_payload.get("risks")
                or ()
            )
            summary = {
                "dimension": str(raw_payload.get("dimension", "") or ""),
                "left_scope": dict(raw_payload.get("left_scope", {}) or {}),
                "right_scope": dict(raw_payload.get("right_scope", {}) or {}),
                "sample_summary": dict(raw_payload.get("sample_summary", {}) or {}),
                "metric_result_summary": dict(raw_payload.get("metric_result_summary", {}) or {}),
                "comparability_notes": [
                    str(item)
                    for item in (raw_payload.get("comparability_notes", ()) or ())
                    if str(item).strip()
                ],
            }
            summary = {key: value for key, value in summary.items() if value not in ("", {}, [], (), None)}

        items = tuple(self._normalize_performance_risk_items(raw_items))
        if summary or items:
            summary = dict(summary)
            summary["performance_risk_count"] = len(items)
        return summary, items

    @staticmethod
    def _normalize_performance_risk_items(
        items: Sequence[QualityGateRiskItem | Mapping[str, Any]] | Mapping[str, Any] | None,
    ) -> list[QualityGateRiskItem]:
        if items is None:
            return []
        raw_items: Sequence[Any]
        if isinstance(items, Mapping):
            raw_items = [items]
        else:
            raw_items = list(items)

        normalized: list[QualityGateRiskItem] = []
        for index, item in enumerate(raw_items):
            if isinstance(item, QualityGateRiskItem):
                normalized.append(item)
                continue
            if not isinstance(item, Mapping):
                continue
            normalized.append(
                QualityGateRiskItem(
                    risk_key=str(item.get("risk_key", "") or f"performance_risk_{index + 1}"),
                    category=str(item.get("category", "") or "performance"),
                    severity=str(item.get("severity", "") or "medium"),
                    summary=str(item.get("summary", "") or ""),
                    details=dict(item.get("details", {}) or {}),
                    source=str(item.get("source", "") or "performance_risk_provider"),
                    blocks_admission=bool(item.get("blocks_admission", False)),
                )
            )
        return normalized

    @staticmethod
    def _issue_type_change_summary(families: Sequence[Any]) -> dict[str, dict[str, int]]:
        summary: dict[str, Counter[str]] = defaultdict(Counter)
        for family in families:
            issue_type = str(getattr(family, "issue_type", "") or "")
            change_type = str(getattr(family, "change_type", "") or "")
            if issue_type and change_type:
                summary[issue_type][change_type] += 1
        return {issue_type: dict(counter) for issue_type, counter in summary.items()}

    @classmethod
    def _evaluate_change_limits(
        cls,
        *,
        change_summary: Mapping[str, int],
        issue_type_change_summary: Mapping[str, Mapping[str, int]],
        policy: Mapping[str, Any],
    ) -> list[RuleReviewFinding]:
        findings: list[RuleReviewFinding] = []
        for change_type, observed_count in change_summary.items():
            findings.extend(
                cls._limit_findings(
                    scope="global",
                    issue_type="",
                    change_type=change_type,
                    observed_count=int(observed_count or 0),
                    limit_payload=cls._mapping_value(policy.get("global_change_limits"), change_type),
                )
            )

        for issue_type, change_map in issue_type_change_summary.items():
            issue_policy = cls._mapping_value(policy.get("issue_type_limits"), issue_type)
            for change_type, observed_count in change_map.items():
                findings.extend(
                    cls._limit_findings(
                        scope="issue_type",
                        issue_type=issue_type,
                        change_type=change_type,
                        observed_count=int(observed_count or 0),
                        limit_payload=cls._mapping_value(issue_policy, change_type),
                    )
                )
        return findings

    @staticmethod
    def _mapping_value(payload: Any, key: str) -> Mapping[str, Any]:
        if isinstance(payload, Mapping):
            value = payload.get(key, {})
            return value if isinstance(value, Mapping) else {}
        return {}

    @classmethod
    def _limit_findings(
        cls,
        *,
        scope: str,
        issue_type: str,
        change_type: str,
        observed_count: int,
        limit_payload: Mapping[str, Any],
    ) -> list[RuleReviewFinding]:
        findings: list[RuleReviewFinding] = []
        if observed_count <= 0 or not limit_payload:
            return findings

        fail_threshold = cls._optional_int(limit_payload.get("fail"))
        warning_threshold = cls._optional_int(limit_payload.get("warning"))
        if fail_threshold is not None and observed_count >= fail_threshold:
            findings.append(
                RuleReviewFinding(
                    level="fail",
                    scope=scope,
                    issue_type=issue_type,
                    change_type=change_type,
                    observed_count=observed_count,
                    threshold=fail_threshold,
                    message=cls._message(scope, issue_type, change_type, observed_count, fail_threshold, "fail"),
                )
            )
            return findings
        if warning_threshold is not None and observed_count >= warning_threshold:
            findings.append(
                RuleReviewFinding(
                    level="warning",
                    scope=scope,
                    issue_type=issue_type,
                    change_type=change_type,
                    observed_count=observed_count,
                    threshold=warning_threshold,
                    message=cls._message(scope, issue_type, change_type, observed_count, warning_threshold, "warning"),
                )
            )
        return findings

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _message(
        scope: str,
        issue_type: str,
        change_type: str,
        observed_count: int,
        threshold: int,
        level: str,
    ) -> str:
        if scope == "issue_type" and issue_type:
            return (
                f"{issue_type} change_type={change_type} observed {observed_count}, "
                f"reaching {level} threshold {threshold}."
            )
        return (
            f"Global change_type={change_type} observed {observed_count}, "
            f"reaching {level} threshold {threshold}."
        )
