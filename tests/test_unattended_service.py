from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
import unittest

from stability.app import DeviceService, ExecutionService, UnattendedService
from stability.domain import (
    Device,
    DeviceAvailabilityState,
    DeviceConnectionState,
    TaskDefinition,
    TaskTargetApp,
)
from stability.domain.value_objects import utcnow
from stability.infrastructure.device_adapter import DeviceDescriptor, DeviceDiscoveryAdapter
from stability.repositories import (
    DomainExecutionInstanceFactory,
    DomainTaskRunFactory,
    InMemoryDeviceRepository,
    InMemoryInstanceRepository,
    InMemoryRunRepository,
    InMemoryTaskRepository,
    StaticDevicePlanner,
)


class _NullDiscoveryAdapter(DeviceDiscoveryAdapter):
    def list_devices(self, include_unavailable: bool = False):
        return []

    def get_device(self, serial: str):
        return None


class _MapDiscoveryAdapter(DeviceDiscoveryAdapter):
    def __init__(self, descriptors: dict[str, DeviceDescriptor]) -> None:
        self._descriptors = descriptors

    def list_devices(self, include_unavailable: bool = False):
        items = list(self._descriptors.values())
        if include_unavailable:
            return items
        return [item for item in items if item.status == "device"]

    def get_device(self, serial: str):
        return self._descriptors.get(serial)


class _FakeRunExecutionService:
    def __init__(
        self,
        *,
        task_repository,
        run_repository,
        instance_repository,
        execution_service: ExecutionService,
        outcomes: list[list[dict[str, object]]],
    ) -> None:
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._instance_repository = instance_repository
        self._execution_service = execution_service
        self._outcomes = list(outcomes)

    def execute_run(
        self,
        run_id: str,
        *,
        persist_monitoring: bool = True,
        collect_snapshot: bool = True,
        stop_on_failure: bool = False,
        max_concurrency: int = 1,
        retry_count: int = 0,
    ):
        run = self._run_repository.get(run_id)
        task = self._task_repository.get(run.task_definition_id)
        instances = list(self._instance_repository.list_by_run(run_id))
        outcome_set = self._outcomes.pop(0)
        for index, instance in enumerate(instances):
            outcome = outcome_set[min(index, len(outcome_set) - 1)]
            summary = {"metadata": {}}
            if outcome.get("recovered_after_disconnect"):
                summary["metadata"]["scenario_result"] = {"recovered_after_disconnect": True}
            if outcome.get("retryable_attempt"):
                summary["metadata"]["execution_attempts"] = [{"attempt": 1, "retryable": True}]
            self._execution_service.mark_instance_preparing(task, run, instance)
            self._execution_service.mark_instance_running(task, run, instance)
            status = str(outcome.get("status", "success"))
            if status == "success":
                self._execution_service.complete_instance(task, run, instance, summary=summary)
            else:
                self._execution_service.fail_instance(
                    task,
                    run,
                    instance,
                    exit_reason=str(outcome.get("exit_reason", "execution_error")),
                    summary=summary,
                )
        return SimpleNamespace(
            task=task,
            run=self._run_repository.get(run_id),
            instances=tuple(self._instance_repository.list_by_run(run_id)),
        )


class UnattendedServiceTest(unittest.TestCase):
    def test_list_long_run_templates_exposes_named_template_family(self) -> None:
        service, _, _ = self._build_service(devices=[], outcomes=[])

        templates = service.list_long_run_templates()

        self.assertEqual(
            [item.template_id for item in templates],
            ["smoke_long_run", "overnight_long_run", "weekly_soak", "custom_long_run"],
        )
        overnight = service.get_long_run_template("overnight_long_run")
        self.assertEqual(overnight.name, "Overnight Long Run")
        self.assertEqual(overnight.default_interval_minutes, 60)
        self.assertEqual(overnight.default_max_rounds, 12)
        self.assertEqual(overnight.recommended_device_count, 2)
        self.assertEqual(overnight.recommended_rotation_strategy, "round_robin")
        self.assertIn("soak", overnight.default_tags)
        self.assertTrue(overnight.risk_notes)

    def test_build_long_run_plan_returns_configure_kwargs_without_starting_task(self) -> None:
        service, task_repo, _ = self._build_service(
            devices=[self._device("device-1", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE)],
            outcomes=[],
        )
        task_repo.add(
            TaskDefinition(
                task_id="task-plan",
                task_name="Plan Only Task",
                target_app=TaskTargetApp(package_name="com.example.plan"),
                selected_device_ids=["device-1"],
            )
        )

        plan = service.build_long_run_plan(
            "overnight_long_run",
            primary_device_ids=["device-1"],
            backup_device_ids=["device-2"],
            tags=["release-candidate", "soak"],
        )

        self.assertEqual(plan.template.template_id, "overnight_long_run")
        self.assertEqual(plan.configure_kwargs["interval_minutes"], 60)
        self.assertEqual(plan.configure_kwargs["desired_device_count"], 2)
        self.assertEqual(plan.configure_kwargs["primary_device_ids"], ["device-1"])
        self.assertEqual(plan.configure_kwargs["backup_device_ids"], ["device-2"])
        self.assertEqual(plan.configure_kwargs["rotation_strategy"], "round_robin")
        self.assertEqual(plan.configure_kwargs["rotation_advance_policy"], "every_round")
        self.assertEqual(plan.runner_kwargs["max_iterations"], 12)
        self.assertEqual(
            plan.task_metadata_suggestions["tags"],
            ["long_run", "overnight", "soak", "release-candidate"],
        )
        self.assertIn("primary_device_ids", plan.overrides)
        self.assertIn("backup_device_ids", plan.overrides)
        record = service.get_task_record("task-plan")
        self.assertFalse(record.configured)

    def test_build_long_run_plan_records_template_overrides(self) -> None:
        service, _, _ = self._build_service(devices=[], outcomes=[])

        plan = service.build_long_run_plan(
            "weekly_soak",
            interval_minutes=30,
            max_rounds=6,
            desired_device_count=2,
            rotation_advance_policy="failure_only",
            failure_threshold=2,
            max_round_history=6,
            max_device_window_history=6,
            enabled=False,
            start_now=True,
        )

        self.assertEqual(plan.configure_kwargs["interval_minutes"], 30)
        self.assertEqual(plan.configure_kwargs["desired_device_count"], 2)
        self.assertEqual(plan.configure_kwargs["rotation_advance_policy"], "failure_only")
        self.assertEqual(plan.configure_kwargs["failure_threshold"], 2)
        self.assertFalse(plan.configure_kwargs["enabled"])
        self.assertTrue(plan.configure_kwargs["start_now"])
        self.assertEqual(plan.runner_kwargs["max_iterations"], 6)
        self.assertEqual(plan.overrides["interval_minutes"]["default"], 120)
        self.assertEqual(plan.overrides["interval_minutes"]["value"], 30)
        self.assertEqual(plan.overrides["max_rounds"]["default"], 84)
        self.assertEqual(plan.overrides["max_rounds"]["value"], 6)
        self.assertEqual(plan.overrides["enabled"]["value"], False)

    def test_get_long_run_template_rejects_unknown_template(self) -> None:
        service, _, _ = self._build_service(devices=[], outcomes=[])

        with self.assertRaises(LookupError):
            service.get_long_run_template("missing-template")

    def test_round_robin_rotation_advances_primary_device_window(self) -> None:
        service, task_repo, _ = self._build_service(
            devices=[
                self._device("device-1", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE),
                self._device("device-2", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE),
            ],
            outcomes=[
                [{"status": "success"}],
                [{"status": "success"}],
                [{"status": "success"}],
            ],
        )
        task_repo.add(
            TaskDefinition(
                task_id="task-rotation",
                task_name="Rotation Task",
                target_app=TaskTargetApp(package_name="com.example.rotation"),
                selected_device_ids=["device-1", "device-2"],
            )
        )

        service.configure_task(
            "task-rotation",
            interval_minutes=10,
            desired_device_count=1,
            start_now=True,
        )

        first = service.run_task_round("task-rotation", force=True)
        second = service.run_task_round("task-rotation", force=True)
        third = service.run_task_round("task-rotation", force=True)
        record = service.get_task_record("task-rotation")

        self.assertEqual(first.round_record["assigned_device_ids"], ["device-1"])
        self.assertEqual(second.round_record["assigned_device_ids"], ["device-2"])
        self.assertEqual(third.round_record["assigned_device_ids"], ["device-1"])
        self.assertEqual(record.rotation_cursor, 1)
        self.assertEqual(record.rotation_advance_count, 3)
        self.assertEqual(record.long_run_summary["unique_assigned_device_count"], 2)
        self.assertEqual(record.recent_device_windows[0]["assigned_device_ids"], ["device-1"])

    def test_failure_only_rotation_advances_after_failure(self) -> None:
        service, task_repo, _ = self._build_service(
            devices=[
                self._device("device-1", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE),
                self._device("device-2", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE),
            ],
            outcomes=[
                [{"status": "success"}],
                [{"status": "failed", "exit_reason": "device_offline"}],
            ],
        )
        task_repo.add(
            TaskDefinition(
                task_id="task-failure-rotation",
                task_name="Failure Rotation Task",
                target_app=TaskTargetApp(package_name="com.example.rotation"),
                selected_device_ids=["device-1", "device-2"],
            )
        )

        service.configure_task(
            "task-failure-rotation",
            interval_minutes=10,
            desired_device_count=1,
            rotation_advance_policy="failure_only",
            start_now=True,
        )

        first = service.run_task_round("task-failure-rotation", force=True)
        second = service.run_task_round("task-failure-rotation", force=True)
        record = service.get_task_record("task-failure-rotation")

        self.assertEqual(first.round_record["assigned_device_ids"], ["device-1"])
        self.assertEqual(second.round_record["assigned_device_ids"], ["device-1"])
        self.assertEqual(record.rotation_cursor, 1)
        self.assertEqual(record.rotation_advance_count, 1)

    def test_run_task_round_uses_backup_device_when_primary_unavailable(self) -> None:
        service, task_repo, device_service = self._build_service(
            devices=[
                self._device("device-primary", DeviceConnectionState.OFFLINE, DeviceAvailabilityState.ERROR),
                self._device("device-backup", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE),
            ],
            outcomes=[[{"status": "success"}]],
        )
        task = TaskDefinition(
            task_id="task-1",
            task_name="Unattended Task",
            target_app=TaskTargetApp(package_name="com.example.app"),
            selected_device_ids=["device-primary"],
        )
        task_repo.add(task)

        service.configure_task(
            "task-1",
            interval_minutes=30,
            backup_device_ids=["device-backup"],
            start_now=True,
        )

        result = service.run_task_round("task-1", force=True)

        self.assertTrue(result.executed)
        self.assertEqual(result.round_record["assigned_device_ids"], ["device-backup"])
        self.assertEqual(result.round_record["unavailable_device_ids"], ["device-primary"])
        self.assertEqual(len(result.round_record["replacement_events"]), 1)
        primary = device_service.require_device("device-primary")
        self.assertEqual(primary.metadata["automation_health"]["failure_streak"], 1)

    def test_repeated_failures_quarantine_device(self) -> None:
        service, task_repo, device_service = self._build_service(
            devices=[self._device("device-1", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE)],
            outcomes=[
                [{"status": "failed", "exit_reason": "device_offline"}],
                [{"status": "failed", "exit_reason": "device_offline"}],
            ],
        )
        task = TaskDefinition(
            task_id="task-2",
            task_name="Quarantine Task",
            target_app=TaskTargetApp(package_name="com.example.app"),
            selected_device_ids=["device-1"],
        )
        task_repo.add(task)

        service.configure_task(
            "task-2",
            interval_minutes=15,
            failure_threshold=2,
            start_now=True,
        )
        service.run_task_round("task-2", force=True)
        service.run_task_round("task-2", force=True)

        device = device_service.require_device("device-1")
        self.assertEqual(device.availability_state, DeviceAvailabilityState.QUARANTINED)
        self.assertEqual(device.metadata["automation_health"]["failure_streak"], 2)
        patrol = service.build_patrol_summary()
        self.assertEqual(patrol.quarantined_device_count, 1)
        self.assertEqual(list(patrol.quarantined_device_ids), ["device-1"])

    def test_patrol_summary_reports_failure_offline_recovery_and_quarantine(self) -> None:
        service, task_repo, _ = self._build_service(
            devices=[
                self._device("device-a-primary", DeviceConnectionState.OFFLINE, DeviceAvailabilityState.ERROR),
                self._device("device-a-backup", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE),
                self._device("device-b-primary", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE),
            ],
            outcomes=[
                [{"status": "success", "recovered_after_disconnect": True}],
                [{"status": "failed", "exit_reason": "device_offline"}],
            ],
        )
        task_repo.add(
            TaskDefinition(
                task_id="task-a",
                task_name="Recovery Task",
                target_app=TaskTargetApp(package_name="com.example.a"),
                selected_device_ids=["device-a-primary"],
            )
        )
        task_repo.add(
            TaskDefinition(
                task_id="task-b",
                task_name="Offline Task",
                target_app=TaskTargetApp(package_name="com.example.b"),
                selected_device_ids=["device-b-primary"],
            )
        )

        service.configure_task(
            "task-a",
            interval_minutes=60,
            backup_device_ids=["device-a-backup"],
            start_now=True,
        )
        service.configure_task(
            "task-b",
            interval_minutes=60,
            failure_threshold=1,
            start_now=True,
        )

        summary = service.run_due_tasks(force=False)

        self.assertEqual(summary.executed_task_count, 2)
        self.assertEqual(summary.metrics["instance_count"], 2)
        self.assertAlmostEqual(summary.failed_rate, 0.5)
        self.assertGreater(summary.offline_rate, 0.0)
        self.assertAlmostEqual(summary.recovery_success_rate, 1.0)
        self.assertEqual(summary.quarantined_device_count, 1)
        self.assertIn("device-b-primary", summary.quarantined_device_ids)

    def test_patrol_probes_quarantined_device_and_recovers_it_when_online(self) -> None:
        device = self._device("device-1", DeviceConnectionState.OFFLINE, DeviceAvailabilityState.QUARANTINED)
        device.metadata["automation_health"] = {
            "failure_streak": 3,
            "quarantined_at": utcnow().isoformat(),
        }
        discovery = _MapDiscoveryAdapter(
            {
                "device-1": DeviceDescriptor(
                    serial="device-1",
                    status="device",
                    model="Recovered Device",
                    brand="Example",
                )
            }
        )
        service, task_repo, device_service = self._build_service(
            devices=[device],
            outcomes=[[{"status": "success"}]],
            discovery_adapter=discovery,
        )
        task_repo.add(
            TaskDefinition(
                task_id="task-recover",
                task_name="Recover Task",
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=["device-1"],
            )
        )
        service.configure_task(
            "task-recover",
            interval_minutes=10,
            failure_threshold=2,
            start_now=True,
        )

        summary = service.run_due_tasks(force=False)

        recovered = device_service.require_device("device-1")
        self.assertEqual(recovered.availability_state, DeviceAvailabilityState.IDLE)
        self.assertEqual(recovered.connection_state, DeviceConnectionState.ONLINE)
        self.assertEqual(summary.quarantine_probe_attempt_count, 1)
        self.assertEqual(summary.quarantine_probe_recovered_count, 1)
        self.assertEqual(list(summary.recovered_device_ids), ["device-1"])
        self.assertEqual(summary.quarantined_device_count, 0)
        self.assertEqual(summary.executed_task_count, 1)
        self.assertEqual(summary.executed_rounds[0]["assigned_device_ids"], ["device-1"])

    def test_patrol_respects_quarantine_probe_cooldown(self) -> None:
        device = self._device("device-1", DeviceConnectionState.OFFLINE, DeviceAvailabilityState.QUARANTINED)
        device.metadata["automation_health"] = {
            "failure_streak": 3,
            "quarantined_at": utcnow().isoformat(),
            "last_probe_at": utcnow().isoformat(),
        }
        discovery = _MapDiscoveryAdapter(
            {
                "device-1": DeviceDescriptor(
                    serial="device-1",
                    status="device",
                    model="Recovered Device",
                    brand="Example",
                )
            }
        )
        service, task_repo, device_service = self._build_service(
            devices=[device],
            outcomes=[],
            discovery_adapter=discovery,
        )
        task_repo.add(
            TaskDefinition(
                task_id="task-cooldown",
                task_name="Cooldown Task",
                target_app=TaskTargetApp(package_name="com.example.app"),
                selected_device_ids=["device-1"],
            )
        )
        service.configure_task(
            "task-cooldown",
            interval_minutes=10,
            failure_threshold=2,
            start_now=True,
        )

        summary = service.run_due_tasks(force=False)

        cooled = device_service.require_device("device-1")
        self.assertEqual(cooled.availability_state, DeviceAvailabilityState.QUARANTINED)
        self.assertEqual(summary.quarantine_probe_attempt_count, 0)
        self.assertEqual(summary.quarantine_probe_skipped_count, 1)
        self.assertEqual(summary.quarantine_probe_recovered_count, 0)
        self.assertEqual(summary.executed_task_count, 0)
        self.assertEqual(summary.skipped_task_count, 1)
        self.assertEqual(summary.executed_rounds[0]["status"], "no_schedulable_devices")

    def test_build_daily_report_aggregates_recent_rounds(self) -> None:
        service, task_repo, _ = self._build_service(
            devices=[
                self._device("device-a-primary", DeviceConnectionState.OFFLINE, DeviceAvailabilityState.ERROR),
                self._device("device-a-backup", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE),
                self._device("device-b-primary", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE),
            ],
            outcomes=[
                [{"status": "success", "recovered_after_disconnect": True}],
                [{"status": "failed", "exit_reason": "device_offline"}],
            ],
        )
        task_repo.add(
            TaskDefinition(
                task_id="task-daily-a",
                task_name="Daily Recovery Task",
                target_app=TaskTargetApp(package_name="com.example.a"),
                selected_device_ids=["device-a-primary"],
            )
        )
        task_repo.add(
            TaskDefinition(
                task_id="task-daily-b",
                task_name="Daily Failure Task",
                target_app=TaskTargetApp(package_name="com.example.b"),
                selected_device_ids=["device-b-primary"],
            )
        )

        service.configure_task(
            "task-daily-a",
            interval_minutes=60,
            backup_device_ids=["device-a-backup"],
            start_now=True,
        )
        service.configure_task(
            "task-daily-b",
            interval_minutes=60,
            failure_threshold=1,
            start_now=True,
        )

        service.run_due_tasks(force=False)
        report = service.build_daily_report()

        self.assertEqual(report.task_count, 2)
        self.assertEqual(report.active_task_count, 2)
        self.assertEqual(report.round_count, 2)
        self.assertEqual(report.executed_round_count, 2)
        self.assertEqual(report.failed_round_count, 1)
        self.assertGreater(report.device_online_rate, 0.0)
        self.assertAlmostEqual(report.recovery_success_rate, 1.0)
        self.assertEqual(report.quarantined_device_count, 1)
        self.assertEqual(len(report.task_summaries), 2)
        self.assertEqual(report.metrics["instance_count"], 2)

    def test_build_weekly_report_aggregates_recent_rounds(self) -> None:
        service, task_repo, _ = self._build_service(
            devices=[
                self._device("device-weekly-a", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE),
                self._device("device-weekly-b", DeviceConnectionState.ONLINE, DeviceAvailabilityState.IDLE),
            ],
            outcomes=[
                [{"status": "success"}],
                [{"status": "failed", "exit_reason": "device_offline"}],
            ],
        )
        task_repo.add(
            TaskDefinition(
                task_id="task-weekly-a",
                task_name="Weekly Success Task",
                target_app=TaskTargetApp(package_name="com.example.weekly.a"),
                selected_device_ids=["device-weekly-a"],
            )
        )
        task_repo.add(
            TaskDefinition(
                task_id="task-weekly-b",
                task_name="Weekly Failure Task",
                target_app=TaskTargetApp(package_name="com.example.weekly.b"),
                selected_device_ids=["device-weekly-b"],
            )
        )

        service.configure_task("task-weekly-a", interval_minutes=60, start_now=True)
        service.configure_task("task-weekly-b", interval_minutes=60, failure_threshold=1, start_now=True)

        service.run_due_tasks(force=False)
        report = service.build_weekly_report(report_date=utcnow().date().isoformat())
        anchor_date = utcnow().date()
        week_start = anchor_date - timedelta(days=anchor_date.weekday())

        self.assertEqual(report.week_key, f"{anchor_date.isocalendar().year}-W{anchor_date.isocalendar().week:02d}")
        self.assertEqual(report.week_start_date, week_start.isoformat())
        self.assertEqual(report.week_end_date, (week_start + timedelta(days=6)).isoformat())
        self.assertEqual(report.task_count, 2)
        self.assertEqual(report.active_task_count, 2)
        self.assertEqual(report.round_count, 2)
        self.assertEqual(report.failed_round_count, 1)
        self.assertGreaterEqual(report.active_day_count, 1)
        self.assertEqual(len(report.daily_summaries), 1)
        self.assertEqual(report.daily_summaries[0]["round_count"], 2)
        self.assertEqual(len(report.task_summaries), 2)
        self.assertEqual(report.metrics["instance_count"], 2)

    @staticmethod
    def _device(device_id: str, connection_state: DeviceConnectionState, availability_state: DeviceAvailabilityState) -> Device:
        return Device(
            device_id=device_id,
            serial=device_id,
            connection_state=connection_state,
            availability_state=availability_state,
        )

    def _build_service(
        self,
        *,
        devices: list[Device],
        outcomes: list[list[dict[str, object]]],
        discovery_adapter: DeviceDiscoveryAdapter | None = None,
    ):
        task_repository = InMemoryTaskRepository()
        run_repository = InMemoryRunRepository()
        instance_repository = InMemoryInstanceRepository()
        device_repository = InMemoryDeviceRepository()
        device_map = {device.device_id: device for device in devices}
        for device in devices:
            device_repository.add(device)
        device_service = DeviceService(
            repository=device_repository,
            discovery_adapter=discovery_adapter or _NullDiscoveryAdapter(),
        )
        execution_service = ExecutionService(
            planner=StaticDevicePlanner(devices=device_map),
            run_factory=DomainTaskRunFactory(),
            instance_factory=DomainExecutionInstanceFactory(devices=device_map),
            run_repository=run_repository,
            instance_repository=instance_repository,
        )
        fake_run_execution_service = _FakeRunExecutionService(
            task_repository=task_repository,
            run_repository=run_repository,
            instance_repository=instance_repository,
            execution_service=execution_service,
            outcomes=outcomes,
        )
        service = UnattendedService(
            task_repository=task_repository,
            device_service=device_service,
            execution_service=execution_service,
            run_execution_service=fake_run_execution_service,
        )
        return service, task_repository, device_service


if __name__ == "__main__":
    unittest.main()
