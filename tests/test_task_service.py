from __future__ import annotations

import unittest

from stability.app import TaskService
from stability.domain import AppError, SamplingConfig, TaskDefinition, TaskTargetApp, TaskTemplateType
from stability.repositories import InMemoryTaskRepository


class _EventSink:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def publish_event(self, **kwargs):
        self.events.append(dict(kwargs))
        return kwargs


class TaskServiceTest(unittest.TestCase):
    def test_create_task_uses_scenario_registry_validation(self) -> None:
        service = TaskService(repository=InMemoryTaskRepository())

        with self.assertRaises(AppError) as ctx:
            service.create_task(
                TaskDefinition(
                    task_id="task-invalid",
                    task_name="Invalid",
                    template_type=TaskTemplateType.COLD_START_LOOP,
                    target_app=TaskTargetApp(package_name="com.example.app"),
                    task_params={"loop_count": "bad"},
                    sampling_config=SamplingConfig(enabled_metrics=["gpu"]),
                )
            )

        self.assertIn(ctx.exception.code, {"invalid_task_params", "unsupported_metric"})

    def test_archive_task_hides_from_default_lists_and_records_audit_event(self) -> None:
        sink = _EventSink()
        service = TaskService(repository=InMemoryTaskRepository(), audit_event_sink=sink)
        service.create_task(
            TaskDefinition(
                task_id="task-archive",
                task_name="Archive Me",
                template_type=TaskTemplateType.COLD_START_LOOP,
                target_app=TaskTargetApp(package_name="com.example.app"),
            )
        )

        result = service.archive_task(
            "task-archive",
            actor_id="tester",
            reason="临时任务已结束。",
            audit_source={
                "audit_event_id": "audit-event-1",
                "request_id": "request-1",
                "resolved_identity_id": "identity-1",
                "resolved_session_id": "session-1",
                "auth_mechanism": "session_token",
            },
        )

        self.assertEqual(result.audit_event["audit_event_id"], "audit-event-1")
        self.assertEqual(result.audit_event["actor_id"], "tester")
        self.assertEqual(result.audit_event["identity_id"], "identity-1")
        self.assertEqual(service.list_tasks(), [])
        self.assertEqual(len(service.list_tasks(include_archived=True)), 1)
        archived = service.list_task_summaries(include_archived=True)[0]
        self.assertTrue(archived["archived"])
        self.assertTrue(archived["hidden"])
        self.assertEqual(archived["archived_by"], "tester")
        self.assertEqual(archived["archive_reason"], "临时任务已结束。")
        self.assertEqual(sink.events[0]["event_type"], "task.archived")
        self.assertEqual(sink.events[0]["target_id"], "task-archive")


if __name__ == "__main__":
    unittest.main()
