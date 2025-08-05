from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from stability.app import admission_case_aggregation as aggregation
from stability.app import admission_case_contracts as contracts
from stability.app import admission_case_lifecycle as lifecycle
from stability.app.admission_case_contract_payload import (
    admission_case_contract_payload,
    admission_case_list_contract_payload,
)
from stability.app.admission_case_store import (
    AdmissionCaseStore,
    datetime_or_none,
    json_ready,
    payload_revision_fingerprint,
)
from stability.app.admission_report_builder import build_admission_report_payload
from stability.domain import (
    AdmissionCase,
    AdmissionReportPayload,
    QualityGateResult,
)
from stability.domain.value_objects import utcnow


class AdmissionCaseService:
    """Build first-class admission cases by aggregating report, execution, and gate inputs."""

    def __init__(
        self,
        *,
        rule_review_report_service: object,
        root_dir: str | Path = "runtime/admission_cases",
        quality_gate_service: object | None = None,
        run_history_service: object | None = None,
        analysis_service: object | None = None,
        regression_service: object | None = None,
        outbox_service: object | None = None,
    ) -> None:
        self._rule_review_report_service = rule_review_report_service
        self._store = AdmissionCaseStore(Path(root_dir))
        self._quality_gate_service = quality_gate_service
        self._run_history_service = run_history_service
        self._analysis_service = analysis_service
        self._regression_service = regression_service
        self._outbox_service = outbox_service

    def list_cases(self, *, limit: int = 20) -> tuple[AdmissionCase, ...]:
        baselines = list(self._rule_review_report_service.list_baselines())
        if limit > 0:
            baselines = baselines[:limit]
        return tuple(self.get_case(item.baseline_key) for item in baselines)

    def list_admission_case_payloads(self, *, limit: int = 20) -> dict[str, Any]:
        """Return the stable AdmissionCase list contract as JSON-ready data."""

        return admission_case_list_contract_payload(self.list_cases(limit=limit))

    def get_case(self, baseline_key: str) -> AdmissionCase:
        key = baseline_key.strip()
        if not key:
            raise ValueError("Baseline key is required.")

        baseline = self._rule_review_report_service.get_baseline(key)
        report = self._rule_review_report_service.get_report(getattr(baseline, "report_id", ""))
        latest_audit = self._latest_baseline_audit_or_none(key)
        baseline_updated_at = datetime_or_none(getattr(baseline, "updated_at", None))
        filters = self._normalized_filters(dict(getattr(report, "filters", {}) or {}))
        execution_summary = self._execution_summary(filters)
        top_issues = self._top_issues(filters)
        regression_summary = self._regression_summary(filters)
        scenario_coverage = self._scenario_coverage(
            filters=filters,
            execution_summary=execution_summary,
            top_issues=top_issues,
        )
        quality_gate = self._quality_gate(key)
        final_decision = str(getattr(quality_gate, "final_decision", "") or "unknown")
        error_code = self._error_code(final_decision=final_decision, quality_gate=quality_gate)
        performance_risk_items = tuple(getattr(quality_gate, "performance_risk_items", ()) or ()) if quality_gate else ()
        case_trace = self._case_trace_payload(
            baseline_key=key,
            report=report,
            quality_gate=quality_gate,
            execution_summary=execution_summary,
            top_issues=top_issues,
            regression_summary=regression_summary,
            scenario_coverage=scenario_coverage,
            latest_audit=latest_audit,
            final_decision=final_decision,
            error_code=error_code,
            final_review_opinion=str(getattr(quality_gate, "final_review_opinion", "") or ""),
            report_id=str(getattr(report, "report_id", "") or ""),
            report_name=str(getattr(report, "name", "") or ""),
            baseline_updated_at=baseline_updated_at,
        )

        report_created_at = datetime_or_none(getattr(report, "created_at", None))
        source_links = dict(getattr(quality_gate, "source_links", {}) or {})
        if not source_links:
            source_links = {
                "report_detail_path": str(getattr(report, "detail_path", "") or ""),
                "report_markdown_path": str(getattr(report, "markdown_path", "") or ""),
                "report_html_path": str(getattr(report, "html_path", "") or ""),
                "latest_audit_detail_path": str(getattr(latest_audit, "detail_path", "") or ""),
                "latest_audit_markdown_path": str(getattr(latest_audit, "markdown_path", "") or ""),
                "latest_audit_html_path": str(getattr(latest_audit, "html_path", "") or ""),
                "latest_audit_index_path": str(getattr(latest_audit, "index_path", "") or ""),
            }

        source_refs = self._source_refs(
            report=report,
            latest_audit=latest_audit,
            quality_gate=quality_gate,
            source_links=source_links,
            filters=filters,
        )
        previous = self._load_case_for_baseline(key)
        ci_contract = self._ci_contract(
            case_id=f"admission_case:{key}:{getattr(report, 'report_id', '') or 'unknown'}",
            baseline_key=key,
            report_id=str(getattr(report, "report_id", "") or ""),
            final_decision=final_decision,
            error_code=error_code,
            final_review_opinion=str(getattr(quality_gate, "final_review_opinion", "") or ""),
            status=self._normalize_status(str(getattr(previous, "status", "") or "open")),
            revision=max(int(getattr(previous, "revision", 0) or 0), 1),
            assignee_id=str(getattr(previous, "assignee_id", "") or ""),
            assignee_display_name=str(getattr(previous, "assignee_display_name", "") or ""),
            final_reviewer_id=str(getattr(previous, "final_reviewer_id", "") or ""),
            final_reviewer_display_name=str(getattr(previous, "final_reviewer_display_name", "") or ""),
            source_refs=source_refs,
            case_trace=case_trace,
        )
        candidate = AdmissionCase(
            case_id=f"admission_case:{key}:{getattr(report, 'report_id', '') or 'unknown'}",
            baseline_key=key,
            report_id=str(getattr(report, "report_id", "") or ""),
            report_name=str(getattr(report, "name", "") or ""),
            status=self._normalize_status(str(getattr(previous, "status", "") or "open")),
            revision=max(int(getattr(previous, "revision", 0) or 0), 1),
            assignee_id=str(getattr(previous, "assignee_id", "") or ""),
            assignee_display_name=str(getattr(previous, "assignee_display_name", "") or ""),
            final_reviewer_id=str(getattr(previous, "final_reviewer_id", "") or ""),
            final_reviewer_display_name=str(getattr(previous, "final_reviewer_display_name", "") or ""),
            created_at=report_created_at,
            updated_at=baseline_updated_at,
            updated_by=str(getattr(baseline, "updated_by", "") or ""),
            filters=filters,
            execution_summary=execution_summary,
            top_issues=top_issues,
            regression_summary=regression_summary,
            scenario_coverage=scenario_coverage,
            performance_risk_items=performance_risk_items,
            quality_gate=quality_gate,
            override=getattr(quality_gate, "override", None) if quality_gate else None,
            final_review_opinion=str(getattr(quality_gate, "final_review_opinion", "") or ""),
            final_decision=final_decision,
            error_code=error_code,
            lifecycle_events=tuple(getattr(previous, "lifecycle_events", ()) or ()),
            role_audit_entries=tuple(getattr(previous, "role_audit_entries", ()) or ()),
            case_trace=case_trace,
            report_summary=dict(getattr(report, "summary", {}) or {}),
            latest_audit_summary=dict(getattr(latest_audit, "summary", {}) or {}),
            source_links=source_links,
            source_refs=source_refs,
            ci_contract=ci_contract,
        )
        return self._persist_case(candidate, previous=previous)

    def build_admission_report(
        self,
        baseline_key: str | None = None,
        *,
        case: AdmissionCase | None = None,
        generated_at: datetime | None = None,
    ) -> AdmissionReportPayload:
        """Build an export-ready, auditable report contract for one admission case."""

        item = case
        if item is None:
            key = str(baseline_key or "").strip()
            if not key:
                raise ValueError("Baseline key or AdmissionCase is required.")
            item = self.get_case(key)

        return build_admission_report_payload(item, generated_at=generated_at)

    def export_admission_report_payload(
        self,
        baseline_key: str | None = None,
        *,
        case: AdmissionCase | None = None,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Return the admission report contract as stable JSON-ready data."""

        report = self.build_admission_report(baseline_key, case=case, generated_at=generated_at)
        return json_ready(asdict(report))

    def export_admission_case_payload(
        self,
        baseline_key: str | None = None,
        *,
        case: AdmissionCase | None = None,
    ) -> dict[str, Any]:
        """Return the stable AdmissionCase contract as JSON-ready data."""

        item = case
        if item is None:
            key = str(baseline_key or "").strip()
            if not key:
                raise ValueError("Baseline key or AdmissionCase is required.")
            item = self.get_case(key)
        return admission_case_contract_payload(item)

    def update_case_collaboration(
        self,
        baseline_key: str,
        *,
        status: str | None = None,
        assignee_id: str | None = None,
        assignee_display_name: str | None = None,
        final_reviewer_id: str | None = None,
        final_reviewer_display_name: str | None = None,
        action: str = "sync",
        changed_by: str = "",
        changed_by_display_name: str = "",
        reason: str = "",
        audit_source: Mapping[str, Any] | None = None,
    ) -> AdmissionCase:
        key = baseline_key.strip()
        if not key:
            raise ValueError("Baseline key is required.")
        previous = self._load_case_for_baseline(key)
        current = previous or self.get_case(key)
        current_status = self._normalize_status(str(getattr(current, "status", "") or "open"))
        next_status = self._normalize_status(
            str(status if status is not None else getattr(current, "status", "open") or "open")
        )
        self._validate_status_transition(from_status=current_status, to_status=next_status, action=action)
        next_assignee_id = str(assignee_id if assignee_id is not None else getattr(current, "assignee_id", "") or "")
        next_assignee_display_name = str(
            assignee_display_name
            if assignee_display_name is not None
            else getattr(current, "assignee_display_name", "") or ""
        )
        next_final_reviewer_id = str(
            final_reviewer_id if final_reviewer_id is not None else getattr(current, "final_reviewer_id", "") or ""
        )
        next_final_reviewer_display_name = str(
            final_reviewer_display_name
            if final_reviewer_display_name is not None
            else getattr(current, "final_reviewer_display_name", "") or ""
        )
        actor_id = str(changed_by or getattr(current, "updated_by", "") or "system")
        actor_name = str(changed_by_display_name or actor_id)
        audit_payload = dict(audit_source or {})
        changed_at = datetime_or_none(audit_payload.get("changed_at")) or utcnow()
        lifecycle_events = list(getattr(current, "lifecycle_events", ()) or ())
        role_audit_entries = list(getattr(current, "role_audit_entries", ()) or ())
        if not lifecycle_events:
            lifecycle_events.append(
                self._lifecycle_event(
                    action="case_initialized",
                    from_status="",
                    to_status=current_status,
                    changed_at=datetime_or_none(getattr(current, "created_at", None)) or changed_at,
                    changed_by=str(getattr(current, "updated_by", "") or "system"),
                    reason="AdmissionCase initialized from baseline/report inputs.",
                    audit_source={},
                )
            )
        if current_status != next_status:
            lifecycle_events.append(
                self._lifecycle_event(
                    action=action,
                    from_status=current_status,
                    to_status=next_status,
                    changed_at=changed_at,
                    changed_by=actor_id,
                    reason=reason,
                    audit_source=audit_payload,
                )
            )
        if str(getattr(current, "assignee_id", "") or "") != next_assignee_id or str(
            getattr(current, "assignee_display_name", "") or ""
        ) != next_assignee_display_name:
            role_audit_entries.append(
                self._role_audit_entry(
                    role_name="assignee",
                    changed_at=changed_at,
                    changed_by=actor_id,
                    from_actor_id=str(getattr(current, "assignee_id", "") or ""),
                    from_actor_display_name=str(getattr(current, "assignee_display_name", "") or ""),
                    to_actor_id=next_assignee_id,
                    to_actor_display_name=next_assignee_display_name,
                    reason=reason or f"assignee changed via {action} by {actor_name}",
                    audit_source=audit_payload,
                )
            )
        if str(getattr(current, "final_reviewer_id", "") or "") != next_final_reviewer_id or str(
            getattr(current, "final_reviewer_display_name", "") or ""
        ) != next_final_reviewer_display_name:
            role_audit_entries.append(
                self._role_audit_entry(
                    role_name="final_reviewer",
                    changed_at=changed_at,
                    changed_by=actor_id,
                    from_actor_id=str(getattr(current, "final_reviewer_id", "") or ""),
                    from_actor_display_name=str(getattr(current, "final_reviewer_display_name", "") or ""),
                    to_actor_id=next_final_reviewer_id,
                    to_actor_display_name=next_final_reviewer_display_name,
                    reason=reason or f"reviewer changed via {action} by {actor_name}",
                    audit_source=audit_payload,
                )
            )
        candidate = replace(
            current,
            status=next_status,
            assignee_id=next_assignee_id,
            assignee_display_name=next_assignee_display_name,
            final_reviewer_id=next_final_reviewer_id,
            final_reviewer_display_name=next_final_reviewer_display_name,
            updated_by=actor_id,
            lifecycle_events=tuple(lifecycle_events),
            role_audit_entries=tuple(role_audit_entries),
        )
        return self._persist_case(candidate, previous=current)

    def _latest_baseline_audit_or_none(self, baseline_key: str):
        try:
            return self._rule_review_report_service.show_latest_baseline_audit(
                baseline_key=baseline_key,
                version_limit=10,
            )
        except ValueError:
            return None

    def _quality_gate(self, baseline_key: str) -> QualityGateResult | None:
        service = self._quality_gate_service
        if service is None or not hasattr(service, "get_quality_gate"):
            return None
        return service.get_quality_gate(baseline_key)

    def _persist_case(self, candidate: AdmissionCase, *, previous: AdmissionCase | None) -> AdmissionCase:
        payload = self._store.case_payload(candidate)
        revision = max(int(getattr(previous, "revision", 0) or 0), 1)
        previous_payload = self._store.load_raw_case_payload(getattr(previous, "case_id", "") or candidate.case_id)
        if payload_revision_fingerprint(previous_payload) != payload_revision_fingerprint(payload):
            revision = max(int(getattr(previous, "revision", 0) or 0) + 1, 1)
        persisted = replace(
            candidate,
            revision=revision,
            ci_contract=self._ci_contract(
                case_id=str(getattr(candidate, "case_id", "") or ""),
                baseline_key=str(getattr(candidate, "baseline_key", "") or ""),
                report_id=str(getattr(candidate, "report_id", "") or ""),
                final_decision=str(getattr(candidate, "final_decision", "") or ""),
                error_code=str(getattr(candidate, "error_code", "") or ""),
                final_review_opinion=str(getattr(candidate, "final_review_opinion", "") or ""),
                status=str(getattr(candidate, "status", "") or "open"),
                revision=revision,
                assignee_id=str(getattr(candidate, "assignee_id", "") or ""),
                assignee_display_name=str(getattr(candidate, "assignee_display_name", "") or ""),
                final_reviewer_id=str(getattr(candidate, "final_reviewer_id", "") or ""),
                final_reviewer_display_name=str(getattr(candidate, "final_reviewer_display_name", "") or ""),
                source_refs=dict(getattr(candidate, "source_refs", {}) or {}),
                case_trace=dict(getattr(candidate, "case_trace", {}) or {}),
            ),
        )
        self._store.write_case(persisted)
        self._publish_case_contract_event(persisted, previous=previous)
        return persisted

    def _load_case_for_baseline(self, baseline_key: str) -> AdmissionCase | None:
        return self._store.load_case_for_baseline(baseline_key)

    def _load_case(self, case_id: str) -> AdmissionCase | None:
        return self._store.load_case(case_id)

    def _publish_case_contract_event(self, item: AdmissionCase, *, previous: AdmissionCase | None) -> None:
        if self._outbox_service is None or not hasattr(self._outbox_service, "publish_event"):
            return
        final_decision = str(getattr(item, "final_decision", "") or "").strip().lower()
        if final_decision not in {"pass", "conditional_pass", "fail"}:
            return
        payload = dict(getattr(item, "ci_contract", {}) or {})
        previous_payload = dict(getattr(previous, "ci_contract", {}) or {}) if previous is not None else {}
        if previous_payload == payload:
            return
        self._outbox_service.publish_event(
            event_type="admission_case.updated",
            target_type="admission_case",
            target_id=str(getattr(item, "baseline_key", "") or ""),
            created_by=str(getattr(item, "updated_by", "") or "system"),
            session_source="admission_case_service",
            audit_source={
                "case_id": str(getattr(item, "case_id", "") or ""),
                "case_revision": int(getattr(item, "revision", 1) or 1),
                "sync_reason": "case_contract_changed",
                "final_decision": final_decision,
            },
            payload=payload,
        )

    _error_code = staticmethod(contracts.error_code)
    _case_trace_payload = staticmethod(contracts.case_trace_payload)
    _source_refs = staticmethod(contracts.source_refs)
    _ci_contract = staticmethod(contracts.ci_contract)
    _normalize_status = staticmethod(lifecycle.normalize_status)
    _validate_status_transition = staticmethod(lifecycle.validate_status_transition)
    _lifecycle_event = staticmethod(lifecycle.lifecycle_event)
    _role_audit_entry = staticmethod(lifecycle.role_audit_entry)

    def _execution_summary(self, filters: Mapping[str, Any]):
        return aggregation.execution_summary(self._run_history_service, filters)

    def _top_issues(self, filters: Mapping[str, Any]):
        return aggregation.top_issues(self._analysis_service, filters)

    def _regression_summary(self, filters: Mapping[str, Any]):
        return aggregation.regression_summary(self._regression_service, filters)

    _scenario_coverage = staticmethod(aggregation.scenario_coverage)
    _normalized_filters = staticmethod(aggregation.normalized_filters)
    _scoped_filters = staticmethod(aggregation.scoped_filters)
