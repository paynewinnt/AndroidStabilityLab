from __future__ import annotations

import argparse

from stability.domain import TaskRunStatus, TaskTemplateType
from stability.cli.parser_utils import _add_monitoring_backend_override_argument


def register_rule_commands(subparsers: argparse._SubParsersAction, handler_module: object) -> None:
    show_rules_parser = subparsers.add_parser(
        "show-analysis-rules",
        help="Show current effective analysis rules plus source file details.",
    )
    show_rules_parser.add_argument("--path", default="", help="Optional rule file path override.")
    show_rules_parser.set_defaults(handler=handler_module._handle_show_analysis_rules)

    describe_rule_entrypoint_parser = subparsers.add_parser(
        "describe-rule-entrypoint",
        help="Describe the formal analysis rule configuration entrypoint as structured JSON.",
    )
    describe_rule_entrypoint_parser.add_argument("--path", default="", help="Optional rule file path override.")
    describe_rule_entrypoint_parser.set_defaults(handler=handler_module._handle_describe_rule_entrypoint)

    preview_rule_update_parser = subparsers.add_parser(
        "preview-analysis-rule-update",
        help="Preview an analysis rule configuration update without writing config files.",
    )
    preview_rule_update_parser.add_argument("--path", default="", help="Optional rule file path override.")
    preview_rule_update_parser.add_argument(
        "--set",
        dest="updates",
        action="append",
        default=[],
        help="Preview one editable field update as key=value. Repeat for multiple fields.",
    )
    preview_rule_update_parser.set_defaults(handler=handler_module._handle_preview_analysis_rule_update)

    save_rule_candidate_parser = subparsers.add_parser(
        "save-analysis-rule-candidate",
        help="Persist a candidate analysis-rule change for approval and publication.",
    )
    save_rule_candidate_parser.add_argument("--path", default="", help="Optional rule file path override.")
    save_rule_candidate_parser.add_argument("--created-by", default="cli", help="Candidate creator identity.")
    save_rule_candidate_parser.add_argument("--title", default="", help="Short candidate title.")
    save_rule_candidate_parser.add_argument("--reason", default="", help="Reason or change request summary.")
    save_rule_candidate_parser.add_argument("--required-approvals", type=int, default=1, help="Required approvals.")
    save_rule_candidate_parser.add_argument(
        "--set",
        dest="updates",
        action="append",
        default=[],
        help="Candidate field update as section.key=value. Repeat for multiple fields.",
    )
    save_rule_candidate_parser.set_defaults(handler=handler_module._handle_save_analysis_rule_candidate)

    list_rule_candidates_parser = subparsers.add_parser(
        "list-analysis-rule-candidates",
        help="List persisted candidate analysis-rule changes.",
    )
    list_rule_candidates_parser.add_argument("--path", default="", help="Optional rule file path override.")
    list_rule_candidates_parser.add_argument("--status", default="", help="Optional candidate status filter.")
    list_rule_candidates_parser.add_argument("--limit", type=int, default=20, help="Maximum candidates to return.")
    list_rule_candidates_parser.set_defaults(handler=handler_module._handle_list_analysis_rule_candidates)

    approve_rule_candidate_parser = subparsers.add_parser(
        "approve-analysis-rule-candidate",
        help="Approve or reject one persisted analysis-rule candidate.",
    )
    approve_rule_candidate_parser.add_argument("--candidate-id", required=True, help="Candidate id.")
    approve_rule_candidate_parser.add_argument("--actor-id", default="cli", help="Approver actor identity.")
    approve_rule_candidate_parser.add_argument(
        "--decision",
        default="approve",
        choices=["approve", "reject"],
        help="Review decision.",
    )
    approve_rule_candidate_parser.add_argument("--comment", default="", help="Optional review comment.")
    approve_rule_candidate_parser.add_argument("--path", default="", help="Optional rule file path override.")
    approve_rule_candidate_parser.set_defaults(handler=handler_module._handle_approve_analysis_rule_candidate)

    publish_rule_candidate_parser = subparsers.add_parser(
        "publish-analysis-rule-candidate",
        help="Publish an approved analysis-rule candidate to the active rule file.",
    )
    publish_rule_candidate_parser.add_argument("--candidate-id", required=True, help="Candidate id.")
    publish_rule_candidate_parser.add_argument("--published-by", default="cli", help="Publisher actor identity.")
    publish_rule_candidate_parser.add_argument("--path", default="", help="Optional rule file path override.")
    publish_rule_candidate_parser.set_defaults(handler=handler_module._handle_publish_analysis_rule_candidate)

    list_rule_versions_parser = subparsers.add_parser(
        "list-analysis-rule-versions",
        help="List published analysis-rule versions.",
    )
    list_rule_versions_parser.add_argument("--path", default="", help="Optional rule file path override.")
    list_rule_versions_parser.add_argument("--limit", type=int, default=20, help="Maximum versions to return.")
    list_rule_versions_parser.set_defaults(handler=handler_module._handle_list_analysis_rule_versions)

    rollback_rule_version_parser = subparsers.add_parser(
        "rollback-analysis-rule-version",
        help="Restore the active rule file using a published version record.",
    )
    rollback_rule_version_parser.add_argument("--version-id", required=True, help="Published version id to roll back.")
    rollback_rule_version_parser.add_argument("--rolled-back-by", default="cli", help="Rollback operator identity.")
    rollback_rule_version_parser.add_argument("--path", default="", help="Optional rule file path override.")
    rollback_rule_version_parser.set_defaults(handler=handler_module._handle_rollback_analysis_rule_version)

    bind_rule_permission_parser = subparsers.add_parser(
        "bind-analysis-rule-permission",
        help="Bind an actor to a rule-governance role or explicit permission set.",
    )
    bind_rule_permission_parser.add_argument("--actor-id", required=True, help="Actor id.")
    bind_rule_permission_parser.add_argument(
        "--role",
        default="reviewer",
        choices=["admin", "rule_admin", "publisher", "reviewer", "author", "viewer"],
        help="Rule-governance role.",
    )
    bind_rule_permission_parser.add_argument(
        "--permission",
        action="append",
        default=[],
        help="Optional explicit permission. Repeat for multiple permissions.",
    )
    bind_rule_permission_parser.add_argument("--bound-by", default="cli", help="Operator identity.")
    bind_rule_permission_parser.add_argument("--path", default="", help="Optional rule file path override.")
    bind_rule_permission_parser.set_defaults(handler=handler_module._handle_bind_analysis_rule_permission)

    list_rule_permissions_parser = subparsers.add_parser(
        "list-analysis-rule-permissions",
        help="List rule-governance actor permission bindings.",
    )
    list_rule_permissions_parser.add_argument("--path", default="", help="Optional rule file path override.")
    list_rule_permissions_parser.set_defaults(handler=handler_module._handle_list_analysis_rule_permissions)

    validate_rules_parser = subparsers.add_parser(
        "validate-analysis-rules",
        help="Validate one analysis rule file and report errors or warnings.",
    )
    validate_rules_parser.add_argument("--path", default="", help="Optional rule file path override.")
    validate_rules_parser.set_defaults(handler=handler_module._handle_validate_analysis_rules)

    export_rules_parser = subparsers.add_parser(
        "export-analysis-rules",
        help="Export the current effective analysis rules into one JSON file.",
    )
    export_rules_parser.add_argument("--output", required=True, help="Output path for the exported JSON file.")
    export_rules_parser.add_argument("--path", default="", help="Optional rule file path override.")
    export_rules_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    export_rules_parser.set_defaults(handler=handler_module._handle_export_analysis_rules)

    diff_rules_parser = subparsers.add_parser(
        "diff-analysis-rules",
        help="Diff two rule views across source/effective/default payloads.",
    )
    diff_rules_parser.add_argument("--left-path", default="", help="Optional left-side rule file path override.")
    diff_rules_parser.add_argument("--right-path", default="", help="Optional right-side rule file path override.")
    diff_rules_parser.add_argument(
        "--left-view",
        default="effective",
        choices=["effective", "source", "default"],
        help="Left-side rule view. Default: effective.",
    )
    diff_rules_parser.add_argument(
        "--right-view",
        default="source",
        choices=["effective", "source", "default"],
        help="Right-side rule view. Default: source.",
    )
    diff_rules_parser.set_defaults(handler=handler_module._handle_diff_analysis_rules)

    replay_rules_parser = subparsers.add_parser(
        "replay-analysis-rules",
        help="Replay one Top Issue query under baseline and candidate rule files, then diff the outcome.",
    )
    replay_rules_parser.add_argument("--candidate-path", required=True, help="Candidate rule file path.")
    replay_rules_parser.add_argument("--baseline-path", default="", help="Optional baseline rule file path override.")
    replay_rules_parser.add_argument("--task-id", default="", help="Optional task id filter.")
    replay_rules_parser.add_argument(
        "--status",
        default="",
        choices=[""] + [item.value for item in TaskRunStatus],
        help="Optional run status filter.",
    )
    replay_rules_parser.add_argument(
        "--template-type",
        default="",
        choices=[""] + [item.value for item in TaskTemplateType],
        help="Optional template type filter.",
    )
    replay_rules_parser.add_argument("--version", default="", help="Optional version filter.")
    replay_rules_parser.add_argument("--package-name", default="", help="Optional package name filter.")
    replay_rules_parser.add_argument("--device-id", default="", help="Optional device id filter.")
    replay_rules_parser.add_argument("--issue-type", default="", help="Optional issue type filter.")
    replay_rules_parser.add_argument("--created-from", default="", help="Optional inclusive ISO lower bound.")
    replay_rules_parser.add_argument("--created-to", default="", help="Optional inclusive ISO upper bound.")
    replay_rules_parser.add_argument("--limit", type=int, default=20, help="Maximum family rows to return.")
    replay_rules_parser.add_argument(
        "--include-unchanged",
        action="store_true",
        help="Include unchanged issue families in the output.",
    )
    replay_rules_parser.set_defaults(handler=handler_module._handle_replay_analysis_rules)

    verify_replay_goldens_parser = subparsers.add_parser(
        "verify-rule-replay-golden-samples",
        help="Run the built-in replay golden sample suite and report pass/fail by case.",
    )
    verify_replay_goldens_parser.add_argument(
        "--suite-path",
        default="",
        help="Optional replay golden sample suite path override.",
    )
    verify_replay_goldens_parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional golden case id filter. Repeat to select multiple cases.",
    )
    verify_replay_goldens_parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop the acceptance suite after the first failed case.",
    )
    verify_replay_goldens_parser.set_defaults(handler=handler_module._handle_verify_rule_replay_golden_samples)

    list_replay_golden_parser = subparsers.add_parser(
        "list-rule-replay-golden-samples",
        help="List golden suite cases with lightweight filters and counters.",
    )
    list_replay_golden_parser.add_argument(
        "--suite-path",
        default="",
        help="Optional golden suite path override.",
    )
    list_replay_golden_parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional case id filter. Repeat to select multiple cases.",
    )
    list_replay_golden_parser.add_argument("--issue-type", default="", help="Optional issue type filter.")
    list_replay_golden_parser.add_argument("--layer", default="", help="Optional layer filter.")
    list_replay_golden_parser.add_argument("--expectation", default="", help="Optional expectation filter.")
    list_replay_golden_parser.add_argument("--limit", type=int, default=100, help="Maximum case rows to return.")
    list_replay_golden_parser.set_defaults(handler=handler_module._handle_list_rule_replay_golden_samples)

    show_replay_golden_parser = subparsers.add_parser(
        "show-rule-replay-golden-sample",
        help="Show the full payload for one golden suite case.",
    )
    show_replay_golden_parser.add_argument("--case-id", required=True, help="Golden case id.")
    show_replay_golden_parser.add_argument(
        "--suite-path",
        default="",
        help="Optional golden suite path override.",
    )
    show_replay_golden_parser.set_defaults(handler=handler_module._handle_show_rule_replay_golden_sample)

    diff_replay_golden_parser = subparsers.add_parser(
        "diff-rule-replay-golden-samples",
        help="Diff two golden suite files by case id.",
    )
    diff_replay_golden_parser.add_argument("--left-path", required=True, help="Left suite path.")
    diff_replay_golden_parser.add_argument("--right-path", required=True, help="Right suite path.")
    diff_replay_golden_parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional case id filter. Repeat to compare multiple specific cases.",
    )
    diff_replay_golden_parser.add_argument(
        "--include-unchanged",
        action="store_true",
        help="Include unchanged cases in the diff output.",
    )
    diff_replay_golden_parser.set_defaults(handler=handler_module._handle_diff_rule_replay_golden_samples)

    draft_replay_golden_parser = subparsers.add_parser(
        "draft-rule-replay-golden-sample",
        help="Export one replay golden-sample draft from a persisted run.",
    )
    draft_replay_golden_parser.add_argument("--run-id", required=True, help="Source run id.")
    draft_replay_golden_parser.add_argument(
        "--issue-id",
        action="append",
        default=[],
        help="Issue id to include. Repeat to select multiple issue events.",
    )
    draft_replay_golden_parser.add_argument(
        "--issue-type",
        default="",
        help="Optional issue type filter when issue ids are not provided.",
    )
    draft_replay_golden_parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max issue count when selecting by issue type.",
    )
    draft_replay_golden_parser.add_argument("--case-id", default="", help="Optional explicit case id.")
    draft_replay_golden_parser.add_argument("--description", default="", help="Optional explicit description.")
    draft_replay_golden_parser.add_argument("--layer", default="", help="Optional explicit layer override.")
    draft_replay_golden_parser.add_argument(
        "--expectation",
        default="",
        help="Optional explicit expectation override.",
    )
    draft_replay_golden_parser.add_argument(
        "--baseline-path",
        default="",
        help="Optional baseline rule file override. Defaults to config/stability_rules.json.",
    )
    draft_replay_golden_parser.add_argument(
        "--candidate-path",
        default="",
        help="Optional candidate rule file override. Defaults to baseline.",
    )
    draft_replay_golden_parser.add_argument(
        "--output",
        required=True,
        help="Draft suite output path.",
    )
    draft_replay_golden_parser.add_argument(
        "--append",
        action="store_true",
        help="Append into an existing suite file instead of overwriting it.",
    )
    draft_replay_golden_parser.set_defaults(handler=handler_module._handle_draft_rule_replay_golden_sample)

    promote_replay_golden_parser = subparsers.add_parser(
        "promote-rule-replay-golden-draft",
        help="Validate one draft golden suite and promote selected cases into the target suite.",
    )
    promote_replay_golden_parser.add_argument("--source-path", required=True, help="Draft golden suite path.")
    promote_replay_golden_parser.add_argument(
        "--target-path",
        default="config/rule_replay_golden_samples.json",
        help="Target golden suite path. Default: config/rule_replay_golden_samples.json.",
    )
    promote_replay_golden_parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Optional case id filter. Repeat to promote multiple cases from one draft file.",
    )
    promote_replay_golden_parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Replace existing target cases with the same case ids.",
    )
    promote_replay_golden_parser.set_defaults(handler=handler_module._handle_promote_rule_replay_golden_draft)

    review_rules_parser = subparsers.add_parser(
        "review-analysis-rules",
        help="Evaluate one candidate rule change against the local rule-admission policy.",
    )
    review_rules_parser.add_argument("--candidate-path", required=True, help="Candidate rule file path.")
    review_rules_parser.add_argument("--baseline-path", default="", help="Optional baseline rule file path override.")
    review_rules_parser.add_argument("--policy-path", default="", help="Optional review policy file path override.")
    review_rules_parser.add_argument("--task-id", default="", help="Optional task id filter.")
    review_rules_parser.add_argument(
        "--status",
        default="",
        choices=[""] + [item.value for item in TaskRunStatus],
        help="Optional run status filter.",
    )
    review_rules_parser.add_argument(
        "--template-type",
        default="",
        choices=[""] + [item.value for item in TaskTemplateType],
        help="Optional template type filter.",
    )
    review_rules_parser.add_argument("--version", default="", help="Optional version filter.")
    review_rules_parser.add_argument("--package-name", default="", help="Optional package name filter.")
    review_rules_parser.add_argument("--device-id", default="", help="Optional device id filter.")
    review_rules_parser.add_argument("--issue-type", default="", help="Optional issue type filter.")
    review_rules_parser.add_argument(
        "--dimension",
        default="",
        choices=["", "version", "device", "scenario"],
        help="Optional performance comparison dimension used to layer baseline risks into the review result.",
    )
    review_rules_parser.add_argument(
        "--left-value",
        default="",
        help="Optional left-side scope value for performance baseline comparison.",
    )
    review_rules_parser.add_argument(
        "--right-value",
        default="",
        help="Optional right-side scope value for performance baseline comparison.",
    )
    review_rules_parser.add_argument("--created-from", default="", help="Optional inclusive ISO lower bound.")
    review_rules_parser.add_argument("--created-to", default="", help="Optional inclusive ISO upper bound.")
    review_rules_parser.add_argument("--limit", type=int, default=20, help="Maximum family rows to return.")
    review_rules_parser.add_argument(
        "--include-unchanged",
        action="store_true",
        help="Include unchanged issue families in the evaluation payload.",
    )
    review_rules_parser.set_defaults(handler=handler_module._handle_review_analysis_rules)

    create_review_report_parser = subparsers.add_parser(
        "create-rule-review-report",
        help="Build one readable report across persisted rule-review snapshots.",
    )
    create_review_report_parser.add_argument("--name", required=True, help="Report title.")
    create_review_report_parser.add_argument("--created-by", default="cli", help="Report creator identity.")
    create_review_report_parser.add_argument(
        "--snapshot-created-by",
        default="",
        help="Optional creator filter applied to source review snapshots.",
    )
    create_review_report_parser.add_argument(
        "--decision",
        default="",
        choices=["", "pass", "conditional_pass", "fail"],
        help="Optional decision filter applied to source review snapshots.",
    )
    create_review_report_parser.add_argument("--policy-version", default="", help="Optional policy version filter.")
    create_review_report_parser.add_argument("--baseline-path", default="", help="Optional baseline path filter.")
    create_review_report_parser.add_argument("--candidate-path", default="", help="Optional candidate path filter.")
    create_review_report_parser.add_argument("--created-from", default="", help="Optional inclusive ISO lower bound.")
    create_review_report_parser.add_argument("--created-to", default="", help="Optional inclusive ISO upper bound.")
    create_review_report_parser.add_argument("--limit", type=int, default=50, help="Maximum snapshot count.")
    create_review_report_parser.set_defaults(handler=handler_module._handle_create_rule_review_report)

    compare_review_reports_parser = subparsers.add_parser(
        "compare-rule-review-reports",
        help="Compare two persisted rule review summary reports and write one diff bundle.",
    )
    compare_review_reports_parser.add_argument("--name", required=True, help="Comparison title.")
    compare_review_reports_parser.add_argument("--created-by", default="cli", help="Comparison creator identity.")
    compare_review_reports_parser.add_argument("--left-report-id", required=True, help="Left review report id.")
    compare_review_reports_parser.add_argument("--right-report-id", required=True, help="Right review report id.")
    compare_review_reports_parser.add_argument(
        "--include-unchanged",
        action="store_true",
        help="Include unchanged high-risk family rows in the diff bundle.",
    )
    compare_review_reports_parser.set_defaults(handler=handler_module._handle_compare_rule_review_reports)

    set_review_report_baseline_parser = subparsers.add_parser(
        "set-rule-review-report-baseline",
        help="Register one named baseline pointer to a persisted rule review report.",
    )
    set_review_report_baseline_parser.add_argument("--baseline-key", required=True, help="Stable baseline key.")
    set_review_report_baseline_parser.add_argument("--report-id", required=True, help="Rule review report id.")
    set_review_report_baseline_parser.add_argument("--updated-by", default="cli", help="Updater identity.")
    set_review_report_baseline_parser.set_defaults(handler=handler_module._handle_set_rule_review_report_baseline)

    show_review_report_baseline_parser = subparsers.add_parser(
        "show-rule-review-report-baseline",
        help="Show one named rule review report baseline.",
    )
    show_review_report_baseline_parser.add_argument("--baseline-key", required=True, help="Stable baseline key.")
    show_review_report_baseline_parser.set_defaults(handler=handler_module._handle_show_rule_review_report_baseline)

    compare_against_baseline_parser = subparsers.add_parser(
        "compare-rule-review-report-against-baseline",
        help="Compare one rule review report against a named or auto-resolved baseline.",
    )
    compare_against_baseline_parser.add_argument("--name", required=True, help="Comparison title.")
    compare_against_baseline_parser.add_argument("--report-id", required=True, help="Target rule review report id.")
    compare_against_baseline_parser.add_argument("--created-by", default="cli", help="Comparison creator identity.")
    compare_against_baseline_parser.add_argument("--baseline-key", default="", help="Optional named baseline key.")
    compare_against_baseline_parser.add_argument(
        "--policy-version",
        default="",
        help="Optional auto-baseline filter by policy version when no baseline key is provided.",
    )
    compare_against_baseline_parser.add_argument(
        "--candidate-path",
        default="",
        help="Optional auto-baseline filter by candidate path when no baseline key is provided.",
    )
    compare_against_baseline_parser.add_argument(
        "--include-unchanged",
        action="store_true",
        help="Include unchanged high-risk family rows in the diff bundle.",
    )
    compare_against_baseline_parser.set_defaults(handler=handler_module._handle_compare_rule_review_report_against_baseline)

    promote_baseline_parser = subparsers.add_parser(
        "promote-rule-review-report-baseline",
        help="Evaluate one report against baseline-promotion policy and update the baseline if approved.",
    )
    promote_baseline_parser.add_argument("--baseline-key", required=True, help="Named baseline key to update.")
    promote_baseline_parser.add_argument("--report-id", required=True, help="Target rule review report id.")
    promote_baseline_parser.add_argument("--updated-by", default="cli", help="Updater identity.")
    promote_baseline_parser.add_argument("--policy-path", default="", help="Optional promotion policy file path.")
    promote_baseline_parser.add_argument(
        "--include-unchanged",
        action="store_true",
        help="Include unchanged family rows when generating the comparison artifact.",
    )
    promote_baseline_parser.set_defaults(handler=handler_module._handle_promote_rule_review_report_baseline)

    list_baseline_history_parser = subparsers.add_parser(
        "list-rule-review-report-baseline-history",
        help="List one baseline's assignment history for audit and rollback.",
    )
    list_baseline_history_parser.add_argument("--baseline-key", required=True, help="Named baseline key.")
    list_baseline_history_parser.set_defaults(handler=handler_module._handle_list_rule_review_report_baseline_history)

    rollback_baseline_parser = subparsers.add_parser(
        "rollback-rule-review-report-baseline",
        help="Roll one named baseline back to the previous or specified historical report.",
    )
    rollback_baseline_parser.add_argument("--baseline-key", required=True, help="Named baseline key.")
    rollback_baseline_parser.add_argument("--updated-by", default="cli", help="Updater identity.")
    rollback_baseline_parser.add_argument(
        "--target-report-id",
        default="",
        help="Optional historical report id to roll back to. Defaults to the previous distinct report.",
    )
    rollback_baseline_parser.set_defaults(handler=handler_module._handle_rollback_rule_review_report_baseline)

    create_baseline_audit_parser = subparsers.add_parser(
        "create-rule-review-report-baseline-audit",
        help="Build one readable audit report across a baseline's full change history.",
    )
    create_baseline_audit_parser.add_argument("--baseline-key", required=True, help="Named baseline key.")
    create_baseline_audit_parser.add_argument("--name", required=True, help="Audit report title.")
    create_baseline_audit_parser.add_argument("--created-by", default="cli", help="Report creator identity.")
    create_baseline_audit_parser.set_defaults(handler=handler_module._handle_create_rule_review_report_baseline_audit)

    show_baseline_audit_parser = subparsers.add_parser(
        "show-rule-review-report-baseline-audit",
        help="Show the latest baseline audit summary together with recent indexed versions.",
    )
    show_baseline_audit_parser.add_argument("--baseline-key", required=True, help="Named baseline key.")
    show_baseline_audit_parser.add_argument("--limit", type=int, default=5, help="Maximum indexed versions to return.")
    show_baseline_audit_parser.set_defaults(handler=handler_module._handle_show_rule_review_report_baseline_audit)
