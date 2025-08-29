from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace


def default_runner_status():
    return SimpleNamespace(
        observed_at="2025-07-22T20:10:00",
        root_dir="runtime/unattended_runner",
        lock_path="runtime/unattended_runner/runner.lock",
        heartbeat_path="runtime/unattended_runner/runner_status.json",
        daily_report_paths={
            "report_json_path": "runtime/unattended_runner/daily_reports/2025-07-22/report.json",
            "summary_markdown_path": "runtime/unattended_runner/daily_reports/2025-07-22/summary.md",
        },
        weekly_report_paths={
            "report_json_path": "runtime/unattended_runner/weekly_reports/2025-W30/report.json",
            "summary_markdown_path": "runtime/unattended_runner/weekly_reports/2025-W30/summary.md",
        },
        latest_daily_report={
            "report_date": "2025-07-22",
            "generated_at": "2025-07-22T20:10:00",
            "round_count": 4,
            "executed_round_count": 3,
            "failed_round_count": 1,
            "device_online_rate": 0.75,
            "failed_rate": 0.25,
            "offline_rate": 0.1,
            "recovery_success_rate": 0.5,
            "quarantined_device_count": 1,
            "top_issue_types": [{"issue_type": "device_offline", "count": 1}],
            "task_summaries": [{"task_id": "task-unattended-1", "round_count": 2, "failed_round_count": 1}],
        },
        latest_weekly_report={
            "week_key": "2025-W30",
            "anchor_date": "2025-07-22",
            "week_start_date": "2025-07-20",
            "week_end_date": "2025-07-26",
            "generated_at": "2025-07-22T20:10:00",
            "round_count": 7,
            "executed_round_count": 5,
            "failed_round_count": 2,
            "active_day_count": 3,
            "device_online_rate": 0.8,
            "failed_rate": 0.286,
            "offline_rate": 0.143,
            "recovery_success_rate": 0.5,
            "quarantined_device_count": 1,
            "top_issue_types": [{"issue_type": "device_offline", "count": 2}],
            "daily_summaries": [
                {
                    "report_date": "2025-07-22",
                    "round_count": 4,
                    "failed_round_count": 1,
                    "offline_event_count": 1,
                    "quarantined_device_count": 1,
                }
            ],
            "task_summaries": [{"task_id": "task-unattended-1", "round_count": 5, "failed_round_count": 2}],
            "interruption_rounds": [
                {
                    "task_id": "task-unattended-1",
                    "round_id": "round-weekly-1",
                    "status": "device_offline",
                }
            ],
        },
        lock_present=True,
        heartbeat_present=True,
        lock_state="active",
        status="running",
        pid=4242,
        started_at="2025-07-22T20:00:00",
        finished_at=None,
        last_heartbeat_at="2025-07-22T20:10:00",
        heartbeat_age_seconds=5,
        stale_after_seconds=300,
        is_stale=False,
        interval_seconds=60,
        max_iterations=0,
        task_id="task-unattended-1",
        force=False,
        cycle_count=4,
        active_cycle_index=5,
        stopped_reason="",
        last_patrol={
            "generated_at": "2025-07-22T20:09:55",
            "executed_task_count": 2,
            "failed_rate": 0.25,
            "offline_rate": 0.1,
            "recovery_success_rate": 0.5,
            "quarantined_device_count": 1,
        },
        recent_patrols=(
            {
                "cycle_index": 2,
                "finished_at": "2025-07-22T20:07:55",
                "executed_task_count": 1,
                "failed_rate": 0.0,
                "offline_rate": 0.0,
                "recovery_success_rate": 1.0,
                "quarantined_device_count": 0,
            },
            {
                "cycle_index": 3,
                "finished_at": "2025-07-22T20:08:55",
                "executed_task_count": 1,
                "failed_rate": 0.0,
                "offline_rate": 0.4,
                "recovery_success_rate": 1.0,
                "quarantined_device_count": 0,
            },
            {
                "cycle_index": 4,
                "finished_at": "2025-07-22T20:09:55",
                "task_count": 2,
                "due_task_count": 1,
                "executed_task_count": 2,
                "skipped_task_count": 1,
                "failed_rate": 0.25,
                "offline_rate": 0.1,
                "recovery_success_rate": 0.5,
                "quarantined_device_count": 1,
            },
        ),
    )


def writable_bundle() -> object:
    from .web_portal_bundles import bundle

    web_bundle = bundle()

    base_task = SimpleNamespace(
        task_id="task-1",
        task_name="Calculator Cold Start",
        template_type=SimpleNamespace(value="cold_start_loop"),
        target_app=SimpleNamespace(
            package_name="com.hihonor.calculator",
            app_label="Calculator",
            version_name="1.0.0",
            version_code="100",
            launch_activity=".MainActivity",
        ),
        task_params={},
        selected_device_ids=("device-1",),
        sampling_config=SimpleNamespace(interval_seconds=5, enabled_metrics=("cpu", "memory")),
        duration_seconds=0,
        timeout_seconds=0,
        created_by="cli",
        notes="",
        metadata={},
        planned_device_count=lambda: 1,
    )
    created_task = SimpleNamespace(
        task_id="task-write-1",
        task_name="Calculator Cold Start",
        template_type=SimpleNamespace(value="cold_start_loop"),
        target_app=SimpleNamespace(
            package_name="com.hihonor.calculator",
            app_label="Calculator",
            version_name="1.0.0",
            version_code="100",
            launch_activity=".MainActivity",
        ),
        task_params={"source": "web"},
        selected_device_ids=("device-1",),
        sampling_config=SimpleNamespace(interval_seconds=5, enabled_metrics=("cpu", "memory")),
        duration_seconds=0,
        timeout_seconds=0,
        created_by="tester",
        notes="",
        metadata={"source": "web"},
        planned_device_count=lambda: 1,
    )

    def _create_task(task: object):
        return SimpleNamespace(task=created_task, created_at=datetime(2025, 7, 23, 10, 0, 0))

    def _get_task(task_id: str):
        if task_id == base_task.task_id:
            return base_task
        if task_id == created_task.task_id:
            return created_task
        raise ValueError(task_id)

    def _plan_run(task: object, *, requested_devices=(), metadata=None):
        requested = tuple(requested_devices or getattr(task, "selected_device_ids", ()) or ())
        return SimpleNamespace(
            task=task,
            requested_devices=requested,
            planned_device_count=len(requested) or 1,
            dispatches=(SimpleNamespace(device_id=requested[0] if requested else "device-1"),),
        )

    def _create_run(task: object, *, requested_devices=(), requested_by="", metadata=None):
        requested = tuple(requested_devices or getattr(task, "selected_device_ids", ()) or ())
        run = SimpleNamespace(
            run_id="run-write-1",
            run_status="pending",
            target_device_ids=requested or ("device-1",),
            started_by=requested_by or "tester",
            summary={
                "total_instances": 1,
                "pending_instances": 1,
                "active_instances": 0,
                "success_instances": 0,
                "failed_instances": 0,
            },
        )
        instance = SimpleNamespace(
            instance_id="instance-write-1",
            instance_status="pending",
            device_id=requested[0] if requested else "device-1",
        )
        return SimpleNamespace(
            task=task,
            run=run,
            plan=SimpleNamespace(planned_device_count=len(requested) or 1),
            instances=(instance,),
            created_at=datetime(2025, 7, 23, 10, 0, 0),
        )

    def _execute_run(run_id: str, *, persist_monitoring=True, collect_snapshot=True, stop_on_failure=False, max_concurrency=1, retry_count=0):
        run = SimpleNamespace(run_id=run_id, run_status="success")
        instance = SimpleNamespace(
            instance_id="instance-write-1",
            device_id="device-1",
            instance_status="success",
            monitoring_backend="solox",
            monitoring_profile="solox",
            monitoring_trace_path="runtime/monitoring/trace.perfetto-trace",
            monitoring_snapshot_path="runtime/monitoring/snapshot.json",
        )
        return SimpleNamespace(
            task=base_task,
            run=run,
            instances=(instance,),
            executed_at=datetime(2025, 7, 23, 10, 0, 0),
            report_paths={"instance-write-1": "runtime/report.md"},
        )

    def _stop_run(run_id: str, *, requested_by="", reason="user_stopped"):
        run = SimpleNamespace(run_id=run_id, run_status="cancelled")
        instance = SimpleNamespace(
            instance_id="instance-write-1",
            device_id="device-1",
            instance_status="cancelled",
        )
        return SimpleNamespace(
            task=base_task,
            run=run,
            instances=(instance,),
            requested_by=requested_by,
            reason=reason,
            stopped_instance_count=1,
            already_terminal_instance_count=0,
            cleanup_results=({"device_id": "device-1", "ok": True},),
        )

    def _configure_task(*, task_id: str, interval_minutes: int, device_id: str = "device-1", backup_device_id: str = "device-2", **kwargs):
        return SimpleNamespace(
            task_id=task_id,
            task_name="Calculator Cold Start",
            configured=True,
            enabled=True,
            interval_minutes=interval_minutes,
            desired_device_count=1,
            failure_threshold=3,
            rotation_strategy="round_robin",
            rotation_advance_policy="every_round",
            rotation_cursor=0,
            rotation_advance_count=0,
            primary_device_ids=(device_id,),
            backup_device_ids=(backup_device_id,),
            next_run_at=None,
            last_run_at=None,
            last_run_id="",
            due=False,
            latest_summary={},
            long_run_summary={"round_count": 0},
            recent_device_windows=(),
            recent_rounds=(),
        )

    def _run_task_round(*, task_id: str, **kwargs):
        configured_task = _configure_task(task_id=task_id, interval_minutes=30)
        return SimpleNamespace(
            task=configured_task,
            executed=True,
            reason="executed",
            round_record={"round_id": "round-write-1", "run_id": "run-1", "assigned_device_ids": ["device-1"]},
        )

    def _run_due_tasks(*, task_id: str = "", **kwargs):
        configured_task = _configure_task(task_id=task_id or "task-1", interval_minutes=30)
        return SimpleNamespace(
            generated_at=None,
            task_count=1,
            enabled_task_count=1,
            due_task_count=1,
            executed_task_count=1,
            skipped_task_count=0,
            failed_rate=0.0,
            offline_rate=0.0,
            recovery_success_rate=1.0,
            quarantined_device_count=0,
            quarantined_device_ids=(),
            quarantine_probe_attempt_count=0,
            quarantine_probe_skipped_count=0,
            quarantine_probe_recovered_count=0,
            recovered_device_ids=(),
            metrics={"instance_count": 1},
            executed_rounds=({"round_id": "round-write-1"},),
            task_records=(configured_task,),
        )

    def _build_daily_report(*, task_id: str = "", **kwargs):
        return SimpleNamespace(
            report_date="2025-07-23",
            generated_at=None,
            task_count=1,
            active_task_count=1,
            round_count=1,
            executed_round_count=1,
            skipped_round_count=0,
            failed_round_count=0,
            total_runtime_seconds=60,
            total_runtime_hours=0.017,
            device_online_rate=1.0,
            failed_rate=0.0,
            offline_rate=0.0,
            recovery_success_rate=1.0,
            quarantined_device_count=0,
            quarantined_device_ids=(),
            issue_type_distribution={},
            top_issue_types=(),
            interruption_rounds=(),
            task_summaries=(),
            metrics={"instance_count": 1},
        )

    def _build_weekly_report(*, task_id: str = "", **kwargs):
        return SimpleNamespace(
            week_key="2025-W30",
            anchor_date="2025-07-23",
            week_start_date="2025-07-20",
            week_end_date="2025-07-26",
            generated_at=None,
            task_count=1,
            active_task_count=1,
            active_day_count=1,
            round_count=1,
            executed_round_count=1,
            skipped_round_count=0,
            failed_round_count=0,
            total_runtime_seconds=60,
            total_runtime_hours=0.017,
            device_online_rate=1.0,
            failed_rate=0.0,
            offline_rate=0.0,
            recovery_success_rate=1.0,
            quarantined_device_count=0,
            quarantined_device_ids=(),
            issue_type_distribution={},
            top_issue_types=(),
            interruption_rounds=(),
            task_summaries=(),
            daily_summaries=(),
            metrics={"instance_count": 1},
        )

    web_bundle.task_service.create_task = _create_task
    web_bundle.task_service.get_task = _get_task
    web_bundle.execution_service = SimpleNamespace(plan_run=_plan_run, create_run=_create_run)
    web_bundle.run_execution_service = SimpleNamespace(execute_run=_execute_run, stop_run=_stop_run)
    web_bundle.unattended_service = SimpleNamespace(
        configure_task=_configure_task,
        list_task_records=lambda **kwargs: (_configure_task(task_id="task-1", interval_minutes=30),),
        get_task_record=lambda task_id: _configure_task(task_id=task_id, interval_minutes=30),
        run_task_round=_run_task_round,
        run_due_tasks=_run_due_tasks,
        build_daily_report=_build_daily_report,
        build_weekly_report=_build_weekly_report,
    )
    return web_bundle


