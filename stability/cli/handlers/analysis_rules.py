from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from collections.abc import Iterable
from typing import Any, Mapping, Sequence

from stability import create_v1_bootstrap, create_v1_persistent_bootstrap
from stability.app import (
    AggregatedIssueNotFound,
    DeviceRecordNotFound,
    RunRecordNotFound,
    SnapshotRecordNotFound,
    UnattendedPatrolRunnerAlreadyRunning,
    UnattendedTaskRecordNotFound,
)
from stability.app.task_service import TaskRecordNotFound
from stability.domain import (
    AggregatedIssue,
    AnalysisSnapshotRecord,
    AnalysisSnapshotSummary,
    ComparedMetricTrend,
    ComparedIssue,
    ComparisonResult,
    IssueEventReference,
    IssueAttribution,
    MetricTrendSummary,
    PerformanceTrendComparison,
    RegressedIssue,
    RegressedMetric,
    RegressionResult,
    SamplingConfig,
    TaskDefinition,
    TaskRunStatus,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.cli.handlers.web import handle_serve_web as _web_handle_serve_web
from stability.web import serve_web_portal

# Split from stability.cli.task_create; analysis.py owns this command/payload group.

# Split from stability/cli/handlers/analysis.py.

def _handle_show_analysis_rules(args: argparse.Namespace) -> int:
    """Show effective analysis rules and the current source file payload."""
    bundle = create_v1_persistent_bootstrap()
    path_override = args.path.strip() or None
    result = bundle.rule_governance_service.inspect_rules(path_override)
    payload = {
        "storage_mode": "persistent",
        "rules": _rule_inspection_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_describe_rule_entrypoint(args: argparse.Namespace) -> int:
    """Describe the formal rule configuration entrypoint for CLI/API users."""
    bundle = create_v1_persistent_bootstrap()
    path_override = args.path.strip() or None
    service = bundle.rule_governance_service
    payload = {
        "storage_mode": "persistent",
        "rule_entrypoint": _describe_rule_entrypoint_payload(service, path_override=path_override),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_preview_analysis_rule_update(args: argparse.Namespace) -> int:
    """Preview an analysis rule update without writing the underlying config file."""
    bundle = create_v1_persistent_bootstrap()
    path_override = args.path.strip() or None
    updates = _parse_key_value_overrides(args.updates)
    service = bundle.rule_governance_service
    payload = {
        "storage_mode": "persistent",
        "rule_update_preview": _preview_analysis_rule_update_payload(
            service,
            path_override=path_override,
            updates=updates,
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_save_analysis_rule_candidate(args: argparse.Namespace) -> int:
    """Persist one candidate rule change for approval and publication."""
    bundle = create_v1_persistent_bootstrap()
    updates = _parse_key_value_overrides(args.updates)
    edit_request = _rule_update_edit_request(updates)
    try:
        result = bundle.rule_governance_service.save_rule_change_candidate(
            edit_request["patch"],
            path=args.path.strip() or None,
            created_by=args.created_by.strip(),
            title=args.title.strip(),
            reason=args.reason.strip(),
            required_approvals=args.required_approvals,
        )
    except (PermissionError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "candidate": _jsonable_mapping(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_analysis_rule_candidates(args: argparse.Namespace) -> int:
    """List persisted candidate rule changes."""
    bundle = create_v1_persistent_bootstrap()
    result = bundle.rule_governance_service.list_rule_change_candidates(
        path=args.path.strip() or None,
        status=args.status.strip(),
        limit=args.limit,
    )
    payload = {
        "storage_mode": "persistent",
        "candidate_count": len(result),
        "candidates": [_jsonable_mapping(item) for item in result],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_approve_analysis_rule_candidate(args: argparse.Namespace) -> int:
    """Approve or reject one persisted candidate rule change."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_governance_service.approve_rule_change_candidate(
            candidate_id=args.candidate_id.strip(),
            actor_id=args.actor_id.strip(),
            decision=args.decision.strip(),
            comment=args.comment.strip(),
            path=args.path.strip() or None,
        )
    except (PermissionError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "candidate": _jsonable_mapping(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_publish_analysis_rule_candidate(args: argparse.Namespace) -> int:
    """Publish an approved candidate into the active analysis-rule file."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_governance_service.publish_rule_change_candidate(
            candidate_id=args.candidate_id.strip(),
            published_by=args.published_by.strip(),
            path=args.path.strip() or None,
        )
    except (PermissionError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "version": _jsonable_mapping(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_analysis_rule_versions(args: argparse.Namespace) -> int:
    """List published rule versions."""
    bundle = create_v1_persistent_bootstrap()
    result = bundle.rule_governance_service.list_rule_versions(
        path=args.path.strip() or None,
        limit=args.limit,
    )
    payload = {
        "storage_mode": "persistent",
        "version_count": len(result),
        "versions": [_jsonable_mapping(item) for item in result],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_rollback_analysis_rule_version(args: argparse.Namespace) -> int:
    """Roll the active analysis rules back using one published version record."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_governance_service.rollback_rule_version(
            version_id=args.version_id.strip(),
            rolled_back_by=args.rolled_back_by.strip(),
            path=args.path.strip() or None,
        )
    except (PermissionError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "rollback": _jsonable_mapping(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_bind_analysis_rule_permission(args: argparse.Namespace) -> int:
    """Bind one actor to a rule-governance role or explicit permission set."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_governance_service.bind_rule_permission(
            actor_id=args.actor_id.strip(),
            role=args.role.strip(),
            permissions=tuple(args.permission or ()),
            bound_by=args.bound_by.strip(),
            path=args.path.strip() or None,
        )
    except (PermissionError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "permission": _jsonable_mapping(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_analysis_rule_permissions(args: argparse.Namespace) -> int:
    """List actor permission bindings for rule governance."""
    bundle = create_v1_persistent_bootstrap()
    result = bundle.rule_governance_service.list_rule_permission_bindings(path=args.path.strip() or None)
    payload = {
        "storage_mode": "persistent",
        "permission_count": len(result),
        "permissions": [_jsonable_mapping(item) for item in result],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_validate_analysis_rules(args: argparse.Namespace) -> int:
    """Validate one analysis rule file and return structured findings."""
    bundle = create_v1_persistent_bootstrap()
    path_override = args.path.strip() or None
    result = bundle.rule_governance_service.validate_rules(path_override)
    payload = {
        "storage_mode": "persistent",
        "validation": _rule_validation_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.valid else 1


def _handle_export_analysis_rules(args: argparse.Namespace) -> int:
    """Export the effective analysis rule bundle into one JSON file."""
    bundle = create_v1_persistent_bootstrap()
    path_override = args.path.strip() or None
    try:
        result = bundle.rule_governance_service.export_effective_rules(
            args.output.strip(),
            path=path_override,
            overwrite=args.overwrite,
        )
    except FileExistsError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "export": {
            "source_path": result.source_path,
            "output_path": result.output_path,
            "bytes_written": result.bytes_written,
            "rule_versions": dict(result.rule_versions),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_diff_analysis_rules(args: argparse.Namespace) -> int:
    """Diff two rule views and return field-level changes."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_governance_service.diff_rules(
            left_path=args.left_path.strip() or None,
            right_path=args.right_path.strip() or None,
            left_view=args.left_view.strip(),
            right_view=args.right_view.strip(),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "diff": {
            "left_label": result.left_label,
            "right_label": result.right_label,
            "left_path": result.left_path,
            "right_path": result.right_path,
            "left_validation": _rule_validation_payload(result.left_validation),
            "right_validation": _rule_validation_payload(result.right_validation),
            "diff_count": result.diff_count,
            "diffs": [_rule_diff_payload(item) for item in result.diffs],
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_prune_analysis_snapshots(args: argparse.Namespace) -> int:
    """Preview or execute one snapshot retention policy."""
    bundle = create_v1_persistent_bootstrap()
    try:
        if args.execute:
            result = bundle.snapshot_service.apply_retention(
                snapshot_type=args.snapshot_type.strip(),
                created_by=args.created_by.strip(),
                max_count=args.max_count,
                max_age_days=args.max_age_days,
            )
            payload = {
                "storage_mode": "persistent",
                "retention": {
                    "mode": "execute",
                    **result,
                },
            }
        else:
            result = bundle.snapshot_service.plan_retention(
                snapshot_type=args.snapshot_type.strip(),
                created_by=args.created_by.strip(),
                max_count=args.max_count,
                max_age_days=args.max_age_days,
            )
            payload = {
                "storage_mode": "persistent",
                "retention": {
                    "mode": "preview",
                    **result,
                },
            }
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_replay_analysis_rules(args: argparse.Namespace) -> int:
    """Replay one Top Issue query under two rule files and diff the results."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_replay_service.replay_top_issues(
            baseline_path=args.baseline_path.strip(),
            candidate_path=args.candidate_path.strip(),
            task_id=args.task_id.strip(),
            run_status=args.status.strip(),
            template_type=args.template_type.strip(),
            version=args.version.strip(),
            package_name=args.package_name.strip(),
            device_id=args.device_id.strip(),
            issue_type=args.issue_type.strip(),
            created_from=args.created_from.strip(),
            created_to=args.created_to.strip(),
            limit=args.limit,
            include_unchanged=args.include_unchanged,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "replay": _rule_replay_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_verify_rule_replay_golden_samples(args: argparse.Namespace) -> int:
    """Run the deterministic replay golden suite and print a validation summary."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_replay_acceptance_service.verify_golden_suite(
            suite_path=args.suite_path.strip(),
            case_ids=tuple(args.case_id or ()),
            fail_fast=args.fail_fast,
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "file_backed",
        "replay_golden_suite": _rule_replay_golden_suite_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_rule_replay_golden_samples(args: argparse.Namespace) -> int:
    """List one golden suite with simple filters and counters."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_replay_golden_suite_service.list_cases(
            suite_path=args.suite_path.strip(),
            case_ids=tuple(args.case_id or ()),
            issue_type=args.issue_type.strip(),
            layer=args.layer.strip(),
            expectation=args.expectation.strip(),
            limit=args.limit,
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "file_backed",
        "golden_suite": _rule_replay_golden_suite_listing_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_rule_replay_golden_sample(args: argparse.Namespace) -> int:
    """Show one golden suite case in full."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_replay_golden_suite_service.get_case(
            case_id=args.case_id.strip(),
            suite_path=args.suite_path.strip(),
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "file_backed",
        "golden_case": _rule_replay_golden_case_detail_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_diff_rule_replay_golden_samples(args: argparse.Namespace) -> int:
    """Diff two golden suite files by case id."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_replay_golden_suite_service.diff_suites(
            left_path=args.left_path.strip(),
            right_path=args.right_path.strip(),
            case_ids=tuple(args.case_id or ()),
            include_unchanged=args.include_unchanged,
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "file_backed",
        "golden_suite_diff": _rule_replay_golden_diff_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_draft_rule_replay_golden_sample(args: argparse.Namespace) -> int:
    """Export one semi-automatic replay golden-sample draft from a real run."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_replay_golden_draft_service.create_draft(
            run_id=args.run_id.strip(),
            output_path=args.output.strip(),
            issue_ids=tuple(args.issue_id or ()),
            issue_type=args.issue_type.strip(),
            limit=args.limit,
            case_id=args.case_id.strip(),
            description=args.description.strip(),
            layer=args.layer.strip(),
            expectation=args.expectation.strip(),
            baseline_path=args.baseline_path.strip(),
            candidate_path=args.candidate_path.strip(),
            append=args.append,
        )
    except (RunRecordNotFound, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "golden_draft": _rule_replay_golden_draft_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_promote_rule_replay_golden_draft(args: argparse.Namespace) -> int:
    """Validate one draft suite and promote selected cases into the target suite."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_replay_golden_promotion_service.promote(
            source_path=args.source_path.strip(),
            target_path=args.target_path.strip(),
            case_ids=tuple(args.case_id or ()),
            replace_existing=args.replace_existing,
        )
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "file_backed",
        "golden_promotion": _rule_replay_golden_promotion_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_review_analysis_rules(args: argparse.Namespace) -> int:
    """Review one candidate rule change against the local admission policy."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_review_service.review_rule_change(
            baseline_path=args.baseline_path.strip(),
            candidate_path=args.candidate_path.strip(),
            policy_path=args.policy_path.strip(),
            task_id=args.task_id.strip(),
            run_status=args.status.strip(),
            template_type=args.template_type.strip(),
            version=args.version.strip(),
            package_name=args.package_name.strip(),
            device_id=args.device_id.strip(),
            issue_type=args.issue_type.strip(),
            dimension=args.dimension.strip(),
            left_value=args.left_value.strip(),
            right_value=args.right_value.strip(),
            created_from=args.created_from.strip(),
            created_to=args.created_to.strip(),
            limit=args.limit,
            include_unchanged=args.include_unchanged,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "review": _rule_review_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_create_rule_review_report(args: argparse.Namespace) -> int:
    """Build one persisted summary report across review snapshots."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_review_report_service.create_report(
            name=args.name.strip(),
            created_by=args.created_by.strip(),
            snapshot_created_by=args.snapshot_created_by.strip(),
            decision=args.decision.strip(),
            policy_version=args.policy_version.strip(),
            baseline_path=args.baseline_path.strip(),
            candidate_path=args.candidate_path.strip(),
            created_from=args.created_from.strip(),
            created_to=args.created_to.strip(),
            limit=args.limit,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "report": _rule_review_report_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_compare_rule_review_reports(args: argparse.Namespace) -> int:
    """Compare two persisted rule review summary reports."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_review_report_service.compare_reports(
            name=args.name.strip(),
            created_by=args.created_by.strip(),
            left_report_id=args.left_report_id.strip(),
            right_report_id=args.right_report_id.strip(),
            include_unchanged=args.include_unchanged,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "comparison": _rule_review_report_comparison_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_set_rule_review_report_baseline(args: argparse.Namespace) -> int:
    """Register one named rule review report baseline."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_review_report_service.set_baseline(
            baseline_key=args.baseline_key.strip(),
            report_id=args.report_id.strip(),
            updated_by=args.updated_by.strip(),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "baseline": _rule_review_report_baseline_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_rule_review_report_baseline(args: argparse.Namespace) -> int:
    """Show one named rule review report baseline."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_review_report_service.get_baseline(args.baseline_key.strip())
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "baseline": _rule_review_report_baseline_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_compare_rule_review_report_against_baseline(args: argparse.Namespace) -> int:
    """Compare one rule review report against a named or auto-resolved baseline."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_review_report_service.compare_report_against_baseline(
            name=args.name.strip(),
            created_by=args.created_by.strip(),
            report_id=args.report_id.strip(),
            baseline_key=args.baseline_key.strip(),
            policy_version=args.policy_version.strip(),
            candidate_path=args.candidate_path.strip(),
            include_unchanged=args.include_unchanged,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "comparison": _rule_review_report_comparison_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_promote_rule_review_report_baseline(args: argparse.Namespace) -> int:
    """Evaluate one promotion attempt and update the baseline on approval."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_review_report_service.promote_baseline(
            baseline_key=args.baseline_key.strip(),
            report_id=args.report_id.strip(),
            updated_by=args.updated_by.strip(),
            policy_path=args.policy_path.strip(),
            include_unchanged=args.include_unchanged,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "promotion": _rule_review_report_baseline_promotion_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_rule_review_report_baseline_history(args: argparse.Namespace) -> int:
    """List one baseline's audit history."""
    bundle = create_v1_persistent_bootstrap()
    try:
        items = bundle.rule_review_report_service.list_baseline_history(args.baseline_key.strip())
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "baseline_key": args.baseline_key.strip(),
        "history_count": len(items),
        "history": [_rule_review_report_baseline_history_payload(item) for item in items],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_rollback_rule_review_report_baseline(args: argparse.Namespace) -> int:
    """Roll one named baseline back to a previous historical report."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_review_report_service.rollback_baseline(
            baseline_key=args.baseline_key.strip(),
            updated_by=args.updated_by.strip(),
            target_report_id=args.target_report_id.strip(),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "rollback": _rule_review_report_baseline_rollback_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_create_rule_review_report_baseline_audit(args: argparse.Namespace) -> int:
    """Create one persisted audit report for a baseline's full change history."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_review_report_service.create_baseline_audit_report(
            baseline_key=args.baseline_key.strip(),
            name=args.name.strip(),
            created_by=args.created_by.strip(),
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    payload = {
        "audit": _rule_review_report_baseline_audit_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_rule_review_report_baseline_audit(args: argparse.Namespace) -> int:
    """Show the latest audit summary and recent indexed versions for one baseline."""
    bundle = create_v1_persistent_bootstrap()
    try:
        result = bundle.rule_review_report_service.show_latest_baseline_audit(
            baseline_key=args.baseline_key.strip(),
            version_limit=args.limit,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "audit": _rule_review_report_baseline_audit_view_payload(result),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
