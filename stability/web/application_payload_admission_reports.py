from __future__ import annotations

from .application_common import *
from stability.time_utils import now_beijing_string


def _generated_at_now() -> str:
    return now_beijing_string()


class ApplicationPayloadAdmissionReportsMixin:
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
        baseline_key = str(
            case.get("baseline_key", "")
            or gate.get("baseline_key", "")
            or baseline.get("baseline_key", "")
            or ""
        )
        report_id = str(case.get("report_id", "") or gate.get("report_id", "") or baseline.get("report_id", "") or "")
        report_name = str(
            case.get("report_name", "") or gate.get("report_name", "") or baseline.get("report_name", "") or ""
        )
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
                        dict(
                            dict(getattr(latest_audit, "summary", {}) or {}).get("current_report_golden_suite", {})
                            or {}
                        )
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
