from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from stability.domain import (
    QualityGateCoverageGap,
    QualityGateOverrideRecord,
    QualityGateResult,
    QualityGateRiskItem,
    QualityGateRule,
    QualityGateTriggeredRule,
)
from stability.domain.value_objects import new_id, utcnow

from .integration_outbox_service import IntegrationOutboxService


class QualityGateService:
    """Build a first-class V3 admission result on top of report/baseline/audit inputs."""

    _rule_version = "quality-gate-v1"
    _decision_priority = {
        "pass": 0,
        "conditional_pass": 1,
        "fail": 2,
    }

    def __init__(
        self,
        *,
        rule_review_report_service: object,
        root_dir: str | Path = "runtime/quality_gates",
        performance_risk_provider: Callable[..., Sequence[QualityGateRiskItem | Mapping[str, Any]]] | None = None,
        outbox_service: IntegrationOutboxService | None = None,
    ) -> None:
        self._rule_review_report_service = rule_review_report_service
        self._root_dir = Path(root_dir)
        self._override_registry_path = self._root_dir / "overrides.json"
        self._performance_risk_provider = performance_risk_provider
        self._outbox_service = outbox_service

    def list_quality_gates(self, *, limit: int = 20) -> tuple[QualityGateResult, ...]:
        baselines = list(self._rule_review_report_service.list_baselines())
        if limit > 0:
            baselines = baselines[:limit]
        return tuple(self.get_quality_gate(item.baseline_key) for item in baselines)

    def get_quality_gate(self, baseline_key: str) -> QualityGateResult:
        key = baseline_key.strip()
        if not key:
            raise ValueError("Baseline key is required.")

        baseline = self._rule_review_report_service.get_baseline(key)
        report = self._rule_review_report_service.get_report(getattr(baseline, "report_id", ""))
        latest_audit = self._latest_baseline_audit_or_none(key)

        report_summary = dict(getattr(report, "summary", {}) or {})
        latest_audit_summary = dict(getattr(latest_audit, "summary", {}) or {})
        golden_suite = self._resolve_golden_suite(
            report_summary=report_summary,
            latest_audit_summary=latest_audit_summary,
        )
        rules = self._default_rules()
        triggered_rules: list[QualityGateTriggeredRule] = []
        risk_items: list[QualityGateRiskItem] = []
        coverage_gaps: list[QualityGateCoverageGap] = []

        decision_counts = {
            str(key): int(value or 0)
            for key, value in dict(report_summary.get("decision_counts", {}) or {}).items()
        }
        snapshot_count = int(report_summary.get("snapshot_count", 0) or 0)
        fail_count = int(decision_counts.get("fail", 0) or 0)
        conditional_count = int(decision_counts.get("conditional_pass", 0) or 0)
        high_risk_family_count = int(report_summary.get("high_risk_family_count", 0) or 0)
        golden_case_count = int(golden_suite.get("case_count_total", 0) or 0)
        golden_failed_case_count = int(golden_suite.get("failed_case_count_total", 0) or 0)

        if fail_count > 0:
            triggered_rules.append(
                self._triggered_rule(
                    rule_key="review_failures",
                    observed_value=fail_count,
                    threshold=0,
                    decision_on_trigger="fail",
                    message=f"当前报告包含 {fail_count} 个 fail 决策快照。",
                    source="report.summary.decision_counts.fail",
                )
            )
        if golden_failed_case_count > 0:
            triggered_rules.append(
                self._triggered_rule(
                    rule_key="golden_suite_failures",
                    observed_value=golden_failed_case_count,
                    threshold=0,
                    decision_on_trigger="fail",
                    message=(
                        f"Golden Suite 失败 {golden_failed_case_count} 个 case，"
                        f"当前总 case 数 {golden_case_count}。"
                    ),
                    source="report.current_report_golden_suite.failed_case_count_total",
                )
            )
        if fail_count == 0 and conditional_count > 0:
            triggered_rules.append(
                self._triggered_rule(
                    rule_key="review_warnings",
                    observed_value=conditional_count,
                    threshold=0,
                    decision_on_trigger="conditional_pass",
                    message=f"当前报告包含 {conditional_count} 个 conditional_pass 决策快照。",
                    source="report.summary.decision_counts.conditional_pass",
                )
            )
        if high_risk_family_count > 0:
            triggered_rules.append(
                self._triggered_rule(
                    rule_key="high_risk_families",
                    observed_value=high_risk_family_count,
                    threshold=0,
                    decision_on_trigger="conditional_pass",
                    message=f"当前报告仍有 {high_risk_family_count} 个高风险 family。",
                    source="report.summary.high_risk_family_count",
                )
            )
            risk_items.append(
                QualityGateRiskItem(
                    risk_key="stability_high_risk_families",
                    category="stability",
                    severity="high" if high_risk_family_count >= 3 else "medium",
                    summary=f"高风险 family 数为 {high_risk_family_count}，建议继续人工评审。",
                    details={"high_risk_family_count": high_risk_family_count},
                    source="report.summary.high_risk_family_count",
                    blocks_admission=False,
                )
            )
        if snapshot_count < 1:
            coverage_gaps.append(
                QualityGateCoverageGap(
                    gap_key="review_snapshot_coverage",
                    category="review_snapshot",
                    severity="high",
                    summary="当前准入报告没有可用的 review snapshot，覆盖不足。",
                    observed_value=snapshot_count,
                    required_value=1,
                    source="report.summary.snapshot_count",
                )
            )
            triggered_rules.append(
                self._triggered_rule(
                    rule_key="review_snapshot_coverage",
                    observed_value=snapshot_count,
                    threshold=1,
                    decision_on_trigger="conditional_pass",
                    message="当前准入报告没有可用的 review snapshot，自动结论降级为 conditional_pass。",
                    source="report.summary.snapshot_count",
                )
            )
        if golden_case_count < 1:
            coverage_gaps.append(
                QualityGateCoverageGap(
                    gap_key="golden_suite_coverage",
                    category="golden_suite",
                    severity="medium",
                    summary="当前准入结果没有 golden suite case 覆盖，建议补齐验收样本。",
                    observed_value=golden_case_count,
                    required_value=1,
                    source="report.current_report_golden_suite.case_count_total",
                )
            )
            triggered_rules.append(
                self._triggered_rule(
                    rule_key="golden_suite_coverage",
                    observed_value=golden_case_count,
                    threshold=1,
                    decision_on_trigger="conditional_pass",
                    message="当前准入结果缺少 golden suite case 覆盖。",
                    source="report.current_report_golden_suite.case_count_total",
                )
            )

        performance_risk_items = self._performance_risk_items(
            baseline_key=key,
            report=report,
            latest_audit=latest_audit,
            report_summary=report_summary,
        )
        if performance_risk_items:
            triggered_rules.append(
                self._triggered_rule(
                    rule_key="performance_risks",
                    observed_value=len(performance_risk_items),
                    threshold=0,
                    decision_on_trigger="risk_only",
                    message=f"检测到 {len(performance_risk_items)} 个性能风险提示项，仅作为辅助风险，不直接替代稳定性结论。",
                    source="performance_risk_provider",
                )
            )

        automatic_decision = self._automatic_decision(triggered_rules)
        override = self._load_override(key)
        final_decision = override.final_decision if override is not None else automatic_decision
        failure_reasons = tuple(
            item.message
            for item in triggered_rules
            if item.decision_on_trigger in {"fail", "conditional_pass"}
        )
        source_links = {
            "report_detail_path": str(getattr(report, "detail_path", "") or ""),
            "report_markdown_path": str(getattr(report, "markdown_path", "") or ""),
            "report_html_path": str(getattr(report, "html_path", "") or ""),
            "latest_audit_detail_path": str(getattr(latest_audit, "detail_path", "") or ""),
            "latest_audit_markdown_path": str(getattr(latest_audit, "markdown_path", "") or ""),
            "latest_audit_html_path": str(getattr(latest_audit, "html_path", "") or ""),
            "latest_audit_index_path": str(getattr(latest_audit, "index_path", "") or ""),
        }
        return QualityGateResult(
            baseline_key=key,
            report_id=str(getattr(report, "report_id", "") or ""),
            report_name=str(getattr(report, "name", "") or ""),
            evaluated_at=utcnow(),
            automatic_decision=automatic_decision,
            final_decision=final_decision,
            final_review_opinion=self._final_review_opinion(
                automatic_decision=automatic_decision,
                final_decision=final_decision,
                override=override,
                risk_items=risk_items,
                performance_risk_items=performance_risk_items,
                coverage_gaps=coverage_gaps,
            ),
            rules=rules,
            triggered_rules=tuple(triggered_rules),
            failure_reasons=failure_reasons,
            risk_items=tuple(risk_items),
            performance_risk_items=tuple(performance_risk_items),
            coverage_gaps=tuple(coverage_gaps),
            override=override,
            policy_versions=tuple(getattr(baseline, "policy_versions", ()) or ()),
            candidate_paths=tuple(getattr(baseline, "candidate_paths", ()) or ()),
            baseline_paths=tuple(getattr(baseline, "baseline_paths", ()) or ()),
            report_created_at=str(getattr(baseline, "report_created_at", "") or ""),
            updated_at=getattr(baseline, "updated_at", None),
            updated_by=str(getattr(baseline, "updated_by", "") or ""),
            latest_audit_summary=latest_audit_summary,
            current_report_golden_suite=golden_suite,
            report_summary=report_summary,
            source_links=source_links,
        )

    def _latest_baseline_audit_or_none(self, baseline_key: str):
        try:
            return self._rule_review_report_service.show_latest_baseline_audit(
                baseline_key=baseline_key,
                version_limit=10,
            )
        except ValueError:
            return None

    def record_override(
        self,
        *,
        baseline_key: str,
        final_decision: str,
        reason: str,
        created_by: str,
        session_source: str = "",
        audit_source: Mapping[str, Any] | None = None,
        comment: str = "",
        evidence_paths: Sequence[str] = (),
    ) -> QualityGateOverrideRecord:
        key = baseline_key.strip()
        decision = final_decision.strip()
        why = reason.strip()
        actor = created_by.strip() or "cli"
        if not key:
            raise ValueError("Baseline key is required.")
        if decision not in {"pass", "conditional_pass", "fail"}:
            raise ValueError("final_decision must be one of pass/conditional_pass/fail.")
        if not why:
            raise ValueError("Override reason is required.")

        current = self.get_quality_gate(key)
        override = QualityGateOverrideRecord(
            override_id=new_id("gate_override"),
            baseline_key=key,
            automatic_decision=current.automatic_decision,
            final_decision=decision,
            reason=why,
            created_at=utcnow(),
            created_by=actor,
            session_source=session_source.strip(),
            audit_source=dict(audit_source or {}),
            comment=comment.strip(),
            evidence_paths=tuple(str(item).strip() for item in evidence_paths if str(item).strip()),
        )
        registry = self._load_override_registry()
        registry[key] = self._override_payload(override)
        self._save_override_registry(registry)
        if self._outbox_service is not None:
            self._outbox_service.publish_event(
                event_type="admission.override_recorded",
                target_type="admission",
                target_id=key,
                created_by=actor,
                session_source=session_source.strip(),
                audit_source=dict(audit_source or {}),
                payload={
                    "automatic_decision": current.automatic_decision,
                    "final_decision": decision,
                    "reason": why,
                    "comment": comment.strip(),
                    "evidence_paths": list(override.evidence_paths),
                },
            )
        return override

    def _default_rules(self) -> tuple[QualityGateRule, ...]:
        return (
            QualityGateRule(
                rule_key="review_failures",
                name="规则评审失败门槛",
                rule_version=self._rule_version,
                scope="global",
                metric_key="decision_counts.fail",
                comparator=">",
                threshold=0,
                decision_on_trigger="fail",
                description="当前报告只要存在 fail 决策快照，就直接阻断自动准入。",
                created_by="system",
                updated_by="system",
            ),
            QualityGateRule(
                rule_key="golden_suite_failures",
                name="Golden Suite 失败门槛",
                rule_version=self._rule_version,
                scope="global",
                metric_key="current_report_golden_suite.failed_case_count_total",
                comparator=">",
                threshold=0,
                decision_on_trigger="fail",
                description="黄金样本失败代表规则变更未通过关键 acceptance。",
                created_by="system",
                updated_by="system",
            ),
            QualityGateRule(
                rule_key="review_warnings",
                name="规则评审警告门槛",
                rule_version=self._rule_version,
                scope="global",
                metric_key="decision_counts.conditional_pass",
                comparator=">",
                threshold=0,
                decision_on_trigger="conditional_pass",
                description="出现 warning 时自动结论降级为 conditional_pass。",
                created_by="system",
                updated_by="system",
            ),
            QualityGateRule(
                rule_key="high_risk_families",
                name="高风险 Family 门槛",
                rule_version=self._rule_version,
                scope="global",
                metric_key="high_risk_family_count",
                comparator=">",
                threshold=0,
                decision_on_trigger="conditional_pass",
                description="高风险 family 不一定直接阻断，但必须显式暴露给评审者。",
                created_by="system",
                updated_by="system",
            ),
            QualityGateRule(
                rule_key="review_snapshot_coverage",
                name="准入评审覆盖门槛",
                rule_version=self._rule_version,
                scope="global",
                metric_key="snapshot_count",
                comparator="<",
                threshold=1,
                decision_on_trigger="conditional_pass",
                description="缺少 review snapshot 时不应给出无条件通过。",
                created_by="system",
                updated_by="system",
            ),
            QualityGateRule(
                rule_key="golden_suite_coverage",
                name="Golden Suite 覆盖门槛",
                rule_version=self._rule_version,
                scope="global",
                metric_key="current_report_golden_suite.case_count_total",
                comparator="<",
                threshold=1,
                decision_on_trigger="conditional_pass",
                description="缺少 golden suite 覆盖时需要显式提示覆盖不足。",
                created_by="system",
                updated_by="system",
            ),
            QualityGateRule(
                rule_key="performance_risks",
                name="性能风险辅助项",
                rule_version=self._rule_version,
                scope="global",
                metric_key="performance_risk_items",
                comparator=">",
                threshold=0,
                decision_on_trigger="risk_only",
                description="性能结果只作为风险辅助项，不直接替代稳定性结论。",
                created_by="system",
                updated_by="system",
            ),
        )

    def _triggered_rule(
        self,
        *,
        rule_key: str,
        observed_value: Any,
        threshold: Any,
        decision_on_trigger: str,
        message: str,
        source: str,
    ) -> QualityGateTriggeredRule:
        rule = {item.rule_key: item for item in self._default_rules()}[rule_key]
        return QualityGateTriggeredRule(
            rule_key=rule.rule_key,
            rule_name=rule.name,
            rule_version=rule.rule_version,
            decision_on_trigger=decision_on_trigger,
            observed_value=observed_value,
            threshold=threshold,
            message=message,
            source=source,
        )

    def _automatic_decision(self, triggered_rules: Sequence[QualityGateTriggeredRule]) -> str:
        decision = "pass"
        for item in triggered_rules:
            candidate = str(item.decision_on_trigger or "").strip()
            if candidate == "risk_only":
                continue
            if self._decision_priority.get(candidate, 0) > self._decision_priority.get(decision, 0):
                decision = candidate
        return decision

    def _final_review_opinion(
        self,
        *,
        automatic_decision: str,
        final_decision: str,
        override: QualityGateOverrideRecord | None,
        risk_items: Sequence[QualityGateRiskItem],
        performance_risk_items: Sequence[QualityGateRiskItem],
        coverage_gaps: Sequence[QualityGateCoverageGap],
    ) -> str:
        if override is not None:
            return (
                f"人工覆盖已将自动结论 {automatic_decision} 调整为 {final_decision}，"
                f"覆盖人：{override.created_by}，原因：{override.reason}"
            )
        if final_decision == "fail":
            return "自动准入失败，需先处理阻断规则后再继续评审。"
        if final_decision == "conditional_pass":
            return (
                f"自动准入为 conditional_pass，当前仍有 {len(risk_items) + len(performance_risk_items)} 个风险项"
                f"和 {len(coverage_gaps)} 个覆盖不足项需要人工确认。"
            )
        return "自动准入通过，当前没有发现阻断项；如需发布，仍建议结合报告和风险项做最终确认。"

    def _performance_risk_items(
        self,
        *,
        baseline_key: str,
        report: object,
        latest_audit: object,
        report_summary: Mapping[str, Any],
    ) -> tuple[QualityGateRiskItem, ...]:
        items: list[QualityGateRiskItem] = []
        provider = self._performance_risk_provider
        if provider is not None:
            raw_items = provider(
                baseline_key=baseline_key,
                report=report,
                latest_audit=latest_audit,
            )
            items.extend(self._normalize_risk_items(raw_items, default_category="performance"))

        metric_summary = dict(report_summary.get("metric_result_summary", {}) or {})
        worsened_count = int(metric_summary.get("worsened_count", 0) or 0)
        embedded_items = report_summary.get("performance_risk_items", ()) or report_summary.get("performance_risks", ())
        normalized_embedded_items = self._normalize_risk_items(embedded_items, default_category="performance")
        if worsened_count > 0 and not normalized_embedded_items:
            items.append(
                QualityGateRiskItem(
                    risk_key="performance_metric_regression",
                    category="performance",
                    severity="medium" if worsened_count < 3 else "high",
                    summary=f"关键性能指标存在 {worsened_count} 项恶化趋势。",
                    details=metric_summary,
                    source="report.summary.metric_result_summary",
                    blocks_admission=False,
                )
            )
        items.extend(normalized_embedded_items)
        return tuple(items)

    @staticmethod
    def _normalize_risk_items(
        items: Sequence[QualityGateRiskItem | Mapping[str, Any]] | Mapping[str, Any] | None,
        *,
        default_category: str,
    ) -> list[QualityGateRiskItem]:
        if items is None:
            return []
        raw_items: Sequence[Any]
        if isinstance(items, Mapping):
            candidate_items = items.get("items", ())
            if isinstance(candidate_items, Sequence) and not isinstance(candidate_items, (str, bytes)):
                raw_items = candidate_items
            else:
                raw_items = [items]
        else:
            raw_items = list(items)

        normalized: list[QualityGateRiskItem] = []
        for item in raw_items:
            if isinstance(item, QualityGateRiskItem):
                normalized.append(item)
                continue
            if not isinstance(item, Mapping):
                continue
            normalized.append(
                QualityGateRiskItem(
                    risk_key=str(item.get("risk_key", "") or item.get("key", "") or new_id("gate_risk")),
                    category=str(item.get("category", "") or default_category),
                    severity=str(item.get("severity", "") or "medium"),
                    summary=str(item.get("summary", "") or item.get("message", "") or "性能风险提示"),
                    details=dict(item.get("details", {}) or {}),
                    source=str(item.get("source", "") or ""),
                    blocks_admission=bool(item.get("blocks_admission", False)),
                )
            )
        return normalized

    @staticmethod
    def _resolve_golden_suite(
        *,
        report_summary: Mapping[str, Any],
        latest_audit_summary: Mapping[str, Any],
    ) -> dict[str, Any]:
        golden_suite = dict(latest_audit_summary.get("current_report_golden_suite", {}) or {})
        if golden_suite:
            return golden_suite
        return {
            "snapshot_count": int(report_summary.get("golden_suite_snapshot_count", 0) or 0),
            "passed_snapshot_count": int(report_summary.get("golden_suite_passed_snapshot_count", 0) or 0),
            "failed_snapshot_count": int(report_summary.get("golden_suite_failed_snapshot_count", 0) or 0),
            "case_count_total": int(report_summary.get("golden_suite_case_count_total", 0) or 0),
            "passed_case_count_total": int(report_summary.get("golden_suite_passed_case_count_total", 0) or 0),
            "failed_case_count_total": int(report_summary.get("golden_suite_failed_case_count_total", 0) or 0),
            "versions": list(report_summary.get("golden_suite_versions", ()) or ()),
            "suite_paths": list(report_summary.get("golden_suite_suite_paths", ()) or ()),
            "layer_summaries": {
                str(key): dict(value)
                for key, value in dict(report_summary.get("golden_suite_layer_summaries", {}) or {}).items()
            },
        }

    def _load_override(self, baseline_key: str) -> QualityGateOverrideRecord | None:
        registry = self._load_override_registry()
        payload = registry.get(baseline_key.strip())
        if not isinstance(payload, Mapping):
            return None
        created_at_raw = str(payload.get("created_at", "") or "")
        return QualityGateOverrideRecord(
            override_id=str(payload.get("override_id", "") or ""),
            baseline_key=str(payload.get("baseline_key", "") or baseline_key.strip()),
            automatic_decision=str(payload.get("automatic_decision", "") or "pass"),
            final_decision=str(payload.get("final_decision", "") or "pass"),
            reason=str(payload.get("reason", "") or ""),
            created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else utcnow(),
            created_by=str(payload.get("created_by", "") or ""),
            session_source=str(payload.get("session_source", "") or ""),
            audit_source=dict(payload.get("audit_source", {}) or {}),
            comment=str(payload.get("comment", "") or ""),
            evidence_paths=tuple(str(item) for item in (payload.get("evidence_paths", ()) or ()) if str(item).strip()),
        )

    def _load_override_registry(self) -> dict[str, Any]:
        if not self._override_registry_path.exists():
            return {}
        try:
            payload = json.loads(self._override_registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(payload, Mapping):
            return {}
        return {str(key): value for key, value in payload.items()}

    def _save_override_registry(self, payload: Mapping[str, Any]) -> None:
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._override_registry_path.write_text(
            json.dumps(dict(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _override_payload(item: QualityGateOverrideRecord) -> dict[str, Any]:
        return {
            "override_id": item.override_id,
            "baseline_key": item.baseline_key,
            "automatic_decision": item.automatic_decision,
            "final_decision": item.final_decision,
            "reason": item.reason,
            "created_at": item.created_at.isoformat(),
            "created_by": item.created_by,
            "session_source": item.session_source,
            "audit_source": dict(item.audit_source),
            "comment": item.comment,
            "evidence_paths": list(item.evidence_paths),
        }
