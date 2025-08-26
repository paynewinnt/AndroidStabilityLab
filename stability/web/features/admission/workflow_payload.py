from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import quote

from stability.time_utils import now_beijing_string

from .payload_core import AdmissionPayloadMixin


def _generated_at_now() -> str:
    return now_beijing_string()


class AdmissionWorkflowPayloadMixin(AdmissionPayloadMixin):
    def _issues_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        limit = self._int_query(query, "limit", default=30)
        actors = self._collaboration_actors()
        issues = self._issue_summaries(limit=limit)
        current_actor = self._current_actor_payload(request_context=request_context, query=query)
        for item in issues:
            item["current_actor"] = dict(current_actor)
        severity_counts: dict[str, int] = {}
        issue_type_counts: dict[str, int] = {}
        state_counts: dict[str, int] = {}
        for item in issues:
            severity = str(item.get("severity", "") or "unknown")
            issue_type = str(item.get("issue_type", "") or "unknown")
            workflow_state = str(item.get("workflow_state", "") or "new")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            issue_type_counts[issue_type] = issue_type_counts.get(issue_type, 0) + 1
            state_counts[workflow_state] = state_counts.get(workflow_state, 0) + 1
        return {
            "page": "issues",
            "title": "问题中心",
            "generated_at": _generated_at_now(),
            "current_actor": current_actor,
            "summary": {
                "issue_count": len(issues),
                "severity_counts": severity_counts,
                "issue_type_counts": issue_type_counts,
                "state_counts": state_counts,
                "actor_count": len(actors),
            },
            "actors": actors,
            "issues": issues,
        }

    def _goldens_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "rule_replay_golden_suite_service", None)
        if service is None:
            raise ValueError("Rule replay golden suite service is unavailable.")
        limit = self._int_query(query, "limit", default=50)
        suite_path = self._str_query(query, "suite_path")
        issue_type = self._str_query(query, "issue_type")
        layer = self._str_query(query, "layer")
        expectation = self._str_query(query, "expectation")
        result = service.list_cases(
            suite_path=suite_path,
            issue_type=issue_type,
            layer=layer,
            expectation=expectation,
            limit=limit,
        )
        return {
            "page": "goldens",
            "title": "Golden Suite",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "suite_path": getattr(result, "suite_path", ""),
            "suite_version": getattr(result, "suite_version", ""),
            "summary": {
                "case_count": int(getattr(result, "case_count", 0) or 0),
                "layer_count": len(dict(getattr(result, "layer_counts", {}) or {})),
                "issue_type_count": len(dict(getattr(result, "issue_type_counts", {}) or {})),
                "expectation_count": len(dict(getattr(result, "expectation_counts", {}) or {})),
                "layer_counts": dict(getattr(result, "layer_counts", {}) or {}),
                "issue_type_counts": dict(getattr(result, "issue_type_counts", {}) or {}),
                "expectation_counts": dict(getattr(result, "expectation_counts", {}) or {}),
            },
            "filters": dict(getattr(result, "filters", {}) or {}),
            "cases": [
                {
                    "case_id": getattr(item, "case_id", ""),
                    "description": getattr(item, "description", ""),
                    "issue_type": getattr(item, "issue_type", ""),
                    "layer": getattr(item, "layer", ""),
                    "expectation": getattr(item, "expectation", ""),
                    "include_unchanged": bool(getattr(item, "include_unchanged", False)),
                    "issue_count": int(getattr(item, "issue_count", 0) or 0),
                    "package_name": getattr(item, "package_name", ""),
                    "template_type": getattr(item, "template_type", ""),
                    "source_run_id": getattr(item, "source_run_id", ""),
                }
                for item in (getattr(result, "cases", ()) or ())
            ],
        }

    def _golden_diff_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "rule_replay_golden_suite_service", None)
        if service is None:
            raise ValueError("Rule replay golden suite service is unavailable.")
        left_path = self._str_query(query, "left_path") or "config/rule_replay_golden_samples.json"
        right_path = self._str_query(query, "right_path")
        include_unchanged = self._bool_query(query, "include_unchanged", default=False)
        change_type = self._str_query(query, "change_type")
        changed_field = self._str_query(query, "changed_field")
        case_query = self._str_query(query, "case_query")
        case_ids = [str(item).strip() for item in query.get("case_id", []) if str(item).strip()]
        if not right_path:
            return {
                "page": "golden_diff",
                "title": "Golden Suite Diff",
                "generated_at": _generated_at_now(),
                "comparison_ready": False,
                "left_path": left_path,
                "right_path": "",
                "left_suite_version": "",
                "right_suite_version": "",
                "filters": {
                    "case_ids": case_ids,
                    "include_unchanged": include_unchanged,
                    "change_type": change_type,
                    "changed_field": changed_field,
                    "case_query": case_query,
                    "available_change_types": [],
                    "available_changed_fields": [],
                },
                "summary": {"diff_count": 0, "total_diff_count": 0, "change_counts": {}, "total_change_counts": {}},
                "entries": [],
                "help": {
                    "message": "请在 URL 后追加 right_path，再打开这页做只读 diff。",
                    "example": "/goldens/diff?left_path=config/rule_replay_golden_samples.json&right_path=/tmp/other_golden_suite.json",
                },
            }
        result = service.diff_suites(
            left_path=left_path,
            right_path=right_path,
            case_ids=tuple(case_ids),
            include_unchanged=include_unchanged,
        )
        entries = []
        for entry in (getattr(result, "entries", ()) or ()):
            case_id = str(getattr(entry, "case_id", "") or "")
            left_case = dict(getattr(entry, "left_case", {}) or {})
            right_case = dict(getattr(entry, "right_case", {}) or {})
            entries.append(
                {
                    "case_id": case_id,
                    "change_type": str(getattr(entry, "change_type", "") or ""),
                    "changed_fields": list(getattr(entry, "changed_fields", ()) or ()),
                    "left_case": left_case,
                    "right_case": right_case,
                    "field_diff_summary": self._golden_diff_field_summary(
                        left_case=left_case,
                        right_case=right_case,
                        change_type=str(getattr(entry, "change_type", "") or ""),
                        changed_fields=list(getattr(entry, "changed_fields", ()) or ()),
                    ),
                    "block_diff_summary": self._golden_diff_block_summary(left_case=left_case, right_case=right_case),
                    "left_case_link": (
                        f"/goldens/case/{quote(case_id, safe='')}?suite_path={quote(str(getattr(result, 'left_path', '') or ''), safe='')}"
                        if left_case
                        else ""
                    ),
                    "right_case_link": (
                        f"/goldens/case/{quote(case_id, safe='')}?suite_path={quote(str(getattr(result, 'right_path', '') or ''), safe='')}"
                        if right_case
                        else ""
                    ),
                }
            )
        available_change_types = sorted(
            {
                str(item.get("change_type", "") or "")
                for item in entries
                if str(item.get("change_type", "") or "").strip()
            }
        )
        available_changed_fields = sorted(
            {
                str(field)
                for item in entries
                for field in list(item.get("changed_fields", []) or [])
                if str(field).strip()
            }
        )
        filtered_entries = self._filter_golden_diff_entries(
            entries,
            change_type=change_type,
            changed_field=changed_field,
            case_query=case_query,
        )
        filtered_change_counts: dict[str, int] = {}
        for item in filtered_entries:
            key = str(item.get("change_type", "") or "unknown")
            filtered_change_counts[key] = filtered_change_counts.get(key, 0) + 1
        return {
            "page": "golden_diff",
            "title": "Golden Suite Diff",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "comparison_ready": True,
            "left_path": getattr(result, "left_path", ""),
            "right_path": getattr(result, "right_path", ""),
            "left_suite_version": getattr(result, "left_suite_version", ""),
            "right_suite_version": getattr(result, "right_suite_version", ""),
            "filters": {
                "case_ids": case_ids,
                "include_unchanged": include_unchanged,
                "change_type": change_type,
                "changed_field": changed_field,
                "case_query": case_query,
                "available_change_types": available_change_types,
                "available_changed_fields": available_changed_fields,
            },
            "summary": {
                "diff_count": len(filtered_entries),
                "total_diff_count": int(getattr(result, "diff_count", 0) or 0),
                "change_counts": filtered_change_counts,
                "total_change_counts": dict(getattr(result, "change_counts", {}) or {}),
            },
            "entries": filtered_entries,
            "help": {"message": "", "example": ""},
        }

    def _admission_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        limit = self._int_query(query, "limit", default=20)
        baselines = self._baseline_summaries(limit=limit)
        auto_decision_counts: dict[str, int] = {}
        final_decision_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        action_counts: dict[str, int] = {}
        override_count = 0
        risk_baseline_count = 0
        performance_risk_baseline_count = 0
        coverage_gap_baseline_count = 0
        golden_suite_baseline_count = 0
        golden_suite_failed_baseline_count = 0
        golden_suite_case_count_total = 0
        golden_suite_failed_case_count_total = 0
        for baseline in baselines:
            admission_case = dict(baseline.get("admission_case", {}) or {})
            evidence = dict(baseline.get("evidence", {}) or {})
            quality_gate = dict(evidence.get("quality_gate", {}) or {})
            auto_decision = str(quality_gate.get("automatic_decision", "") or "")
            if auto_decision:
                auto_decision_counts[auto_decision] = auto_decision_counts.get(auto_decision, 0) + 1
            final_decision = str(admission_case.get("final_decision", "") or "")
            if final_decision:
                final_decision_counts[final_decision] = final_decision_counts.get(final_decision, 0) + 1
            case_status = str(admission_case.get("status", "") or "")
            if case_status:
                status_counts[case_status] = status_counts.get(case_status, 0) + 1
            rule_review = dict(evidence.get("rule_review_report", {}) or {})
            latest_summary = dict(rule_review.get("latest_audit_summary", {}) or {})
            for action, count in dict(latest_summary.get("action_counts", {}) or {}).items():
                action_counts[str(action)] = action_counts.get(str(action), 0) + int(count or 0)
            if quality_gate.get("has_override"):
                override_count += 1
            if int(quality_gate.get("risk_count", 0) or 0) > 0:
                risk_baseline_count += 1
            if int(quality_gate.get("performance_risk_count", admission_case.get("performance_risk_count", 0)) or 0) > 0:
                performance_risk_baseline_count += 1
            if int(quality_gate.get("coverage_gap_count", 0) or 0) > 0:
                coverage_gap_baseline_count += 1
            golden_suite = dict(evidence.get("golden_suite", {}) or {})
            if golden_suite:
                golden_suite_baseline_count += 1
                failed_case_count = int(golden_suite.get("failed_case_count_total", 0) or 0)
                golden_suite_case_count_total += int(golden_suite.get("case_count_total", 0) or 0)
                golden_suite_failed_case_count_total += failed_case_count
                if failed_case_count > 0:
                    golden_suite_failed_baseline_count += 1
        current_actor = self._current_actor_payload(request_context=request_context, query=query)
        return {
            "page": "admission",
            "title": "准入中心",
            "generated_at": _generated_at_now(),
            "current_actor": current_actor,
            "actors": self._collaboration_actors(),
            "summary": {
                "baseline_count": len(baselines),
                "auto_decision_counts": auto_decision_counts,
                "final_decision_counts": final_decision_counts,
                "status_counts": status_counts,
                "override_count": override_count,
                "risk_baseline_count": risk_baseline_count,
                "performance_risk_baseline_count": performance_risk_baseline_count,
                "coverage_gap_baseline_count": coverage_gap_baseline_count,
                "action_counts": action_counts,
                "golden_suite_baseline_count": golden_suite_baseline_count,
                "golden_suite_failed_baseline_count": golden_suite_failed_baseline_count,
                "golden_suite_case_count_total": golden_suite_case_count_total,
                "golden_suite_failed_case_count_total": golden_suite_failed_case_count_total,
            },
            "baselines": baselines,
            "views": self._admission_view_groups(
                items=[self._admission_summary_view_entry(item) for item in baselines],
                current_actor=current_actor,
            ),
        }

    @staticmethod
    def _admission_summary_view_entry(item: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(item or {})
        case = dict(payload.get("admission_case", {}) or {})
        evidence = dict(payload.get("evidence", {}) or {})
        gate = dict(evidence.get("quality_gate", {}) or {})
        return {
            **payload,
            **case,
            "automatic_decision": gate.get("automatic_decision", ""),
            "has_override": gate.get("has_override", False),
            "risk_count": gate.get("risk_count", 0),
            "triggered_rule_count": gate.get("triggered_rule_count", 0),
            "coverage_gap_count": gate.get("coverage_gap_count", 0),
            "performance_risk_count": gate.get("performance_risk_count", case.get("performance_risk_count", 0)),
        }

    def _admission_latest_audit_payload(self, latest_audit: object) -> dict[str, Any]:
        return {
            "audit_id": getattr(latest_audit, "audit_id", ""),
            "audit_name": getattr(latest_audit, "audit_name", ""),
            "created_at": self._isoformat_or_none(getattr(latest_audit, "created_at", None)),
            "created_by": getattr(latest_audit, "created_by", ""),
            "summary": dict(getattr(latest_audit, "summary", {}) or {}),
            "retention": dict(getattr(latest_audit, "retention", {}) or {}),
            "version_count": int(getattr(latest_audit, "version_count", 0) or 0),
            "versions": [
                {
                    "revision_id": version.revision_id,
                    "action": version.action,
                    "changed_at": self._isoformat_or_none(version.changed_at),
                    "changed_by": version.changed_by,
                    "report_id": version.report_id,
                    "report_name": version.report_name,
                    "audit_id": getattr(version, "audit_id", ""),
                    "summary": dict(getattr(version, "summary", {}) or {}),
                    "detail_path": getattr(version, "detail_path", ""),
                    "markdown_path": getattr(version, "markdown_path", ""),
                    "html_path": getattr(version, "html_path", ""),
                }
                for version in (getattr(latest_audit, "versions", ()) or ())
            ],
            "detail_path": getattr(latest_audit, "detail_path", ""),
            "markdown_path": getattr(latest_audit, "markdown_path", ""),
            "html_path": getattr(latest_audit, "html_path", ""),
            "index_path": getattr(latest_audit, "index_path", ""),
        }

    def _baseline_detail_payload(
        self,
        baseline_key: str,
        *,
        query: dict[str, list[str]] | None = None,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = baseline_key.strip()
        service = getattr(self._bundle, "rule_review_report_service", None)
        if service is None:
            raise ValueError("Rule review report service is unavailable.")
        baseline = service.get_baseline(key)
        latest_audit = None
        latest_audit_error = ""
        try:
            latest_audit = service.show_latest_baseline_audit(baseline_key=key, version_limit=10)
        except ValueError as exc:
            latest_audit_error = str(exc)
        report = service.get_report(getattr(baseline, "report_id", ""))
        history = list(service.list_baseline_history(key)) if hasattr(service, "list_baseline_history") else []
        action_filter = self._str_query(query or {}, "action")
        comparison_only = self._bool_query(query or {}, "comparison_only", default=False)
        filtered_history = self._filter_baseline_history(history, action=action_filter, comparison_only=comparison_only)
        report_summary = dict(getattr(report, "summary", {}) or {})
        comparison_reports = self._comparison_report_links(filtered_history)
        golden_suite = (
            dict(report_summary.get("current_report_golden_suite", {}) or {})
            or dict(report_summary.get("golden_suite", {}) or {})
            or dict(dict(getattr(latest_audit, "summary", {}) or {}).get("current_report_golden_suite", {}) or {})
        )
        quality_gate = self._quality_gate_detail_payload(key)
        admission_case = self._admission_case_detail_payload(key)
        admission_case["current_actor"] = self._current_actor_payload(request_context=request_context, query=query or {})
        formal_report = self._admission_report_payload(key)
        evidence = {
            "quality_gate": quality_gate,
            "rule_review_report": {
                "baseline": {
                    "baseline_key": baseline.baseline_key,
                    "report_id": baseline.report_id,
                    "report_name": baseline.report_name,
                    "policy_versions": list(baseline.policy_versions),
                    "candidate_paths": list(baseline.candidate_paths),
                    "baseline_paths": list(baseline.baseline_paths),
                    "latest_audit_version_count": baseline.latest_audit_version_count,
                },
                "report": {
                    "report_id": getattr(report, "report_id", ""),
                    "name": getattr(report, "name", ""),
                    "summary": report_summary,
                    "detail_path": getattr(report, "detail_path", ""),
                    "markdown_path": getattr(report, "markdown_path", ""),
                    "html_path": getattr(report, "html_path", ""),
                },
                "latest_audit": self._admission_latest_audit_payload(latest_audit),
            },
            "golden_suite": golden_suite,
            "regression": dict(admission_case.get("regression_summary", {}) or {}),
        }
        current_actor = self._current_actor_payload(request_context=request_context, query=query or {})
        return {
            "page": "admission_detail",
            "title": f"准入详情 | {key}",
            "generated_at": _generated_at_now(),
            "current_actor": current_actor,
            "actors": self._collaboration_actors(),
            "latest_audit_error": latest_audit_error,
            "filters": {
                "action": action_filter,
                "comparison_only": comparison_only,
                "available_actions": sorted(
                    {
                        str(getattr(entry, "action", "") or "")
                        for entry in history
                        if str(getattr(entry, "action", "") or "").strip()
                    }
                ),
                "history_count_total": len(history),
                "history_count_filtered": len(filtered_history),
            },
            "admission_case": admission_case,
            "formal_report": formal_report,
            "evidence": evidence,
            "legacy_detail": dict(evidence),
            "baseline": {
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
            },
            "report": {
                "report_id": getattr(report, "report_id", ""),
                "name": getattr(report, "name", ""),
                "created_at": self._isoformat_or_none(getattr(report, "created_at", None)),
                "created_by": getattr(report, "created_by", ""),
                "summary": report_summary,
                "detail_path": getattr(report, "detail_path", ""),
                "markdown_path": getattr(report, "markdown_path", ""),
                "html_path": getattr(report, "html_path", ""),
            },
            "comparison_reports": comparison_reports,
            "status_summary": self._baseline_status_summary(
                report={
                    "detail_path": getattr(report, "detail_path", ""),
                    "markdown_path": getattr(report, "markdown_path", ""),
                    "html_path": getattr(report, "html_path", ""),
                },
                comparison_reports=comparison_reports,
                latest_audit={
                    "detail_path": getattr(latest_audit, "detail_path", ""),
                    "markdown_path": getattr(latest_audit, "markdown_path", ""),
                    "html_path": getattr(latest_audit, "html_path", ""),
                },
                golden_suite=golden_suite,
            ),
            "status_actions": self._baseline_status_actions(
                self._baseline_status_summary(
                    report={
                        "detail_path": getattr(report, "detail_path", ""),
                        "markdown_path": getattr(report, "markdown_path", ""),
                        "html_path": getattr(report, "html_path", ""),
                    },
                    comparison_reports=comparison_reports,
                    latest_audit={
                        "detail_path": getattr(latest_audit, "detail_path", ""),
                        "markdown_path": getattr(latest_audit, "markdown_path", ""),
                        "html_path": getattr(latest_audit, "html_path", ""),
                    },
                    golden_suite=golden_suite,
                )
            ),
            "baseline_history": [
                {
                    "revision_id": str(getattr(entry, "revision_id", "") or ""),
                    "report_id": str(getattr(entry, "report_id", "") or ""),
                    "report_name": str(getattr(entry, "report_name", "") or ""),
                    "changed_at": self._isoformat_or_none(getattr(entry, "changed_at", None)),
                    "changed_by": str(getattr(entry, "changed_by", "") or ""),
                    "action": str(getattr(entry, "action", "") or ""),
                    "reasons": list(getattr(entry, "reasons", ()) or ()),
                    "comparison_id": str(getattr(entry, "comparison_id", "") or ""),
                    "comparison_detail_path": str(getattr(entry, "comparison_detail_path", "") or ""),
                    "policy_version": str(getattr(entry, "policy_version", "") or ""),
                }
                for entry in filtered_history
            ],
            "latest_audit": self._admission_latest_audit_payload(latest_audit),
        }

    def _golden_case_detail_payload(
        self,
        case_id: str,
        *,
        query: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "rule_replay_golden_suite_service", None)
        if service is None:
            raise ValueError("Rule replay golden suite service is unavailable.")
        suite_path = self._str_query(query or {}, "suite_path")
        result = service.get_case(case_id=case_id.strip(), suite_path=suite_path)
        payload = dict(getattr(result, "payload", {}) or {})
        summary = getattr(result, "summary", object())
        return {
            "page": "golden_case_detail",
            "title": f"Golden Case | {getattr(summary, 'case_id', '')}",
            "generated_at": _generated_at_now(),
            "suite_path": getattr(result, "suite_path", ""),
            "suite_version": getattr(result, "suite_version", ""),
            "summary": {
                "case_id": getattr(summary, "case_id", ""),
                "description": getattr(summary, "description", ""),
                "issue_type": getattr(summary, "issue_type", ""),
                "layer": getattr(summary, "layer", ""),
                "expectation": getattr(summary, "expectation", ""),
                "include_unchanged": bool(getattr(summary, "include_unchanged", False)),
                "issue_count": int(getattr(summary, "issue_count", 0) or 0),
                "package_name": getattr(summary, "package_name", ""),
                "template_type": getattr(summary, "template_type", ""),
                "source_run_id": getattr(summary, "source_run_id", ""),
            },
            "payload": payload,
            "baseline_rules": dict(payload.get("baseline_rules", {}) or {}),
            "candidate_rules": dict(payload.get("candidate_rules", {}) or {}),
            "filters": dict(payload.get("filters", {}) or {}),
            "dataset": dict(payload.get("dataset", {}) or {}),
            "expected": dict(payload.get("expected", {}) or {}),
            "draft_metadata": dict(payload.get("draft_metadata", {}) or {}),
        }
