from __future__ import annotations

import argparse

from stability.domain import TaskRunStatus, TaskTemplateType
from stability.cli.parser_utils import _add_monitoring_backend_override_argument


def register_analysis_commands(subparsers: argparse._SubParsersAction, handler_module: object) -> None:
    list_top_issues_parser = subparsers.add_parser(
        "list-top-issues",
        help="List aggregated issues grouped by issue fingerprint and ordered by Top Issue score.",
    )
    list_top_issues_parser.add_argument("--task-id", default="", help="Optional task id filter.")
    list_top_issues_parser.add_argument(
        "--status",
        default="",
        choices=[""] + [item.value for item in TaskRunStatus],
        help="Optional run status filter.",
    )
    list_top_issues_parser.add_argument(
        "--template-type",
        default="",
        choices=[""] + [item.value for item in TaskTemplateType],
        help="Optional template type filter.",
    )
    list_top_issues_parser.add_argument(
        "--version",
        default="",
        help="Optional target-app version filter, e.g. 1.0.0(100).",
    )
    list_top_issues_parser.add_argument("--package-name", default="", help="Optional package name filter.")
    list_top_issues_parser.add_argument("--device-id", default="", help="Optional device id filter.")
    list_top_issues_parser.add_argument(
        "--issue-type",
        default="",
        help="Optional issue type filter, e.g. crash/startup_timeout/device_offline.",
    )
    list_top_issues_parser.add_argument(
        "--created-from",
        default="",
        help="Optional inclusive ISO datetime lower bound for run creation time.",
    )
    list_top_issues_parser.add_argument(
        "--created-to",
        default="",
        help="Optional inclusive ISO datetime upper bound for run creation time.",
    )
    list_top_issues_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of aggregated issues to return. Default: 20.",
    )
    list_top_issues_parser.set_defaults(handler=handler_module._handle_list_top_issues)

    show_issue_group_parser = subparsers.add_parser(
        "show-issue-group",
        help="Show one aggregated issue group with sample issue events and evidence references.",
    )
    show_issue_group_parser.add_argument("--fingerprint", required=True, help="Issue fingerprint to inspect.")
    show_issue_group_parser.add_argument("--task-id", default="", help="Optional task id filter.")
    show_issue_group_parser.add_argument(
        "--status",
        default="",
        choices=[""] + [item.value for item in TaskRunStatus],
        help="Optional run status filter.",
    )
    show_issue_group_parser.add_argument(
        "--template-type",
        default="",
        choices=[""] + [item.value for item in TaskTemplateType],
        help="Optional template type filter.",
    )
    show_issue_group_parser.add_argument(
        "--version",
        default="",
        help="Optional target-app version filter, e.g. 1.0.0(100).",
    )
    show_issue_group_parser.add_argument("--package-name", default="", help="Optional package name filter.")
    show_issue_group_parser.add_argument("--device-id", default="", help="Optional device id filter.")
    show_issue_group_parser.add_argument(
        "--issue-type",
        default="",
        help="Optional issue type filter, e.g. crash/startup_timeout/device_offline.",
    )
    show_issue_group_parser.add_argument(
        "--created-from",
        default="",
        help="Optional inclusive ISO datetime lower bound for run creation time.",
    )
    show_issue_group_parser.add_argument(
        "--created-to",
        default="",
        help="Optional inclusive ISO datetime upper bound for run creation time.",
    )
    show_issue_group_parser.set_defaults(handler=handler_module._handle_show_issue_group)

    compare_issues_parser = subparsers.add_parser(
        "compare-issues",
        help="Compare aggregated issues across version/device/scenario scopes.",
    )
    compare_issues_parser.add_argument(
        "--dimension",
        required=True,
        choices=["version", "device", "scenario"],
        help="Comparison dimension.",
    )
    compare_issues_parser.add_argument("--left-value", required=True, help="Left-side scope value.")
    compare_issues_parser.add_argument("--right-value", required=True, help="Right-side scope value.")
    compare_issues_parser.add_argument("--task-id", default="", help="Optional task id filter.")
    compare_issues_parser.add_argument(
        "--status",
        default="",
        choices=[""] + [item.value for item in TaskRunStatus],
        help="Optional run status filter.",
    )
    compare_issues_parser.add_argument(
        "--template-type",
        default="",
        choices=[""] + [item.value for item in TaskTemplateType],
        help="Optional shared template type filter when the comparison dimension is not scenario.",
    )
    compare_issues_parser.add_argument(
        "--version",
        default="",
        help="Optional shared version filter when the comparison dimension is not version.",
    )
    compare_issues_parser.add_argument("--package-name", default="", help="Optional package name filter.")
    compare_issues_parser.add_argument(
        "--issue-type",
        default="",
        help="Optional issue type filter, e.g. crash/startup_timeout/device_offline.",
    )
    compare_issues_parser.add_argument(
        "--created-from",
        default="",
        help="Optional inclusive ISO datetime lower bound for run creation time.",
    )
    compare_issues_parser.add_argument(
        "--created-to",
        default="",
        help="Optional inclusive ISO datetime upper bound for run creation time.",
    )
    compare_issues_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of compared issue rows to return. Default: 20.",
    )
    compare_issues_parser.set_defaults(handler=handler_module._handle_compare_issues)

    compare_performance_parser = subparsers.add_parser(
        "compare-performance-trends",
        help="Compare CPU/memory/FPS/power trends across version/device/scenario scopes.",
    )
    compare_performance_parser.add_argument(
        "--dimension",
        required=True,
        choices=["version", "device", "scenario"],
        help="Comparison dimension.",
    )
    compare_performance_parser.add_argument("--left-value", required=True, help="Left-side scope value.")
    compare_performance_parser.add_argument("--right-value", required=True, help="Right-side scope value.")
    compare_performance_parser.add_argument("--task-id", default="", help="Optional task id filter.")
    compare_performance_parser.add_argument(
        "--status",
        default="",
        choices=[""] + [item.value for item in TaskRunStatus],
        help="Optional run status filter.",
    )
    compare_performance_parser.add_argument(
        "--template-type",
        default="",
        choices=[""] + [item.value for item in TaskTemplateType],
        help="Optional shared template type filter when the comparison dimension is not scenario.",
    )
    compare_performance_parser.add_argument(
        "--version",
        default="",
        help="Optional shared version filter when the comparison dimension is not version.",
    )
    compare_performance_parser.add_argument("--package-name", default="", help="Optional package name filter.")
    compare_performance_parser.add_argument(
        "--created-from",
        default="",
        help="Optional inclusive ISO datetime lower bound for run creation time.",
    )
    compare_performance_parser.add_argument(
        "--created-to",
        default="",
        help="Optional inclusive ISO datetime upper bound for run creation time.",
    )
    compare_performance_parser.set_defaults(handler=handler_module._handle_compare_performance_trends)

    judge_regression_parser = subparsers.add_parser(
        "judge-regression",
        help="Judge regression results on top of one version/device/scenario comparison.",
    )
    judge_regression_parser.add_argument(
        "--dimension",
        required=True,
        choices=["version", "device", "scenario"],
        help="Comparison dimension.",
    )
    judge_regression_parser.add_argument("--left-value", required=True, help="Baseline scope value.")
    judge_regression_parser.add_argument("--right-value", required=True, help="Target scope value.")
    judge_regression_parser.add_argument("--task-id", default="", help="Optional task id filter.")
    judge_regression_parser.add_argument(
        "--status",
        default="",
        choices=[""] + [item.value for item in TaskRunStatus],
        help="Optional run status filter.",
    )
    judge_regression_parser.add_argument(
        "--template-type",
        default="",
        choices=[""] + [item.value for item in TaskTemplateType],
        help="Optional shared template type filter when the comparison dimension is not scenario.",
    )
    judge_regression_parser.add_argument(
        "--version",
        default="",
        help="Optional shared version filter when the comparison dimension is not version.",
    )
    judge_regression_parser.add_argument("--package-name", default="", help="Optional package name filter.")
    judge_regression_parser.add_argument(
        "--issue-type",
        default="",
        help="Optional issue type filter, e.g. crash/startup_timeout/device_offline.",
    )
    judge_regression_parser.add_argument(
        "--created-from",
        default="",
        help="Optional inclusive ISO datetime lower bound for run creation time.",
    )
    judge_regression_parser.add_argument(
        "--created-to",
        default="",
        help="Optional inclusive ISO datetime upper bound for run creation time.",
    )
    judge_regression_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of judged issue rows to return. Default: 20.",
    )
    judge_regression_parser.add_argument(
        "--min-side-issue-groups",
        type=int,
        default=None,
        help="Minimum issue-group count required on each side before the overall result is comparable.",
    )
    judge_regression_parser.add_argument(
        "--significant-occurrence-delta",
        type=int,
        default=None,
        help="Minimum occurrence delta treated as a meaningful issue change.",
    )
    judge_regression_parser.add_argument(
        "--significant-affected-run-delta",
        type=int,
        default=None,
        help="Minimum affected-run delta treated as a meaningful issue change.",
    )
    judge_regression_parser.add_argument(
        "--significant-affected-device-delta",
        type=int,
        default=None,
        help="Minimum affected-device delta treated as a meaningful issue change.",
    )
    judge_regression_parser.add_argument(
        "--significant-affected-scenario-delta",
        type=int,
        default=None,
        help="Minimum affected-scenario delta treated as a meaningful issue change.",
    )
    judge_regression_parser.add_argument(
        "--min-side-metric-sessions",
        type=int,
        default=None,
        help="Minimum metric-session count required on each side before one metric is comparable.",
    )
    judge_regression_parser.add_argument(
        "--min-side-metric-samples",
        type=int,
        default=None,
        help="Minimum metric-sample count required on each side before one metric is comparable.",
    )
    judge_regression_parser.add_argument(
        "--significant-metric-delta-ratio",
        type=float,
        default=None,
        help="Minimum average metric delta ratio treated as meaningful, relative to the baseline side.",
    )
    judge_regression_parser.set_defaults(handler=handler_module._handle_judge_regression)

    create_snapshot_parser = subparsers.add_parser(
        "create-analysis-snapshot",
        help="Persist one top-issues/comparison/regression/replay/review analysis result as a reusable snapshot.",
    )
    create_snapshot_parser.add_argument(
        "--snapshot-type",
        required=True,
        choices=["top_issues", "comparison", "regression", "replay", "review"],
        help="Analysis snapshot type.",
    )
    create_snapshot_parser.add_argument("--name", required=True, help="Snapshot title.")
    create_snapshot_parser.add_argument("--created-by", default="cli", help="Snapshot creator identity.")
    create_snapshot_parser.add_argument(
        "--tag",
        dest="tags",
        action="append",
        default=[],
        help="Optional snapshot tag. Repeat this flag or pass a comma-separated list.",
    )
    create_snapshot_parser.add_argument("--task-id", default="", help="Optional task id filter.")
    create_snapshot_parser.add_argument(
        "--status",
        default="",
        choices=[""] + [item.value for item in TaskRunStatus],
        help="Optional run status filter.",
    )
    create_snapshot_parser.add_argument(
        "--template-type",
        default="",
        choices=[""] + [item.value for item in TaskTemplateType],
        help="Optional template type filter.",
    )
    create_snapshot_parser.add_argument("--version", default="", help="Optional version filter.")
    create_snapshot_parser.add_argument("--package-name", default="", help="Optional package name filter.")
    create_snapshot_parser.add_argument("--device-id", default="", help="Optional device id filter.")
    create_snapshot_parser.add_argument(
        "--issue-type",
        default="",
        help="Optional issue type filter, e.g. crash/startup_timeout/device_offline.",
    )
    create_snapshot_parser.add_argument("--created-from", default="", help="Optional inclusive ISO lower bound.")
    create_snapshot_parser.add_argument("--created-to", default="", help="Optional inclusive ISO upper bound.")
    create_snapshot_parser.add_argument("--limit", type=int, default=20, help="Maximum item count.")
    create_snapshot_parser.add_argument(
        "--left-value",
        default="",
        help="Left-side scope value for comparison/regression snapshots.",
    )
    create_snapshot_parser.add_argument(
        "--right-value",
        default="",
        help="Right-side scope value for comparison/regression snapshots.",
    )
    create_snapshot_parser.add_argument(
        "--dimension",
        default="",
        choices=["", "version", "device", "scenario"],
        help="Comparison dimension for comparison/regression snapshots.",
    )
    create_snapshot_parser.add_argument(
        "--min-side-issue-groups",
        type=int,
        default=None,
        help="Regression-only minimum comparable issue-group count on each side.",
    )
    create_snapshot_parser.add_argument(
        "--significant-occurrence-delta",
        type=int,
        default=None,
        help="Regression-only meaningful occurrence delta threshold.",
    )
    create_snapshot_parser.add_argument(
        "--significant-affected-run-delta",
        type=int,
        default=None,
        help="Regression-only meaningful affected-run delta threshold.",
    )
    create_snapshot_parser.add_argument(
        "--significant-affected-device-delta",
        type=int,
        default=None,
        help="Regression-only meaningful affected-device delta threshold.",
    )
    create_snapshot_parser.add_argument(
        "--significant-affected-scenario-delta",
        type=int,
        default=None,
        help="Regression-only meaningful affected-scenario delta threshold.",
    )
    create_snapshot_parser.add_argument(
        "--min-side-metric-sessions",
        type=int,
        default=None,
        help="Regression-only minimum metric-session count required on each side.",
    )
    create_snapshot_parser.add_argument(
        "--min-side-metric-samples",
        type=int,
        default=None,
        help="Regression-only minimum metric-sample count required on each side.",
    )
    create_snapshot_parser.add_argument(
        "--significant-metric-delta-ratio",
        type=float,
        default=None,
        help="Regression-only meaningful average metric delta ratio threshold.",
    )
    create_snapshot_parser.add_argument("--candidate-path", default="", help="Replay-only candidate rule file path.")
    create_snapshot_parser.add_argument("--baseline-path", default="", help="Replay-only baseline rule file path.")
    create_snapshot_parser.add_argument("--policy-path", default="", help="Review-only policy file path override.")
    create_snapshot_parser.add_argument(
        "--include-unchanged",
        action="store_true",
        help="Replay/review-only: include unchanged issue families in the persisted payload.",
    )
    create_snapshot_parser.set_defaults(handler=handler_module._handle_create_analysis_snapshot)

    list_snapshots_parser = subparsers.add_parser(
        "list-analysis-snapshots",
        help="List persisted analysis snapshots.",
    )
    list_snapshots_parser.add_argument(
        "--snapshot-type",
        default="",
        choices=["", "top_issues", "comparison", "regression", "replay", "review"],
        help="Optional snapshot type filter.",
    )
    list_snapshots_parser.add_argument("--created-by", default="", help="Optional creator filter.")
    list_snapshots_parser.add_argument("--limit", type=int, default=20, help="Maximum snapshot count.")
    list_snapshots_parser.set_defaults(handler=handler_module._handle_list_analysis_snapshots)

    show_snapshot_parser = subparsers.add_parser(
        "show-analysis-snapshot",
        help="Show one persisted analysis snapshot.",
    )
    show_snapshot_parser.add_argument("--snapshot-id", required=True, help="Snapshot id to inspect.")
    show_snapshot_parser.set_defaults(handler=handler_module._handle_show_analysis_snapshot)

    delete_snapshot_parser = subparsers.add_parser(
        "delete-analysis-snapshot",
        help="Delete one persisted analysis snapshot bundle.",
    )
    delete_snapshot_parser.add_argument("--snapshot-id", required=True, help="Snapshot id to delete.")
    delete_snapshot_parser.set_defaults(handler=handler_module._handle_delete_analysis_snapshot)

