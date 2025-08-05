from __future__ import annotations

import argparse

from stability.domain import TaskRunStatus, TaskTemplateType
from stability.cli.parser_utils import _add_monitoring_backend_override_argument
from stability.scenario.registry import METRIC_REGISTRY, get_supported_template_values, list_scenario_definitions


_TEMPLATE_VALUES = get_supported_template_values()
_TEMPLATE_HELP = "Task template type. Supported: " + "; ".join(
    f"{item.value}={item.chinese_name}" for item in list_scenario_definitions()
)
_METRIC_HELP = "Enabled metric name. Repeat this flag or pass a comma-separated list. Known: " + ", ".join(
    f"{key}={metric.title}" for key, metric in METRIC_REGISTRY.items()
)


def register_task_commands(subparsers: argparse._SubParsersAction, handler_module: object) -> None:
    # create-task负责沉淀任务定义，默认走持久化仓储，方便后续直接create-run。
    create_parser = subparsers.add_parser(
        "create-task",
        help="Create a V1 task definition with the persistent bootstrap by default.",
    )
    create_parser.add_argument("--task-name", required=True, help="Human-readable task name.")
    create_parser.add_argument("--package-name", required=True, help="Android package name.")
    create_parser.add_argument(
        "--template-type",
        default=TaskTemplateType.CUSTOM.value,
        choices=list(_TEMPLATE_VALUES),
        help=_TEMPLATE_HELP,
    )
    create_parser.add_argument(
        "--device",
        dest="devices",
        action="append",
        default=[],
        help="Target device id. Repeat this flag or pass a comma-separated list.",
    )
    create_parser.add_argument("--app-label", default="", help="Optional app label.")
    create_parser.add_argument("--version-name", default="", help="Optional app version name.")
    create_parser.add_argument("--version-code", default="", help="Optional app version code.")
    create_parser.add_argument("--launch-activity", default="", help="Optional launch activity.")
    create_parser.add_argument("--created-by", default="cli", help="Task creator identity.")
    create_parser.add_argument("--duration-seconds", type=int, default=0, help="Planned duration.")
    create_parser.add_argument("--timeout-seconds", type=int, default=0, help="Execution timeout.")
    create_parser.add_argument(
        "--sampling-interval",
        type=int,
        default=5,
        help="Sampling interval in seconds.",
    )
    create_parser.add_argument(
        "--metric",
        dest="metrics",
        action="append",
        default=[],
        help=_METRIC_HELP,
    )
    create_parser.add_argument("--note", default="", help="Optional task note.")
    create_parser.add_argument(
        "--metadata",
        default="{}",
        help="Optional JSON object merged into task metadata.",
    )
    create_parser.add_argument(
        "--task-params",
        default="{}",
        help="Optional JSON object used as template-specific task params.",
    )
    create_parser.add_argument(
        "--in-memory",
        action="store_true",
        help="Use the in-memory bootstrap instead of the persistent database-backed bootstrap.",
    )
    create_parser.add_argument(
        "--skip-device-sync",
        action="store_true",
        help="Skip device synchronization before creating the task.",
    )
    create_parser.set_defaults(handler=handler_module._handle_create_task)

    schema_parser = subparsers.add_parser(
        "show-task-template-schema",
        help="Show the shared Web/CLI schema for one task template.",
    )
    schema_parser.add_argument(
        "--template-type",
        required=True,
        choices=list(_TEMPLATE_VALUES),
        help=_TEMPLATE_HELP,
    )
    schema_parser.set_defaults(handler=handler_module._handle_show_task_template_schema)

    run_parser = subparsers.add_parser(
        "create-run",
        help="Create a persistent V1 task run and its execution instances.",
    )
    run_parser.add_argument("--task-id", required=True, help="Task definition id to execute.")
    run_parser.add_argument(
        "--device",
        dest="devices",
        action="append",
        default=[],
        help="Requested device id. Repeat this flag or pass a comma-separated list.",
    )
    run_parser.add_argument(
        "--requested-by",
        default="cli",
        help="Operator identity recorded on the task run.",
    )
    run_parser.add_argument(
        "--metadata",
        default="{}",
        help="Optional JSON object merged into run metadata.",
    )
    run_parser.add_argument(
        "--skip-device-sync",
        action="store_true",
        help="Skip device synchronization before creating the run.",
    )
    run_parser.set_defaults(handler=handler_module._handle_create_run)

    # execute-run负责把已有run推进到最小可执行完成态，便于阶段二/三串起来验证。
    execute_parser = subparsers.add_parser(
        "execute-run",
        help="Execute a previously created V1 task run through the minimal local runner.",
    )
    execute_parser.add_argument("--run-id", required=True, help="Task run id to execute.")
    execute_parser.add_argument(
        "--skip-monitoring",
        action="store_true",
        help="Skip monitoring snapshot collection and only advance lifecycle state.",
    )
    execute_parser.add_argument(
        "--no-persist-monitoring",
        action="store_true",
        help="Do not persist monitoring samples into the legacy database storage.",
    )
    execute_parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop executing later instances if one instance fails.",
    )
    execute_parser.add_argument(
        "--max-concurrency",
        type=int,
        default=1,
        help="Maximum number of instances to execute in parallel. Default: 1.",
    )
    execute_parser.add_argument(
        "--retry-count",
        type=int,
        default=0,
        help="Retry one failed instance up to N additional times before marking it failed. Default: 0.",
    )
    _add_monitoring_backend_override_argument(execute_parser)
    execute_parser.set_defaults(handler=handler_module._handle_execute_run)

    list_devices_parser = subparsers.add_parser(
        "list-devices",
        help="List persisted devices with lightweight summary fields.",
    )
    list_devices_sync_group = list_devices_parser.add_mutually_exclusive_group()
    list_devices_sync_group.add_argument(
        "--sync",
        action="store_true",
        help="Refresh the persistent device registry from adb before listing devices.",
    )
    list_devices_sync_group.add_argument(
        "--sync-device",
        default="",
        help="Refresh one target device from adb before listing devices, without a full registry sync.",
    )
    list_devices_parser.set_defaults(handler=handler_module._handle_list_devices)

    show_device_parser = subparsers.add_parser(
        "show-device",
        help="Show one persisted device with detail fields.",
    )
    show_device_parser.add_argument("--device-id", required=True, help="Device id to inspect.")
    show_device_sync_group = show_device_parser.add_mutually_exclusive_group()
    show_device_sync_group.add_argument(
        "--sync",
        action="store_true",
        help="Refresh the persistent device registry from adb before showing the device.",
    )
    show_device_sync_group.add_argument(
        "--sync-target-only",
        action="store_true",
        help="Refresh only the target device from adb before showing it, without a full registry sync.",
    )
    show_device_parser.set_defaults(handler=handler_module._handle_show_device)

    list_device_pools_parser = subparsers.add_parser(
        "list-device-pools",
        help="List schedulable device pool summaries grouped by device group and team.",
    )
    list_device_pools_parser.add_argument(
        "--sync",
        action="store_true",
        help="Refresh the persistent device registry from adb before listing pools.",
    )
    list_device_pools_parser.add_argument("--group", default="", help="Only include one device group.")
    list_device_pools_parser.add_argument("--team", default="", help="Only include one owning team.")
    list_device_pools_parser.add_argument(
        "--tag",
        dest="tags",
        action="append",
        default=[],
        help="Only include devices matching this tag. Repeat this flag or pass a comma-separated list.",
    )
    list_device_pools_parser.set_defaults(handler=handler_module._handle_list_device_pools)

    inspect_device_pool_parser = subparsers.add_parser(
        "inspect-device-pool",
        help="Inspect one filtered device pool with schedulable devices and unschedulable reasons.",
    )
    inspect_device_pool_parser.add_argument(
        "--sync",
        action="store_true",
        help="Refresh the persistent device registry from adb before inspecting the pool.",
    )
    inspect_device_pool_parser.add_argument("--group", default="", help="Device group to inspect.")
    inspect_device_pool_parser.add_argument("--team", default="", help="Owning team to inspect.")
    inspect_device_pool_parser.add_argument(
        "--tag",
        dest="tags",
        action="append",
        default=[],
        help="Device tag to inspect. Repeat this flag or pass a comma-separated list.",
    )
    inspect_device_pool_parser.set_defaults(handler=handler_module._handle_inspect_device_pool)

    list_tasks_parser = subparsers.add_parser(
        "list-tasks",
        help="List persisted task definitions with lightweight summary fields.",
    )
    list_tasks_parser.set_defaults(handler=handler_module._handle_list_tasks)

    show_task_parser = subparsers.add_parser(
        "show-task",
        help="Show one persisted task definition with detail fields.",
    )
    show_task_parser.add_argument("--task-id", required=True, help="Task id to inspect.")
    show_task_parser.set_defaults(handler=handler_module._handle_show_task)

    list_long_run_templates_parser = subparsers.add_parser(
        "list-long-run-templates",
        help="List long-run unattended template defaults and overridable parameters.",
    )
    list_long_run_templates_parser.set_defaults(handler=handler_module._handle_list_long_run_templates)

    show_long_run_template_parser = subparsers.add_parser(
        "show-long-run-template",
        help="Show one long-run unattended template with default values.",
    )
    show_long_run_template_parser.add_argument("--template-key", required=True, help="Long-run template key.")
    show_long_run_template_parser.set_defaults(handler=handler_module._handle_show_long_run_template)

    plan_long_run_template_parser = subparsers.add_parser(
        "plan-long-run-template",
        help="Preview one long-run unattended template with optional key=value overrides.",
    )
    plan_long_run_template_parser.add_argument("--template-key", required=True, help="Long-run template key.")
    plan_long_run_template_parser.add_argument(
        "--override",
        dest="overrides",
        action="append",
        default=[],
        help="Override a template parameter as key=value. Repeat this flag for multiple overrides.",
    )
    plan_long_run_template_parser.set_defaults(handler=handler_module._handle_plan_long_run_template)

    configure_unattended_parser = subparsers.add_parser(
        "configure-unattended-task",
        help="Configure one task for the minimal unattended V3 stage-1 backend loop.",
    )
    configure_unattended_parser.add_argument("--task-id", required=True, help="Task id to configure.")
    configure_unattended_parser.add_argument(
        "--interval-minutes",
        type=int,
        required=True,
        help="Polling interval in minutes.",
    )
    configure_unattended_parser.add_argument(
        "--device",
        dest="devices",
        action="append",
        default=[],
        help="Primary device id. Repeat this flag or pass a comma-separated list.",
    )
    configure_unattended_parser.add_argument(
        "--backup-device",
        dest="backup_devices",
        action="append",
        default=[],
        help="Backup device id. Repeat this flag or pass a comma-separated list.",
    )
    configure_unattended_parser.add_argument(
        "--desired-device-count",
        type=int,
        default=0,
        help="Desired device count for each unattended round. Default: infer from primary devices.",
    )
    configure_unattended_parser.add_argument(
        "--failure-threshold",
        type=int,
        default=3,
        help="Consecutive failure threshold before one device is quarantined. Default: 3.",
    )
    configure_unattended_parser.add_argument(
        "--max-round-history",
        type=int,
        default=10,
        help="Number of recent unattended rounds retained on the task metadata. Default: 10.",
    )
    configure_unattended_parser.add_argument(
        "--rotation-strategy",
        default="round_robin",
        choices=["fixed", "round_robin"],
        help="Primary device rotation strategy used by long-run unattended rounds. Default: round_robin.",
    )
    configure_unattended_parser.add_argument(
        "--rotation-advance-policy",
        default="every_round",
        choices=["every_round", "failure_only"],
        help="When to advance the primary device rotation cursor. Default: every_round.",
    )
    configure_unattended_parser.add_argument(
        "--max-device-window-history",
        type=int,
        default=10,
        help="Number of recent device assignment windows retained on the task metadata. Default: 10.",
    )
    configure_unattended_parser.add_argument(
        "--disabled",
        action="store_true",
        help="Store the unattended config but keep the task disabled.",
    )
    configure_unattended_parser.add_argument(
        "--start-now",
        action="store_true",
        help="Mark the task immediately due instead of waiting one interval window.",
    )
    configure_unattended_parser.set_defaults(handler=handler_module._handle_configure_unattended_task)

    list_unattended_parser = subparsers.add_parser(
        "list-unattended-tasks",
        help="List unattended task configs with due state and latest round summary.",
    )
    list_unattended_parser.add_argument(
        "--enabled-only",
        action="store_true",
        help="Only show enabled unattended tasks.",
    )
    list_unattended_parser.add_argument(
        "--due-only",
        action="store_true",
        help="Only show currently due unattended tasks.",
    )
    list_unattended_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of unattended tasks to return. Default: 20.",
    )
    list_unattended_parser.set_defaults(handler=handler_module._handle_list_unattended_tasks)

    show_unattended_parser = subparsers.add_parser(
        "show-unattended-task",
        help="Show one unattended task config with recent round records.",
    )
    show_unattended_parser.add_argument("--task-id", required=True, help="Task id to inspect.")
    show_unattended_parser.set_defaults(handler=handler_module._handle_show_unattended_task)

    run_unattended_parser = subparsers.add_parser(
        "run-unattended-round",
        help="Trigger one unattended round immediately for one configured task.",
    )
    run_unattended_parser.add_argument("--task-id", required=True, help="Task id to execute.")
    run_unattended_parser.add_argument(
        "--requested-by",
        default="automation",
        help="Operator identity recorded on the generated task run.",
    )
    run_unattended_parser.add_argument(
        "--skip-monitoring",
        action="store_true",
        help="Skip monitoring snapshot collection for the unattended round.",
    )
    run_unattended_parser.add_argument(
        "--no-persist-monitoring",
        action="store_true",
        help="Do not persist monitoring samples into the legacy database storage.",
    )
    run_unattended_parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop executing later instances in this unattended round after one failure.",
    )
    run_unattended_parser.add_argument(
        "--max-concurrency",
        type=int,
        default=1,
        help="Maximum instance concurrency for the generated run. Default: 1.",
    )
    run_unattended_parser.add_argument(
        "--retry-count",
        type=int,
        default=0,
        help="Additional execute-run retry count used for the unattended round. Default: 0.",
    )
    run_unattended_parser.add_argument(
        "--respect-schedule",
        action="store_true",
        help="Only execute when the task is already due.",
    )
    _add_monitoring_backend_override_argument(run_unattended_parser)
    run_unattended_parser.set_defaults(handler=handler_module._handle_run_unattended_round)

    patrol_unattended_parser = subparsers.add_parser(
        "patrol-unattended-tasks",
        help="Execute due unattended tasks and return one patrol summary.",
    )
    patrol_unattended_parser.add_argument("--task-id", default="", help="Optional single-task scope.")
    patrol_unattended_parser.add_argument(
        "--force",
        action="store_true",
        help="Run matching unattended tasks even when they are not due.",
    )
    patrol_unattended_parser.add_argument(
        "--requested-by",
        default="automation",
        help="Operator identity recorded on generated task runs.",
    )
    patrol_unattended_parser.add_argument(
        "--skip-monitoring",
        action="store_true",
        help="Skip monitoring snapshot collection for generated runs.",
    )
    patrol_unattended_parser.add_argument(
        "--no-persist-monitoring",
        action="store_true",
        help="Do not persist monitoring samples into the legacy database storage.",
    )
    patrol_unattended_parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop executing later instances inside each generated run after one failure.",
    )
    patrol_unattended_parser.add_argument(
        "--max-concurrency",
        type=int,
        default=1,
        help="Maximum instance concurrency for each generated run. Default: 1.",
    )
    patrol_unattended_parser.add_argument(
        "--retry-count",
        type=int,
        default=0,
        help="Additional execute-run retry count used for generated runs. Default: 0.",
    )
    _add_monitoring_backend_override_argument(patrol_unattended_parser)
    patrol_unattended_parser.set_defaults(handler=handler_module._handle_patrol_unattended_tasks)

    unattended_runner_parser = subparsers.add_parser(
        "run-unattended-patrol-runner",
        help="Run one minimal timed background loop over patrol-unattended-tasks.",
    )
    unattended_runner_parser.add_argument("--task-id", default="", help="Optional single-task scope.")
    unattended_runner_parser.add_argument(
        "--interval-seconds",
        type=int,
        default=60,
        help="Sleep interval between patrol cycles in seconds. Default: 60.",
    )
    unattended_runner_parser.add_argument(
        "--max-iterations",
        type=int,
        default=0,
        help="Maximum patrol cycles to run. Use 0 to run until interrupted. Default: 0.",
    )
    unattended_runner_parser.add_argument(
        "--force",
        action="store_true",
        help="Run matching unattended tasks even when they are not due.",
    )
    unattended_runner_parser.add_argument(
        "--requested-by",
        default="automation",
        help="Operator identity recorded on generated task runs.",
    )
    unattended_runner_parser.add_argument(
        "--skip-monitoring",
        action="store_true",
        help="Skip monitoring snapshot collection for generated runs.",
    )
    unattended_runner_parser.add_argument(
        "--no-persist-monitoring",
        action="store_true",
        help="Do not persist monitoring samples into the legacy database storage.",
    )
    unattended_runner_parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop executing later instances inside each generated run after one failure.",
    )
    unattended_runner_parser.add_argument(
        "--max-concurrency",
        type=int,
        default=1,
        help="Maximum instance concurrency for each generated run. Default: 1.",
    )
    unattended_runner_parser.add_argument(
        "--retry-count",
        type=int,
        default=0,
        help="Additional execute-run retry count used for generated runs. Default: 0.",
    )
    _add_monitoring_backend_override_argument(unattended_runner_parser)
    unattended_runner_parser.set_defaults(handler=handler_module._handle_run_unattended_patrol_runner)

    unattended_daily_report_parser = subparsers.add_parser(
        "build-unattended-daily-report",
        help="Build one unattended daily report from retained unattended round history.",
    )
    unattended_daily_report_parser.add_argument(
        "--task-id",
        default="",
        help="Optional single-task scope. Default: aggregate every configured unattended task.",
    )
    unattended_daily_report_parser.add_argument(
        "--report-date",
        default="",
        help="Optional report date in YYYY-MM-DD format. Default: today in runner storage time.",
    )
    unattended_daily_report_parser.set_defaults(handler=handler_module._handle_build_unattended_daily_report)

    unattended_weekly_report_parser = subparsers.add_parser(
        "build-unattended-weekly-report",
        help="Build one unattended weekly report from retained unattended round history.",
    )
    unattended_weekly_report_parser.add_argument(
        "--task-id",
        default="",
        help="Optional single-task scope. Default: aggregate every configured unattended task.",
    )
    unattended_weekly_report_parser.add_argument(
        "--report-date",
        default="",
        help="Optional anchor date in YYYY-MM-DD format. Default: today in runner storage time.",
    )
    unattended_weekly_report_parser.set_defaults(handler=handler_module._handle_build_unattended_weekly_report)

    list_runs_parser = subparsers.add_parser(
        "list-runs",
        help="List persisted task runs with lightweight summary fields.",
    )
    list_runs_parser.add_argument("--task-id", default="", help="Optional task id filter.")
    list_runs_parser.add_argument(
        "--status",
        default="",
        choices=[""] + [item.value for item in TaskRunStatus],
        help="Optional run status filter.",
    )
    list_runs_parser.add_argument(
        "--template-type",
        default="",
        choices=[""] + list(_TEMPLATE_VALUES),
        help="Optional template type filter.",
    )
    list_runs_parser.add_argument("--package-name", default="", help="Optional package name filter.")
    list_runs_parser.add_argument("--device-id", default="", help="Optional device id filter.")
    list_runs_parser.add_argument(
        "--has-issue",
        default="",
        choices=["", "true", "false"],
        help="Optional issue presence filter.",
    )
    list_runs_parser.add_argument(
        "--created-from",
        default="",
        help="Optional inclusive ISO datetime lower bound for run creation time.",
    )
    list_runs_parser.add_argument(
        "--created-to",
        default="",
        help="Optional inclusive ISO datetime upper bound for run creation time.",
    )
    list_runs_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of runs to return. Use 0 to return none. Default: 20.",
    )
    list_runs_parser.set_defaults(handler=handler_module._handle_list_runs)

    show_run_parser = subparsers.add_parser(
        "show-run",
        help="Show one persisted task run with per-instance history details.",
    )
    show_run_parser.add_argument("--run-id", required=True, help="Task run id to inspect.")
    show_run_parser.set_defaults(handler=handler_module._handle_show_run)
