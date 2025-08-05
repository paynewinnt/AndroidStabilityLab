from __future__ import annotations

from .application_common import *
from .application_payload_integration_acceptance import ApplicationPayloadIntegrationAcceptanceMixin
from stability.time_utils import now_beijing_string


def _generated_at_now() -> str:
    return now_beijing_string()


class ApplicationPayloadQualityIntegrationMixin(ApplicationPayloadIntegrationAcceptanceMixin):
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
        if isinstance(raw_case_trace, dict):
            case_trace = dict(raw_case_trace)
        else:
            case_trace = {"entries": list(raw_case_trace)}
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
            "override": (
                self._quality_gate_payload(quality_gate).get("override")
                if quality_gate is not None
                else None
            ),
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
            "top_issue_count": len(getattr(item, "top_issues", ()) or ()),
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
            "performance_risk_count": len(getattr(item, "performance_risk_items", ()) or ()),
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
        for key in (
            "threshold_source",
            "matched_scope",
            "threshold_detail",
            "threshold_details",
            "threshold",
            "observed_value",
            "metric_key",
            "scope_key",
        ):
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

    def _integration_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "integration_outbox_service", None)
        if service is None:
            return {
                "page": "integration_outbox",
                "title": "Integration Outbox",
                "generated_at": _generated_at_now(),
                "current_actor": dict(request_context or {}).get("current_actor", {}),
                "summary": {"event_count": 0, "webhook_count": 0},
                "worker": self._integration_worker_payload(None),
                "im_acceptance": self._integration_im_acceptance_payload(None, events=[], webhooks=[]),
                "delivery_receipts": [],
                "consumer_receipts": [],
                "replay_receipts": [],
                "operator_receipts": [],
                "idempotency_contract": self._integration_idempotency_contract_payload(),
                "callback_contract": self._integration_callback_contract_payload(),
                "events": [],
                "webhooks": [],
            }
        limit = self._int_query(query, "limit", default=20)
        events = list(service.list_events(limit=limit)) if hasattr(service, "list_events") else []
        webhooks = list(service.list_webhooks()) if hasattr(service, "list_webhooks") else []
        delivery_status_counts: dict[str, int] = {}
        delivery_channel_counts: dict[str, int] = {}
        dead_letter_count = 0
        retry_pending_count = 0
        delivered_count = 0
        alerting_count = 0
        im_webhook_count = 0
        ci_webhook_count = 0
        defect_webhook_count = 0
        release_webhook_count = 0
        feishu_webhook_count = 0
        for item in events:
            status_key = str(getattr(item, "delivery_status", "") or "pending")
            delivery_status_counts[status_key] = delivery_status_counts.get(status_key, 0) + 1
            if status_key == "dead_letter":
                dead_letter_count += 1
            if status_key == "retry_pending":
                retry_pending_count += 1
            if status_key == "delivered":
                delivered_count += 1
            if str(getattr(item, "alert_status", "") or "") not in {"", "none", "self"}:
                alerting_count += 1
        for item in webhooks:
            channel = str(getattr(item, "delivery_channel", "") or "generic")
            delivery_channel_counts[channel] = delivery_channel_counts.get(channel, 0) + 1
            if channel == "im_notify":
                im_webhook_count += 1
            if channel == "feishu_bot":
                feishu_webhook_count += 1
            if channel == "ci_callback":
                ci_webhook_count += 1
            if channel == "defect_sync":
                defect_webhook_count += 1
            if channel == "release_submission":
                release_webhook_count += 1
        event_payloads = [self._integration_event_payload(item) for item in events]
        consumer_receipts = [
            dict(item)
            for event_payload in event_payloads
            for item in event_payload.get("consumer_receipts", [])
            if isinstance(item, dict)
        ]
        replay_receipts = [
            dict(item)
            for event_payload in event_payloads
            for item in event_payload.get("replay_receipts", [])
            if isinstance(item, dict)
        ]
        operator_receipts = [
            dict(item)
            for event_payload in event_payloads
            for item in event_payload.get("operator_receipts", [])
            if isinstance(item, dict)
        ]
        delivery_receipts = [
            dict(item["delivery_receipt"])
            for item in event_payloads
            if isinstance(item.get("delivery_receipt"), dict)
        ]
        return {
            "page": "integration_outbox",
            "title": "Integration Outbox",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "summary": {
                "event_count": len(events),
                "webhook_count": len(webhooks),
                "delivery_status_counts": delivery_status_counts,
                "delivery_channel_counts": delivery_channel_counts,
                "dead_letter_count": dead_letter_count,
                "retry_pending_count": retry_pending_count,
                "delivered_count": delivered_count,
                "alerting_event_count": alerting_count,
                "im_webhook_count": im_webhook_count,
                "feishu_webhook_count": feishu_webhook_count,
                "ci_webhook_count": ci_webhook_count,
                "defect_webhook_count": defect_webhook_count,
                "release_webhook_count": release_webhook_count,
                "consumer_receipt_count": len(consumer_receipts),
                "replay_receipt_count": len(replay_receipts),
                "operator_receipt_count": len(operator_receipts),
            },
            "worker": self._integration_worker_payload(service, webhooks=webhooks),
            "im_acceptance": self._integration_im_acceptance_payload(service, events=event_payloads, webhooks=webhooks),
            "consumer_receipts": consumer_receipts,
            "replay_receipts": replay_receipts,
            "operator_receipts": operator_receipts,
            "delivery_receipts": delivery_receipts,
            "idempotency_contract": self._integration_idempotency_contract_payload(),
            "callback_contract": self._integration_callback_contract_payload(),
            "events": event_payloads,
            "webhooks": [
                {
                    "webhook_id": str(getattr(item, "webhook_id", "") or ""),
                    "name": str(getattr(item, "name", "") or ""),
                    "url": str(getattr(item, "url", "") or ""),
                    "subscribed_event_types": list(getattr(item, "subscribed_event_types", ()) or ()),
                    "created_at": self._isoformat_or_none(getattr(item, "created_at", None)),
                    "created_by": str(getattr(item, "created_by", "") or ""),
                    "secret_hint": str(getattr(item, "secret_hint", "") or ""),
                    "signature_key_id": str(getattr(item, "signature_key_id", "") or ""),
                    "accepted_signature_key_ids": list(getattr(item, "accepted_signature_key_ids", ()) or ()),
                    "failure_policy": str(getattr(item, "failure_policy", "") or ""),
                    "delivery_channel": str(getattr(item, "delivery_channel", "") or ""),
                    "security_boundary": self._integration_webhook_security_boundary(str(getattr(item, "url", "") or "")),
                    "requires_tls": self._integration_webhook_requires_tls(str(getattr(item, "url", "") or "")),
                    "requires_signing_secret": self._integration_webhook_requires_signing_secret(str(getattr(item, "url", "") or "")),
                }
                for item in webhooks
            ],
        }

    def _integration_worker_payload(self, service: object | None, *, webhooks: Sequence[object] = ()) -> dict[str, Any]:
        worker_status: dict[str, Any] = {}
        if service is not None:
            worker_status_getter = getattr(service, "get_worker_status", None)
            if callable(worker_status_getter):
                try:
                    worker_status = self._integration_worker_status_payload(worker_status_getter())
                except Exception:
                    worker_status = {}
        return {
            "mode": "local_ops_worker_surface",
            "supports_run_delivery_worker": callable(getattr(service, "run_delivery_worker", None)),
            "supports_run_delivery_daemon": callable(getattr(service, "run_delivery_daemon", None)),
            "supports_run_im_notification_worker": callable(getattr(service, "run_im_notification_worker", None)),
            "supports_run_feishu_notify_worker": callable(getattr(service, "run_feishu_notify_worker", None)),
            "supports_run_defect_sync_worker": callable(getattr(service, "run_defect_sync_worker", None)),
            "supports_run_release_sync_worker": callable(getattr(service, "run_release_sync_worker", None)),
            "supports_replay_dead_letter_api": callable(getattr(service, "replay_dead_lettered_events", None)),
            "supports_delivery_receipts": True,
            "supports_consumer_receipts": True,
            "supports_operator_receipts": True,
            "supports_replay_receipts": True,
            "worker_status": worker_status,
            "delivery_interval_seconds": getattr(service, "_delivery_interval", None) if service is not None else None,
            "retry_delay_seconds": getattr(service, "_retry_delay", None) if service is not None else None,
            "max_retry_delay_seconds": getattr(service, "_max_retry_delay", None) if service is not None else None,
            "dead_letter_threshold": getattr(service, "_dead_letter_threshold", None) if service is not None else None,
            "retry_alert_threshold": getattr(service, "_retry_alert_threshold", None) if service is not None else None,
            "registered_webhook_names": [
                str(getattr(item, "name", "") or "")
                for item in webhooks
                if str(getattr(item, "name", "") or "")
            ],
            "commands": {
                "deliver_single_round": "python -m stability.cli deliver-integration-outbox --webhook-name <name>",
                "run_worker_loop": "python -m stability.cli run-integration-outbox-worker --webhook-name <name>",
                "run_daemon_loop": "python -m stability.cli run-integration-outbox-worker --daemon --webhook-name <name>",
                "run_ci_callback_daemon": "python -m stability.cli run-ci-admission-sync-worker --webhook-name <name>",
                "register_im_webhook": "python -m stability.cli register-im-webhook --name <name> --url <https-url>",
                "run_im_notification_daemon": "python -m stability.cli run-im-notify-worker --daemon --webhook-name <name>",
                "register_feishu_webhook": "python -m stability.cli register-feishu-webhook --name <name> --url <https-url>",
                "run_feishu_notify_daemon": "python -m stability.cli run-feishu-notify-worker --daemon --webhook-name <name>",
                "show_im_acceptance_summary": "python -m stability.cli show-im-acceptance-summary --channel feishu_bot --webhook-name <name>",
                "register_defect_webhook": "python -m stability.cli register-defect-webhook --name <name> --url <https-url>",
                "run_defect_sync_daemon": "python -m stability.cli run-defect-sync-worker --daemon --webhook-name <name>",
                "register_release_webhook": "python -m stability.cli register-release-webhook --name <name> --url <https-url>",
                "run_release_sync_daemon": "python -m stability.cli run-release-sync-worker --daemon --webhook-name <name>",
                "replay_dead_letters": "python -m stability.cli replay-integration-dead-letters --execute",
            },
            "receipt_contract": "webhook_transport_ack_only_plus_operator_receipts",
        }

    def _integration_idempotency_contract_payload(self) -> dict[str, Any]:
        return {
            "strategy": "event_id_per_delivery_target",
            "idempotency_key_template": "asl.outbox.idempotency.v1:<event_id>",
            "receipt_key_template": "asl.outbox.receipt.v1:<event_id>",
            "consumer_receipt_mode": "transport_and_consumer",
            "receipt_modes": ["transport", "consumer"],
            "notes": "Current webhook chain confirms transport-level delivery, persists consumer receipts when downstream responds, and records operator/replay receipts for local ops actions.",
        }

    def _integration_callback_contract_payload(self) -> dict[str, Any]:
        return {
            "contract_version": "asl.webhook_callback.v1",
            "delivery_contract_header": "X-ASL-Delivery-Contract: asl.webhook_delivery.v1",
            "signature_headers": [
                "X-ASL-Signature",
                "X-ASL-Signature-Alg",
                "X-ASL-Signature-Key-Id",
            ],
            "routing_headers": [
                "X-ASL-Event-Id",
                "X-ASL-Event-Type",
                "X-ASL-Target-Type",
                "X-ASL-Target-Id",
                "X-ASL-Webhook-Name",
                "X-ASL-Failure-Policy",
                "X-ASL-Idempotency-Key",
            ],
            "receiver_ack_fields": [
                "receipt_id",
                "consumer_receipt_id",
                "consumer_id",
                "signature_verified",
            ],
            "security_rules": [
                "non-local webhook 必须使用 https",
                "non-local webhook 必须配置 signing_secret",
                "signature_key_id 必须稳定可追溯，轮转时 accepted_signature_key_ids 需保留旧值",
            ],
            "delivery_channels": {
                "generic": "通用 JSON webhook，适合自定义接收端。",
                "ci_callback": "CI 准入回写链路，当前以 admission_case.updated 为主。",
                "im_notify": "IM 通知链路，消息体使用 asl.im_notify.v1。",
                "feishu_bot": "飞书自定义机器人链路，消息体使用 feishu.custom_bot.v1。",
                "defect_sync": "缺陷系统同步链路，消息体使用 asl.defect_sync.v1。",
                "release_submission": "提测平台回写链路，消息体使用 asl.release_submission.v1。",
            },
            "channel_contracts": {
                "im_notify": {
                    "contract_version": "asl.im_notify.v1",
                    "message_fields": ["title", "summary", "message", "event", "original_payload"],
                },
                "feishu_bot": {
                    "contract_version": "feishu.custom_bot.v1",
                    "message_fields": ["timestamp", "sign", "msg_type", "content"],
                },
                "defect_sync": {
                    "contract_version": "asl.defect_sync.v1",
                    "message_fields": ["action", "issue", "defect", "routing", "original_payload"],
                },
                "release_submission": {
                    "contract_version": "asl.release_submission.v1",
                    "message_fields": ["action", "release_submission", "routing", "original_payload"],
                },
            },
        }

    @staticmethod
    def _integration_webhook_security_boundary(url: str) -> str:
        return "local_callback" if not WebPortalApplication._integration_webhook_requires_tls(url) else "shared_remote_callback"

    @staticmethod
    def _integration_webhook_requires_tls(url: str) -> bool:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(str(url or "").strip())
            host = str(parsed.hostname or "").strip().lower()
            if host in {"127.0.0.1", "localhost", "::1"}:
                return False
            return True
        except Exception:
            return True

    @staticmethod
    def _integration_webhook_requires_signing_secret(url: str) -> bool:
        return WebPortalApplication._integration_webhook_requires_tls(url)

    def _integration_event_payload(self, item: object) -> dict[str, Any]:
        event_id = str(getattr(item, "event_id", "") or "")
        delivery_status = str(getattr(item, "delivery_status", "") or "pending")
        receipt_status = "transport_ack" if delivery_status == "delivered" else "not_acknowledged"
        raw_consumer_receipts = getattr(item, "consumer_receipts", ()) or ()
        consumer_receipts = [
            self._integration_consumer_receipt_payload(receipt) for receipt in raw_consumer_receipts if receipt is not None
        ]
        return {
            "event_id": event_id,
            "event_type": str(getattr(item, "event_type", "") or ""),
            "target_type": str(getattr(item, "target_type", "") or ""),
            "target_id": str(getattr(item, "target_id", "") or ""),
            "created_at": self._isoformat_or_none(getattr(item, "created_at", None)),
            "created_by": str(getattr(item, "created_by", "") or ""),
            "session_source": str(getattr(item, "session_source", "") or ""),
            "audit_source": dict(getattr(item, "audit_source", {}) or {}),
            "payload": dict(getattr(item, "payload", {}) or {}),
            "delivery_status": delivery_status,
            "attempt_count": int(getattr(item, "attempt_count", 0) or 0),
            "last_attempt_at": self._isoformat_or_none(getattr(item, "last_attempt_at", None)),
            "delivered_at": self._isoformat_or_none(getattr(item, "delivered_at", None)),
            "last_error": str(getattr(item, "last_error", "") or ""),
            "next_retry_at": self._isoformat_or_none(getattr(item, "next_retry_at", None)),
            "signature": str(getattr(item, "signature", "") or ""),
            "retry_backoff_seconds": int(getattr(item, "retry_backoff_seconds", 0) or 0),
            "last_response_code": getattr(item, "last_response_code", None),
            "dead_lettered_at": self._isoformat_or_none(getattr(item, "dead_lettered_at", None)),
            "failure_category": str(getattr(item, "failure_category", "") or ""),
            "alert_status": str(getattr(item, "alert_status", "") or "none"),
            "alert_count": int(getattr(item, "alert_count", 0) or 0),
            "last_alert_at": self._isoformat_or_none(getattr(item, "last_alert_at", None)),
            "idempotency_key": str(
                getattr(item, "idempotency_key", "")
                or f"asl.outbox.idempotency.v1:{event_id}"
            ),
            "consumer_receipts": consumer_receipts,
            "consumer_receipt_count": len(consumer_receipts),
            "replay_receipts": [
                self._integration_replay_receipt_payload(receipt)
                for receipt in (getattr(item, "replay_receipts", ()) or ())
                if receipt is not None
            ],
            "replay_receipt_count": len(getattr(item, "replay_receipts", ()) or ()),
            "operator_receipts": [
                self._integration_operator_receipt_payload(receipt)
                for receipt in (getattr(item, "operator_receipts", ()) or ())
                if receipt is not None
            ],
            "operator_receipt_count": len(getattr(item, "operator_receipts", ()) or ()),
            "delivery_receipt": {
                "receipt_key": f"asl.outbox.receipt.v1:{event_id}",
                "receipt_status": receipt_status,
                "contract": "webhook_transport_ack_only_plus_operator_receipts",
                "delivered_at": self._isoformat_or_none(getattr(item, "delivered_at", None)),
            },
        }

    def _integration_worker_status_payload(self, item: object) -> dict[str, Any]:
        return {
            "worker_name": str(getattr(item, "worker_name", "") or ""),
            "status": str(getattr(item, "status", "") or ""),
            "worker_mode": str(getattr(item, "worker_mode", "") or ""),
            "daemon_enabled": bool(getattr(item, "daemon_enabled", False)),
            "daemon_pid": getattr(item, "daemon_pid", None),
            "daemon_heartbeat_at": self._isoformat_or_none(getattr(item, "daemon_heartbeat_at", None)),
            "last_started_at": self._isoformat_or_none(getattr(item, "last_started_at", None)),
            "last_finished_at": self._isoformat_or_none(getattr(item, "last_finished_at", None)),
            "last_success_at": self._isoformat_or_none(getattr(item, "last_success_at", None)),
            "last_error": str(getattr(item, "last_error", "") or ""),
            "run_count": int(getattr(item, "run_count", 0) or 0),
            "delivered_count": int(getattr(item, "delivered_count", 0) or 0),
            "failed_count": int(getattr(item, "failed_count", 0) or 0),
            "replay_count": int(getattr(item, "replay_count", 0) or 0),
            "configured_webhooks": list(getattr(item, "configured_webhooks", ()) or ()),
            "configured_event_types": list(getattr(item, "configured_event_types", ()) or ()),
            "schedule_interval_seconds": int(getattr(item, "schedule_interval_seconds", 0) or 0),
            "chain_name": str(getattr(item, "chain_name", "") or ""),
            "last_delivery_receipt_id": str(getattr(item, "last_delivery_receipt_id", "") or ""),
            "last_operator_receipt_id": str(getattr(item, "last_operator_receipt_id", "") or ""),
            "last_run_summary": dict(getattr(item, "last_run_summary", {}) or {}),
        }

    @staticmethod
    def _integration_consumer_receipt_payload(item: object) -> dict[str, Any]:
        return {
            "receipt_id": str(getattr(item, "receipt_id", "") or ""),
            "event_id": str(getattr(item, "event_id", "") or ""),
            "webhook_name": str(getattr(item, "webhook_name", "") or ""),
            "idempotency_key": str(getattr(item, "idempotency_key", "") or ""),
            "received_at": WebPortalApplication._isoformat_or_none(getattr(item, "received_at", None)),
            "status": str(getattr(item, "status", "") or "delivered"),
            "response_code": getattr(item, "response_code", None),
            "consumer_id": str(getattr(item, "consumer_id", "") or ""),
            "consumer_receipt_id": str(getattr(item, "consumer_receipt_id", "") or ""),
            "response_excerpt": str(getattr(item, "response_excerpt", "") or ""),
            "receipt_key": f"asl.outbox.consumer_receipt.v1:{str(getattr(item, 'event_id', '') or '')}:{str(getattr(item, 'receipt_id', '') or '')}",
        }

    @staticmethod
    def _integration_replay_receipt_payload(item: object) -> dict[str, Any]:
        return {
            "receipt_id": str(getattr(item, "receipt_id", "") or ""),
            "event_id": str(getattr(item, "event_id", "") or ""),
            "webhook_name": str(getattr(item, "webhook_name", "") or ""),
            "idempotency_key": str(getattr(item, "idempotency_key", "") or ""),
            "replayed_at": WebPortalApplication._isoformat_or_none(getattr(item, "replayed_at", None)),
            "replayed_by": str(getattr(item, "replayed_by", "") or ""),
            "status": str(getattr(item, "status", "") or ""),
            "replay_token": str(getattr(item, "replay_token", "") or ""),
            "notes": str(getattr(item, "notes", "") or ""),
            "receipt_key": f"asl.outbox.replay_receipt.v1:{str(getattr(item, 'event_id', '') or '')}:{str(getattr(item, 'receipt_id', '') or '')}",
        }

    @staticmethod
    def _integration_operator_receipt_payload(item: object) -> dict[str, Any]:
        return {
            "receipt_id": str(getattr(item, "receipt_id", "") or ""),
            "event_id": str(getattr(item, "event_id", "") or ""),
            "webhook_name": str(getattr(item, "webhook_name", "") or ""),
            "action": str(getattr(item, "action", "") or ""),
            "operator_id": str(getattr(item, "operator_id", "") or ""),
            "recorded_at": WebPortalApplication._isoformat_or_none(getattr(item, "recorded_at", None)),
            "status": str(getattr(item, "status", "") or ""),
            "session_source": str(getattr(item, "session_source", "") or ""),
            "audit_source": dict(getattr(item, "audit_source", {}) or {}),
            "notes": str(getattr(item, "notes", "") or ""),
            "receipt_key": f"asl.outbox.operator_receipt.v1:{str(getattr(item, 'event_id', '') or '')}:{str(getattr(item, 'receipt_id', '') or '')}",
        }
