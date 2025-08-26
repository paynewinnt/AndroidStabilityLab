from __future__ import annotations

from typing import Any, Mapping
from ...application_payload_integration_acceptance import ApplicationPayloadIntegrationAcceptanceMixin
from stability.time_utils import now_beijing_string


def _generated_at_now() -> str:
    return now_beijing_string()


class AdmissionPayloadMixin(ApplicationPayloadIntegrationAcceptanceMixin):
    def _runner_snapshot(self) -> dict[str, Any]:
        service = getattr(self._bundle, "unattended_runner_service", None)
        if service is None or not hasattr(service, "show_status"):
            observed_at = _generated_at_now()
            return {
                "available": False,
                "observed_at": observed_at,
                "root_dir": "",
                "lock_path": "",
                "heartbeat_path": "",
                "daily_report_paths": {},
                "latest_daily_report": {},
                "weekly_report_paths": {},
                "latest_weekly_report": {},
                "lock_present": False,
                "heartbeat_present": False,
                "lock_state": "released",
                "status": "missing",
                "pid": None,
                "started_at": None,
                "finished_at": None,
                "last_heartbeat_at": None,
                "heartbeat_age_seconds": None,
                "stale_after_seconds": 0,
                "is_stale": False,
                "interval_seconds": 0,
                "max_iterations": 0,
                "task_id": "",
                "force": False,
                "cycle_count": 0,
                "active_cycle_index": 0,
                "stopped_reason": "",
                "last_patrol": {},
                "recent_patrols": [],
            }
        status = service.show_status()
        return {
            "available": True,
            "observed_at": self._isoformat_or_none(getattr(status, "observed_at", None)),
            "root_dir": str(getattr(status, "root_dir", "") or ""),
            "lock_path": str(getattr(status, "lock_path", "") or ""),
            "heartbeat_path": str(getattr(status, "heartbeat_path", "") or ""),
            "daily_report_paths": dict(getattr(status, "daily_report_paths", {}) or {}),
            "latest_daily_report": dict(getattr(status, "latest_daily_report", {}) or {}),
            "weekly_report_paths": dict(getattr(status, "weekly_report_paths", {}) or {}),
            "latest_weekly_report": dict(getattr(status, "latest_weekly_report", {}) or {}),
            "lock_present": bool(getattr(status, "lock_present", False)),
            "heartbeat_present": bool(getattr(status, "heartbeat_present", False)),
            "lock_state": str(getattr(status, "lock_state", "released") or "released"),
            "status": str(getattr(status, "status", "missing") or "missing"),
            "pid": getattr(status, "pid", None),
            "started_at": self._isoformat_or_none(getattr(status, "started_at", None)),
            "finished_at": self._isoformat_or_none(getattr(status, "finished_at", None)),
            "last_heartbeat_at": self._isoformat_or_none(getattr(status, "last_heartbeat_at", None)),
            "heartbeat_age_seconds": getattr(status, "heartbeat_age_seconds", None),
            "stale_after_seconds": int(getattr(status, "stale_after_seconds", 0) or 0),
            "is_stale": bool(getattr(status, "is_stale", False)),
            "interval_seconds": int(getattr(status, "interval_seconds", 0) or 0),
            "max_iterations": int(getattr(status, "max_iterations", 0) or 0),
            "task_id": str(getattr(status, "task_id", "") or ""),
            "force": bool(getattr(status, "force", False)),
            "cycle_count": int(getattr(status, "cycle_count", 0) or 0),
            "active_cycle_index": int(getattr(status, "active_cycle_index", 0) or 0),
            "stopped_reason": str(getattr(status, "stopped_reason", "") or ""),
            "last_patrol": dict(getattr(status, "last_patrol", {}) or {}),
            "recent_patrols": [dict(item) for item in list(getattr(status, "recent_patrols", ()) or [])],
        }

    def _quality_gate_payload(self, item: object) -> dict[str, Any]:
        override = getattr(item, "override", None)
        final_decision = str(getattr(item, "final_decision", "") or "")
        decision_code = str(getattr(item, "error_code", "") or "")
        if not decision_code:
            decision_code = self._derive_admission_error_code(
                final_decision=final_decision or str(getattr(item, "automatic_decision", "") or ""),
                failure_reasons=getattr(item, "failure_reasons", ()),
            )
        return {
            "baseline_key": str(getattr(item, "baseline_key", "") or ""),
            "report_id": str(getattr(item, "report_id", "") or ""),
            "report_name": str(getattr(item, "report_name", "") or ""),
            "evaluated_at": self._isoformat_or_none(getattr(item, "evaluated_at", None)),
            "automatic_decision": str(getattr(item, "automatic_decision", "") or ""),
            "final_decision": final_decision,
            "error_code": decision_code,
            "final_review_opinion": str(getattr(item, "final_review_opinion", "") or ""),
            "failure_reasons": list(getattr(item, "failure_reasons", ()) or ()),
            "policy_versions": list(getattr(item, "policy_versions", ()) or ()),
            "candidate_paths": list(getattr(item, "candidate_paths", ()) or ()),
            "baseline_paths": list(getattr(item, "baseline_paths", ()) or ()),
            "report_created_at": self._isoformat_or_none(getattr(item, "report_created_at", None)),
            "updated_at": self._isoformat_or_none(getattr(item, "updated_at", None)),
            "updated_by": str(getattr(item, "updated_by", "") or ""),
            "latest_audit_summary": dict(getattr(item, "latest_audit_summary", {}) or {}),
            "current_report_golden_suite": dict(getattr(item, "current_report_golden_suite", {}) or {}),
            "report_summary": dict(getattr(item, "report_summary", {}) or {}),
            "source_links": dict(getattr(item, "source_links", {}) or {}),
            "triggered_rules": [
                {
                    "rule_key": str(getattr(entry, "rule_key", "") or ""),
                    "rule_name": str(getattr(entry, "rule_name", "") or ""),
                    "rule_version": str(getattr(entry, "rule_version", "") or ""),
                    "decision_on_trigger": str(getattr(entry, "decision_on_trigger", "") or ""),
                    "observed_value": getattr(entry, "observed_value", None),
                    "threshold": getattr(entry, "threshold", None),
                    "message": str(getattr(entry, "message", "") or ""),
                    "source": str(getattr(entry, "source", "") or ""),
                }
                for entry in (getattr(item, "triggered_rules", ()) or ())
            ],
            "triggered_rule_count": len(getattr(item, "triggered_rules", ()) or ()),
            "risk_items": [
                self._performance_risk_item_payload(entry)
                for entry in (getattr(item, "risk_items", ()) or ())
            ],
            "risk_count": len(getattr(item, "risk_items", ()) or ()),
            "performance_risk_items": [
                self._performance_risk_item_payload(entry)
                for entry in (getattr(item, "performance_risk_items", ()) or ())
            ],
            "performance_risk_count": len(getattr(item, "performance_risk_items", ()) or ()),
            "coverage_gaps": [
                {
                    "gap_key": str(getattr(entry, "gap_key", "") or ""),
                    "category": str(getattr(entry, "category", "") or ""),
                    "severity": str(getattr(entry, "severity", "") or ""),
                    "summary": str(getattr(entry, "summary", "") or ""),
                    "observed_value": getattr(entry, "observed_value", None),
                    "required_value": getattr(entry, "required_value", None),
                    "source": str(getattr(entry, "source", "") or ""),
                }
                for entry in (getattr(item, "coverage_gaps", ()) or ())
            ],
            "coverage_gap_count": len(getattr(item, "coverage_gaps", ()) or ()),
            "has_override": override is not None,
            "override": (
                {
                    "override_id": str(getattr(override, "override_id", "") or ""),
                    "baseline_key": str(getattr(override, "baseline_key", "") or ""),
                    "automatic_decision": str(getattr(override, "automatic_decision", "") or ""),
                    "final_decision": str(getattr(override, "final_decision", "") or ""),
                    "reason": str(getattr(override, "reason", "") or ""),
                    "created_at": self._isoformat_or_none(getattr(override, "created_at", None)),
                    "created_by": str(getattr(override, "created_by", "") or ""),
                    "session_source": str(getattr(override, "session_source", "") or ""),
                    "audit_source": dict(getattr(override, "audit_source", {}) or {}),
                    "comment": str(getattr(override, "comment", "") or ""),
                    "evidence_paths": list(getattr(override, "evidence_paths", ()) or ()),
                }
                if override is not None
                else None
            ),
        }

    def _service_admission_case_payload(
        self,
        *,
        baseline_key: str = "",
        item: object | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "admission_case_service", None)
        if service is None:
            return {}
        for method_name in (
            "export_admission_case_payload",
            "build_admission_case_payload",
            "get_admission_case_payload",
            "case_payload",
        ):
            method = getattr(service, method_name, None)
            if method is None:
                continue
            for kwargs in (
                {"case": item} if item is not None else {},
                {"baseline_key": baseline_key} if baseline_key else {},
            ):
                if not kwargs:
                    continue
                try:
                    return self._normalize_admission_case_payload(method(**kwargs))
                except TypeError:
                    continue
        return {}

    def _normalize_admission_case_payload(self, item: object) -> dict[str, Any]:
        if isinstance(item, Mapping):
            payload = dict(item)
        elif hasattr(item, "__dataclass_fields__"):
            payload = self._jsonable_mapping(item)
        else:
            payload = {}
        if not payload:
            return {}
        payload["contract_version"] = str(payload.get("contract_version", "") or "admission_case.v1")
        payload["case_id"] = str(payload.get("case_id", "") or "")
        payload["baseline_key"] = str(payload.get("baseline_key", "") or "")
        payload["report_id"] = str(payload.get("report_id", "") or "")
        payload["status"] = str(payload.get("status", "") or "open")
        payload["revision"] = int(payload.get("revision", 1) or 1)
        return payload

    def _with_admission_case_collaboration(self, payload: dict[str, Any]) -> dict[str, Any]:
        collaboration_service = getattr(self._bundle, "collaboration_service", None)
        if collaboration_service is None or not hasattr(collaboration_service, "get_admission_case_record"):
            return payload
        try:
            record = collaboration_service.get_admission_case_record(str(payload.get("baseline_key", "") or ""))
        except Exception:
            record = None
        if record is None:
            return payload
        has_collaboration = bool(getattr(record, "comments", ()) or getattr(record, "events", ()))
        has_collaboration = has_collaboration or bool(str(getattr(record, "assignee_id", "") or "").strip())
        has_collaboration = has_collaboration or bool(str(getattr(record, "final_reviewer_id", "") or "").strip())
        has_collaboration = has_collaboration or (
            str(getattr(record, "workflow_state", "") or "").strip() not in {"", "new"}
        )
        if has_collaboration:
            payload.update(self._admission_collaboration_payload(record))
        return payload

    def _admission_case_payload(self, item: object) -> dict[str, Any]:
        service_payload = self._service_admission_case_payload(item=item)
        if service_payload:
            return self._with_admission_case_collaboration(service_payload)
        quality_gate = getattr(item, "quality_gate", None)
        execution_summary = getattr(item, "execution_summary", None)
        regression_summary = getattr(item, "regression_summary", None)
        scenario_coverage = getattr(item, "scenario_coverage", None)
        final_decision = str(getattr(item, "final_decision", "") or "")
        if not final_decision and quality_gate is not None:
            final_decision = str(getattr(quality_gate, "final_decision", "") or "")
        error_code = str(getattr(item, "error_code", "") or "")
        if not error_code:
            error_code = self._derive_admission_error_code(
                final_decision=final_decision or str(getattr(quality_gate, "automatic_decision", "") or ""),
                failure_reasons=getattr(quality_gate, "failure_reasons", ()),
            )
        raw_case_trace = getattr(item, "case_trace", {}) or {}
        case_trace = dict(raw_case_trace) if isinstance(raw_case_trace, dict) else {"entries": list(raw_case_trace)}
        payload = {
            "contract_version": str(getattr(item, "contract_version", "") or "admission_case.v1"),
            "case_id": str(getattr(item, "case_id", "") or ""),
            "baseline_key": str(getattr(item, "baseline_key", "") or ""),
            "report_id": str(getattr(item, "report_id", "") or ""),
            "report_name": str(getattr(item, "report_name", "") or ""),
            "status": str(getattr(item, "status", "") or "open"),
            "revision": int(getattr(item, "revision", 1) or 1),
            "assignee_id": str(getattr(item, "assignee_id", "") or ""),
            "assignee_display_name": str(getattr(item, "assignee_display_name", "") or ""),
            "final_reviewer_id": str(getattr(item, "final_reviewer_id", "") or ""),
            "final_reviewer_display_name": str(getattr(item, "final_reviewer_display_name", "") or ""),
            "created_at": self._isoformat_or_none(getattr(item, "created_at", None)),
            "updated_at": self._isoformat_or_none(getattr(item, "updated_at", None)),
            "updated_by": str(getattr(item, "updated_by", "") or ""),
            "state_machine_version": str(getattr(item, "state_machine_version", "") or "admission_case.lifecycle.v1"),
            "filters": dict(getattr(item, "filters", {}) or {}),
            "final_review_opinion": str(getattr(item, "final_review_opinion", "") or ""),
            "final_decision": final_decision,
            "error_code": error_code,
            "case_trace": case_trace,
            "lifecycle_events": [
                {
                    "entry_id": str(getattr(entry, "entry_id", "") or ""),
                    "action": str(getattr(entry, "action", "") or ""),
                    "from_status": str(getattr(entry, "from_status", "") or ""),
                    "to_status": str(getattr(entry, "to_status", "") or ""),
                    "changed_at": self._isoformat_or_none(getattr(entry, "changed_at", None)),
                    "changed_by": str(getattr(entry, "changed_by", "") or ""),
                    "reason": str(getattr(entry, "reason", "") or ""),
                    "audit_event_id": str(getattr(entry, "audit_event_id", "") or ""),
                    "permission_check_id": str(getattr(entry, "permission_check_id", "") or ""),
                    "session_id": str(getattr(entry, "session_id", "") or ""),
                }
                for entry in list(getattr(item, "lifecycle_events", ()) or ())
            ],
            "role_audit_entries": [
                {
                    "entry_id": str(getattr(entry, "entry_id", "") or ""),
                    "role_name": str(getattr(entry, "role_name", "") or ""),
                    "changed_at": self._isoformat_or_none(getattr(entry, "changed_at", None)),
                    "changed_by": str(getattr(entry, "changed_by", "") or ""),
                    "from_actor_id": str(getattr(entry, "from_actor_id", "") or ""),
                    "from_actor_display_name": str(getattr(entry, "from_actor_display_name", "") or ""),
                    "to_actor_id": str(getattr(entry, "to_actor_id", "") or ""),
                    "to_actor_display_name": str(getattr(entry, "to_actor_display_name", "") or ""),
                    "reason": str(getattr(entry, "reason", "") or ""),
                    "audit_event_id": str(getattr(entry, "audit_event_id", "") or ""),
                    "permission_check_id": str(getattr(entry, "permission_check_id", "") or ""),
                    "session_id": str(getattr(entry, "session_id", "") or ""),
                }
                for entry in list(getattr(item, "role_audit_entries", ()) or ())
            ],
            "report_summary": dict(getattr(item, "report_summary", {}) or {}),
            "latest_audit_summary": dict(getattr(item, "latest_audit_summary", {}) or {}),
            "source_links": dict(getattr(item, "source_links", {}) or {}),
            "source_refs": dict(getattr(item, "source_refs", {}) or {}),
            "ci_contract": dict(getattr(item, "ci_contract", {}) or {}),
            "quality_gate": self._quality_gate_payload(quality_gate) if quality_gate is not None else {},
            "override": self._quality_gate_payload(quality_gate).get("override") if quality_gate is not None else None,
            "top_issue_count": len(list(getattr(item, "top_issues", ()) or ())),
            "performance_risk_count": len(list(getattr(item, "performance_risk_items", ()) or ())),
            "execution_summary": {
                "total_runs": int(getattr(execution_summary, "total_runs", 0) or 0),
                "status_counts": dict(getattr(execution_summary, "status_counts", {}) or {}),
                "failed_run_count": int(getattr(execution_summary, "failed_run_count", 0) or 0),
                "issue_run_count": int(getattr(execution_summary, "issue_run_count", 0) or 0),
                "task_ids": list(getattr(execution_summary, "task_ids", ()) or ()),
                "task_names": list(getattr(execution_summary, "task_names", ()) or ()),
                "package_names": list(getattr(execution_summary, "package_names", ()) or ()),
                "template_types": list(getattr(execution_summary, "template_types", ()) or ()),
                "device_ids": list(getattr(execution_summary, "device_ids", ()) or ()),
                "latest_run_id": str(getattr(execution_summary, "latest_run_id", "") or ""),
                "latest_run_status": str(getattr(execution_summary, "latest_run_status", "") or ""),
                "latest_run_created_at": self._isoformat_or_none(getattr(execution_summary, "latest_run_created_at", None)),
                "recent_runs": [dict(entry) for entry in list(getattr(execution_summary, "recent_runs", ()) or ())],
            },
            "top_issues": [
                self._admission_top_issue_payload(entry)
                for entry in (getattr(item, "top_issues", ()) or ())
            ],
            "regression_summary": {
                "available": bool(getattr(regression_summary, "available", False)),
                "dimension": str(getattr(regression_summary, "dimension", "") or ""),
                "overall_result": str(getattr(regression_summary, "overall_result", "insufficient_data") or "insufficient_data"),
                "issue_result_summary": dict(getattr(regression_summary, "issue_result_summary", {}) or {}),
                "metric_result_summary": dict(getattr(regression_summary, "metric_result_summary", {}) or {}),
                "reasons": list(getattr(regression_summary, "reasons", ()) or ()),
                "comparability_notes": list(getattr(regression_summary, "comparability_notes", ()) or ()),
                "source_filters": dict(getattr(regression_summary, "source_filters", {}) or {}),
            },
            "scenario_coverage": {
                "scenario_count": int(getattr(scenario_coverage, "scenario_count", 0) or 0),
                "scenarios": list(getattr(scenario_coverage, "scenarios", ()) or ()),
                "issue_scenario_count": int(getattr(scenario_coverage, "issue_scenario_count", 0) or 0),
                "issue_scenarios": list(getattr(scenario_coverage, "issue_scenarios", ()) or ()),
                "coverage_state": str(getattr(scenario_coverage, "coverage_state", "missing") or "missing"),
                "notes": list(getattr(scenario_coverage, "notes", ()) or ()),
            },
            "performance_risk_items": [
                self._performance_risk_item_payload(entry)
                for entry in (getattr(item, "performance_risk_items", ()) or ())
            ],
        }
        return self._with_admission_case_collaboration(payload)

    def _admission_top_issue_payload(self, entry: object) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "fingerprint": str(getattr(entry, "fingerprint", "") or ""),
            "title": str(getattr(entry, "title", "") or ""),
            "issue_type": str(getattr(entry, "issue_type", "") or ""),
            "severity": str(getattr(entry, "severity", "") or ""),
            "occurrence_count": int(getattr(entry, "occurrence_count", 0) or 0),
            "affected_run_count": int(getattr(entry, "affected_run_count", 0) or 0),
            "affected_device_count": int(getattr(entry, "affected_device_count", 0) or 0),
            "affected_scenario_count": int(getattr(entry, "affected_scenario_count", 0) or 0),
            "last_seen_at": self._isoformat_or_none(getattr(entry, "last_seen_at", None)),
            "affected_scenarios": list(getattr(entry, "affected_scenarios", ()) or ()),
            "affected_versions": list(getattr(entry, "affected_versions", ()) or ()),
            "metadata": dict(getattr(entry, "metadata", {}) or {}),
        }
        self._append_advanced_issue_evidence(payload, item=entry)
        return payload

    @staticmethod
    def _performance_risk_item_payload(entry: object) -> dict[str, Any]:
        details = dict(getattr(entry, "details", {}) or {})
        payload: dict[str, Any] = {
            "risk_key": str(getattr(entry, "risk_key", "") or ""),
            "category": str(getattr(entry, "category", "") or ""),
            "severity": str(getattr(entry, "severity", "") or ""),
            "summary": str(getattr(entry, "summary", "") or ""),
            "details": details,
            "source": str(getattr(entry, "source", "") or ""),
            "blocks_admission": bool(getattr(entry, "blocks_admission", False)),
        }
        for key in AdmissionPayloadMixin._performance_risk_detail_fields():
            value = getattr(entry, key, None)
            if value is None:
                value = details.get(key)
            if value not in (None, "", (), []):
                if isinstance(value, Mapping):
                    payload[key] = dict(value)
                elif isinstance(value, (list, tuple)):
                    payload[key] = list(value)
                else:
                    payload[key] = value
        return payload

    @staticmethod
    def _performance_risk_detail_fields() -> list[str]:
        return [
            "threshold_source",
            "matched_scope",
            "threshold_detail",
            "threshold_details",
            "threshold",
            "observed_value",
            "metric_key",
            "scope_key",
        ]

    @staticmethod
    def _derive_admission_error_code(*, final_decision: str, failure_reasons: object) -> str:
        normalized = str(final_decision or "").strip().lower()
        if normalized in {"pass", "approved", "ok"}:
            return "PASS"
        if normalized in {"conditional_pass", "warn", "warning", "conditional"}:
            return "CONDITIONAL_PASS"
        if normalized in {"fail", "rejected", "reject"}:
            return "FAIL"
        if normalized:
            return "UNKNOWN_DECISION"
        if failure_reasons:
            return "REQUIRES_REVIEW"
        return "UNKNOWN_DECISION"

    def _baseline_summaries(self, *, limit: int) -> list[dict[str, Any]]:
        items = self._legacy_baseline_summaries(limit=limit)
        service = getattr(self._bundle, "quality_gate_service", None)
        case_service = getattr(self._bundle, "admission_case_service", None)
        if service is None or not hasattr(service, "list_quality_gates"):
            if case_service is None or not hasattr(case_service, "list_cases"):
                return [self._admission_summary_entry(item, admission_case={}, quality_gate={}) for item in items]
            case_payloads = {
                str(getattr(item, "baseline_key", "") or ""): self._admission_case_payload(item)
                for item in list(case_service.list_cases(limit=limit))
                if str(getattr(item, "baseline_key", "") or "").strip()
            }
            return [
                self._admission_summary_entry(
                    item,
                    admission_case=dict(case_payloads.get(str(item.get("baseline_key", "") or ""), {}) or {}),
                    quality_gate={},
                )
                for item in items
            ]
        gate_results = list(service.list_quality_gates(limit=limit))
        gate_payloads = {
            str(getattr(item, "baseline_key", "") or ""): self._quality_gate_payload(item)
            for item in gate_results
            if str(getattr(item, "baseline_key", "") or "").strip()
        }
        case_payloads: dict[str, dict[str, Any]] = {}
        if case_service is not None and hasattr(case_service, "list_cases"):
            case_payloads = {
                str(getattr(item, "baseline_key", "") or ""): self._admission_case_payload(item)
                for item in list(case_service.list_cases(limit=limit))
                if str(getattr(item, "baseline_key", "") or "").strip()
            }
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            key = str(item.get("baseline_key", "") or "")
            merged.append(
                self._admission_summary_entry(
                    item,
                    admission_case=dict(case_payloads.get(key, {}) or {}),
                    quality_gate=dict(gate_payloads.get(key, {}) or {}),
                )
            )
            if key:
                seen.add(key)
        for key, payload in gate_payloads.items():
            if key not in seen:
                merged.append(
                    self._admission_summary_entry(
                        {"baseline_key": key},
                        admission_case=dict(case_payloads.get(key, {}) or {}),
                        quality_gate=dict(payload),
                    )
                )
                seen.add(key)
        for key, payload in case_payloads.items():
            if key not in seen:
                merged.append(
                    self._admission_summary_entry(
                        {"baseline_key": key},
                        admission_case=dict(payload),
                        quality_gate={},
                    )
                )
        return merged

    def _admission_summary_entry(
        self,
        legacy_baseline: Mapping[str, Any],
        *,
        admission_case: Mapping[str, Any],
        quality_gate: Mapping[str, Any],
    ) -> dict[str, Any]:
        baseline = dict(legacy_baseline or {})
        case = dict(admission_case or {})
        gate = dict(quality_gate or {})
        baseline_key = str(case.get("baseline_key", "") or gate.get("baseline_key", "") or baseline.get("baseline_key", "") or "")
        report_id = str(case.get("report_id", "") or gate.get("report_id", "") or baseline.get("report_id", "") or "")
        report_name = str(case.get("report_name", "") or gate.get("report_name", "") or baseline.get("report_name", "") or "")
        golden_suite = dict(baseline.get("current_report_golden_suite", {}) or {})
        regression_summary = dict(case.get("regression_summary", {}) or {})
        return {
            "baseline_key": baseline_key,
            "report_id": report_id,
            "report_name": report_name,
            "case_id": str(case.get("case_id", "") or ""),
            "status": str(case.get("status", "") or "new"),
            "workflow_state": str(case.get("workflow_state", "") or case.get("status", "") or "new"),
            "assignee_id": str(case.get("assignee_id", "") or ""),
            "assignee_display_name": str(case.get("assignee_display_name", "") or ""),
            "final_reviewer_id": str(case.get("final_reviewer_id", "") or ""),
            "final_reviewer_display_name": str(case.get("final_reviewer_display_name", "") or ""),
            "admission_case": case,
            "evidence": {
                "quality_gate": gate,
                "rule_review_report": baseline,
                "golden_suite": golden_suite,
                "regression": regression_summary,
            },
            "legacy_detail": {
                "quality_gate": gate,
                "rule_review_report": baseline,
                "golden_suite": golden_suite,
                "regression": regression_summary,
            },
        }

    def _legacy_baseline_summaries(self, *, limit: int) -> list[dict[str, Any]]:
        service = getattr(self._bundle, "rule_review_report_service", None)
        if service is None or not hasattr(service, "list_baselines"):
            return []
        baselines = list(service.list_baselines())
        if limit > 0:
            baselines = baselines[:limit]
        items: list[dict[str, Any]] = []
        for baseline in baselines:
            latest_audit = None
            if getattr(baseline, "baseline_key", ""):
                try:
                    latest_audit = service.show_latest_baseline_audit(
                        baseline_key=baseline.baseline_key,
                        version_limit=3,
                    )
                except Exception:
                    latest_audit = None
            items.append(
                {
                    "baseline_key": baseline.baseline_key,
                    "report_id": baseline.report_id,
                    "report_name": baseline.report_name,
                    "policy_versions": list(baseline.policy_versions),
                    "candidate_paths": list(baseline.candidate_paths),
                    "baseline_paths": list(baseline.baseline_paths),
                    "report_created_at": self._isoformat_or_none(baseline.report_created_at),
                    "updated_at": self._isoformat_or_none(baseline.updated_at),
                    "updated_by": baseline.updated_by,
                    "latest_audit_id": baseline.latest_audit_id,
                    "latest_audit_detail_path": baseline.latest_audit_detail_path,
                    "latest_audit_markdown_path": baseline.latest_audit_markdown_path,
                    "latest_audit_html_path": baseline.latest_audit_html_path,
                    "latest_audit_index_path": baseline.latest_audit_index_path,
                    "latest_audit_version_count": baseline.latest_audit_version_count,
                    "latest_audit_summary": dict(getattr(latest_audit, "summary", {}) or {}) if latest_audit else {},
                    "current_report_golden_suite": (
                        dict(dict(getattr(latest_audit, "summary", {}) or {}).get("current_report_golden_suite", {}) or {})
                        if latest_audit
                        else {}
                    ),
                    "retention": dict(getattr(latest_audit, "retention", {}) or {}) if latest_audit else {},
                    "recent_versions": [
                        {
                            "revision_id": version.revision_id,
                            "action": version.action,
                            "changed_at": self._isoformat_or_none(version.changed_at),
                            "changed_by": version.changed_by,
                            "report_id": version.report_id,
                            "report_name": version.report_name,
                        }
                        for version in (getattr(latest_audit, "versions", ()) or ())
                    ],
                }
            )
        return items

    def _quality_gate_detail_payload(self, baseline_key: str) -> dict[str, Any]:
        service = getattr(self._bundle, "quality_gate_service", None)
        if service is None or not hasattr(service, "get_quality_gate"):
            return {}
        return self._quality_gate_payload(service.get_quality_gate(baseline_key.strip()))

    def _admission_case_detail_payload(self, baseline_key: str) -> dict[str, Any]:
        service = getattr(self._bundle, "admission_case_service", None)
        if service is None:
            return {}
        service_payload = self._service_admission_case_payload(baseline_key=baseline_key.strip())
        if service_payload:
            return self._with_admission_case_collaboration(service_payload)
        if not hasattr(service, "get_case"):
            return {}
        return self._admission_case_payload(service.get_case(baseline_key.strip()))

    def _admission_report_response_payload(self, baseline_key: str) -> dict[str, Any]:
        key = baseline_key.strip()
        return {
            "page": "admission_report",
            "title": f"准入报告 | {key}",
            "generated_at": _generated_at_now(),
            "baseline_key": key,
            "formal_report": self._admission_report_payload(key),
        }

    def _admission_report_payload(self, baseline_key: str) -> dict[str, Any]:
        service = getattr(self._bundle, "admission_case_service", None)
        if service is None:
            return self._fallback_admission_report_payload(baseline_key, case_payload={})
        for method_name in (
            "export_admission_report_payload",
            "build_admission_report",
            "build_admission_report_payload",
            "get_admission_report_payload",
            "build_report_payload",
            "get_report_payload",
        ):
            method = getattr(service, method_name, None)
            if method is None:
                continue
            try:
                return self._normalize_admission_report_payload(method(baseline_key=baseline_key), source="service")
            except TypeError:
                return self._normalize_admission_report_payload(method(baseline_key), source="service")
        case_payload = self._admission_case_detail_payload(baseline_key)
        return self._fallback_admission_report_payload(baseline_key, case_payload=case_payload)

    def _normalize_admission_report_payload(self, item: object, *, source: str) -> dict[str, Any]:
        if isinstance(item, Mapping):
            payload = dict(item)
        elif hasattr(item, "__dataclass_fields__"):
            payload = self._jsonable_mapping(item)
        else:
            payload = {
                "report_contract_version": str(getattr(item, "report_contract_version", "") or "admission_report.v1"),
                "report_id": str(getattr(item, "report_id", "") or ""),
                "baseline_key": str(getattr(item, "baseline_key", "") or ""),
                "status": str(getattr(item, "status", "") or ""),
                "final_decision": str(getattr(item, "final_decision", "") or ""),
                "risk_level": str(getattr(item, "risk_level", "") or ""),
                "quality_gate_summary": dict(getattr(item, "quality_gate_summary", {}) or {}),
                "top_issue_summary": dict(getattr(item, "top_issue_summary", {}) or {}),
                "performance_risk_summary": dict(getattr(item, "performance_risk_summary", {}) or {}),
                "manual_overrides": dict(getattr(item, "manual_overrides", {}) or {}),
                "collaboration_summary": dict(getattr(item, "collaboration_summary", {}) or {}),
                "external_sync_summary": dict(getattr(item, "external_sync_summary", {}) or {}),
                "evidence_refs": dict(getattr(item, "evidence_refs", {}) or {}),
                "source_refs": dict(getattr(item, "source_refs", {}) or {}),
                "recommended_actions": list(getattr(item, "recommended_actions", ()) or ()),
                "generated_at": self._isoformat_or_none(getattr(item, "generated_at", None)),
            }
        if "formal_report" in payload and isinstance(payload["formal_report"], Mapping):
            payload = dict(payload["formal_report"])
        payload["report_contract_version"] = str(payload.get("report_contract_version", "") or "admission_report.v1")
        payload["source"] = str(payload.get("source", "") or source)
        if "recommended_actions" in payload:
            payload["recommended_actions"] = list(payload.get("recommended_actions") or [])
        return payload

    def _fallback_admission_report_payload(self, baseline_key: str, *, case_payload: Mapping[str, Any]) -> dict[str, Any]:
        case = dict(case_payload or {})
        quality_gate = dict(case.get("quality_gate", {}) or {})
        top_issues = list(case.get("top_issues", []) or [])
        performance_risks = list(case.get("performance_risk_items", []) or [])
        override = quality_gate.get("override") or case.get("override") or {}
        quality_gate_summary = {
            "automatic_decision": quality_gate.get("automatic_decision", ""),
            "final_decision": case.get("final_decision", quality_gate.get("final_decision", "")),
            "error_code": case.get("error_code", quality_gate.get("error_code", "")),
            "triggered_rule_count": quality_gate.get("triggered_rule_count", 0),
            "risk_count": quality_gate.get("risk_count", 0),
            "performance_risk_count": len(performance_risks) or quality_gate.get("performance_risk_count", 0),
            "coverage_gap_count": quality_gate.get("coverage_gap_count", 0),
        }
        final_decision = str(case.get("final_decision", quality_gate.get("final_decision", "")) or "")
        return {
            "report_contract_version": "admission_report.v1",
            "source": "fallback",
            "report_id": str(case.get("report_id", "") or ""),
            "baseline_key": str(case.get("baseline_key", "") or baseline_key),
            "status": str(case.get("status", "") or ""),
            "final_decision": final_decision,
            "risk_level": self._derive_admission_report_risk_level(
                final_decision=final_decision,
                top_issue_count=len(top_issues),
                performance_risk_count=len(performance_risks),
                quality_gate_summary=quality_gate_summary,
            ),
            "quality_gate_summary": quality_gate_summary,
            "top_issue_summary": {"count": len(top_issues), "items": top_issues[:5]},
            "performance_risk_summary": {"count": len(performance_risks), "items": performance_risks[:5]},
            "manual_overrides": {
                "has_override": bool(override),
                "override": dict(override) if isinstance(override, Mapping) else {},
                "final_review_opinion": str(case.get("final_review_opinion", "") or ""),
            },
            "collaboration_summary": {
                "assignee_id": str(case.get("assignee_id", "") or ""),
                "assignee_display_name": str(case.get("assignee_display_name", "") or ""),
                "final_reviewer_id": str(case.get("final_reviewer_id", "") or ""),
                "final_reviewer_display_name": str(case.get("final_reviewer_display_name", "") or ""),
                "status": str(case.get("status", "") or ""),
                "revision": int(case.get("revision", 1) or 1),
            },
            "external_sync_summary": {
                "ci_contract": dict(case.get("ci_contract", {}) or {}),
                "source_links": dict(case.get("source_links", {}) or {}),
            },
            "evidence_refs": dict(case.get("source_refs", {}) or {}),
            "source_refs": dict(case.get("source_refs", {}) or {}),
            "recommended_actions": self._admission_report_recommended_actions(
                final_decision=final_decision,
                top_issue_count=len(top_issues),
                performance_risk_count=len(performance_risks),
                has_override=bool(override),
            ),
            "generated_at": None,
        }

    @staticmethod
    def _derive_admission_report_risk_level(
        *,
        final_decision: str,
        top_issue_count: int,
        performance_risk_count: int,
        quality_gate_summary: Mapping[str, Any],
    ) -> str:
        decision = final_decision.strip().lower()
        if decision in {"fail", "reject", "rejected", "block"}:
            return "critical"
        if top_issue_count > 0 or int(quality_gate_summary.get("risk_count", 0) or 0) > 0:
            return "high"
        if performance_risk_count > 0 or int(quality_gate_summary.get("coverage_gap_count", 0) or 0) > 0:
            return "medium"
        if decision in {"pass", "approved"}:
            return "low"
        return "unknown"

    @staticmethod
    def _admission_report_recommended_actions(
        *,
        final_decision: str,
        top_issue_count: int,
        performance_risk_count: int,
        has_override: bool,
    ) -> list[str]:
        actions: list[str] = []
        decision = final_decision.strip().lower()
        if decision in {"fail", "reject", "rejected", "block"}:
            actions.append("Block release and resolve failing admission evidence before retry.")
        if top_issue_count > 0:
            actions.append("Review top issues and confirm owner, scenario coverage, and fix plan.")
        if performance_risk_count > 0:
            actions.append("Review performance risks against scoped thresholds before final sign-off.")
        if has_override:
            actions.append("Audit manual override reason and evidence before external write-back.")
        if not actions:
            actions.append("No blocking evidence found; proceed with standard release sign-off.")
        return actions
