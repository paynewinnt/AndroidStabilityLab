from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any


class _FakeIntegrationOutboxService:
    def __init__(self) -> None:
        self._events: list[SimpleNamespace] = []
        self._webhooks: list[SimpleNamespace] = []
        self._delivery_interval = 300
        self._retry_delay = 300
        self._max_retry_delay = 3600
        self._dead_letter_threshold = 5
        self._retry_alert_threshold = 3
        self._worker_status = SimpleNamespace(
            worker_name="integration_outbox_worker",
            status="idle",
            last_started_at=None,
            last_finished_at=None,
            last_success_at=None,
            last_error="",
            run_count=0,
            delivered_count=0,
            failed_count=0,
            replay_count=0,
            last_run_summary={},
        )

    def publish_event(
        self,
        *,
        event_type: str,
        target_type: str,
        target_id: str,
        created_by: str,
        session_source: str = "",
        audit_source=None,
        payload=None,
    ):
        event = SimpleNamespace(
            event_id=f"evt_{len(self._events) + 1}",
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            created_at=None,
            created_by=created_by,
            session_source=session_source,
            audit_source=dict(audit_source or {}),
            payload=dict(payload or {}),
            delivery_status="pending",
            attempt_count=0,
            last_attempt_at=None,
            delivered_at=None,
            last_error="",
            next_retry_at=None,
            signature="",
            retry_backoff_seconds=0,
            last_response_code=None,
            dead_lettered_at=None,
            alert_status="none",
            alert_count=0,
            last_alert_at=None,
        )
        self._events.append(event)
        return event

    def list_events(self, *, limit: int = 50):
        items = list(reversed(self._events))
        return items[:limit] if limit > 0 else items

    def list_webhooks(self):
        return tuple(self._webhooks)

    @staticmethod
    def im_notification_event_types():
        return (
            "issue.assigned",
            "issue.transitioned",
            "issue.commented",
            "admission_case.updated",
            "outbox.retry_alert",
        )

    @staticmethod
    def defect_sync_event_types():
        return (
            "issue.defect_create_requested",
            "issue.defect_linked",
            "issue.defect_status_synced",
            "outbox.retry_alert",
        )

    @staticmethod
    def release_submission_event_types():
        return (
            "release_submission.created",
            "release_submission.execution_updated",
            "release_submission.admission_synced",
        )

    def get_worker_status(self):
        return self._worker_status

    def register_webhook(
        self,
        *,
        name: str,
        url: str,
        subscribed_event_types: tuple[str, ...] = (),
        created_by: str = "",
        secret_hint: str = "",
        signing_secret: str = "",
        signature_key_id: str = "v1",
        accepted_signature_key_ids: tuple[str, ...] = (),
        failure_policy: str = "retryable_http",
        delivery_channel: str = "generic",
    ):
        webhook = SimpleNamespace(
            webhook_id=f"webhook_{len(self._webhooks) + 1}",
            name=name,
            url=url,
            subscribed_event_types=tuple(subscribed_event_types),
            created_at=datetime(2025, 7, 23, 10, 0, 0),
            created_by=created_by,
            secret_hint=secret_hint,
            signature_key_id=signature_key_id,
            accepted_signature_key_ids=tuple(accepted_signature_key_ids),
            failure_policy=failure_policy,
            delivery_channel=delivery_channel,
        )
        self._webhooks.append(webhook)
        return webhook

    def register_im_webhook(
        self,
        *,
        name: str,
        url: str,
        created_by: str,
        secret_hint: str = "",
        signing_secret: str = "",
        signature_key_id: str = "v1",
        accepted_signature_key_ids: tuple[str, ...] = (),
        failure_policy: str = "retryable_http",
        subscribed_event_types: tuple[str, ...] = (),
    ):
        return self.register_webhook(
            name=name,
            url=url,
            subscribed_event_types=subscribed_event_types or self.im_notification_event_types(),
            created_by=created_by,
            secret_hint=secret_hint,
            signing_secret=signing_secret,
            signature_key_id=signature_key_id,
            accepted_signature_key_ids=accepted_signature_key_ids,
            failure_policy=failure_policy,
            delivery_channel="im_notify",
        )

    def register_defect_webhook(
        self,
        *,
        name: str,
        url: str,
        created_by: str,
        secret_hint: str = "",
        signing_secret: str = "",
        signature_key_id: str = "v1",
        accepted_signature_key_ids: tuple[str, ...] = (),
        failure_policy: str = "retryable_http",
        subscribed_event_types: tuple[str, ...] = (),
    ):
        return self.register_webhook(
            name=name,
            url=url,
            subscribed_event_types=subscribed_event_types or self.defect_sync_event_types(),
            created_by=created_by,
            secret_hint=secret_hint,
            signing_secret=signing_secret,
            signature_key_id=signature_key_id,
            accepted_signature_key_ids=accepted_signature_key_ids,
            failure_policy=failure_policy,
            delivery_channel="defect_sync",
        )

    def register_release_webhook(
        self,
        *,
        name: str,
        url: str,
        created_by: str,
        secret_hint: str = "",
        signing_secret: str = "",
        signature_key_id: str = "v1",
        accepted_signature_key_ids: tuple[str, ...] = (),
        failure_policy: str = "retryable_http",
        subscribed_event_types: tuple[str, ...] = (),
    ):
        return self.register_webhook(
            name=name,
            url=url,
            subscribed_event_types=subscribed_event_types or self.release_submission_event_types(),
            created_by=created_by,
            secret_hint=secret_hint,
            signing_secret=signing_secret,
            signature_key_id=signature_key_id,
            accepted_signature_key_ids=accepted_signature_key_ids,
            failure_policy=failure_policy,
            delivery_channel="release_submission",
        )

    def deliver_pending_events(
        self,
        *,
        webhook_name: str,
        event_types: tuple[str, ...] = (),
        limit: int = 20,
    ) -> dict[str, object]:
        selected_event_types = {str(item).strip() for item in event_types if str(item).strip()}
        delivered = []
        for event in self._events:
            if str(getattr(event, "delivery_status", "") or "pending") != "pending":
                continue
            if selected_event_types and str(getattr(event, "event_type", "") or "") not in selected_event_types:
                continue
            event.delivery_status = "delivered"
            event.attempt_count = int(getattr(event, "attempt_count", 0) or 0) + 1
            event.delivered_at = datetime(2025, 7, 23, 10, 0, 0)
            delivered.append(event.event_id)
        self._worker_status = SimpleNamespace(
            **{
                **self._worker_status.__dict__,
                "run_count": int(getattr(self._worker_status, "run_count", 0) or 0) + 1,
                "delivered_count": int(getattr(self._worker_status, "delivered_count", 0) or 0) + len(delivered),
                "last_run_summary": {
                    "webhook_name": webhook_name,
                    "delivered_count": len(delivered),
                    "event_types": sorted(selected_event_types),
                },
            }
        )
        return {
            "webhook_name": webhook_name,
            "delivered_count": len(delivered),
            "delivered_event_ids": delivered[:limit] if limit > 0 else delivered,
            "pending_count": sum(1 for event in self._events if str(getattr(event, "delivery_status", "") or "") == "pending"),
            "attempt_count": sum(int(getattr(event, "attempt_count", 0) or 0) for event in self._events),
        }

    def run_delivery_worker(self, *, webhook_names: tuple[str, ...], event_types: tuple[str, ...], limit_per_webhook: int, now=None):
        return {
            "worker": self._worker_status,
            "delivery_rounds": [],
        }

    def run_delivery_daemon(self, *, webhook_names: tuple[str, ...], event_types: tuple[str, ...], limit_per_webhook: int, rounds: int, interval_seconds: int, stop_when_idle: bool, daemon: bool, max_runtime_seconds: int, chain_name: str):
        return {
            "worker": self._worker_status,
            "delivery_rounds": [],
            "rounds_executed": rounds,
            "selected_webhooks": [item for item in webhook_names if str(item).strip()],
            "stop_when_idle": stop_when_idle,
        }

    def run_im_notification_worker(
        self,
        *,
        webhook_names: tuple[str, ...],
        limit_per_webhook: int,
        interval_seconds: int | None = None,
        max_rounds: int = 0,
        max_runtime_seconds: int = 0,
        stop_when_idle: bool = False,
        daemon: bool = True,
    ) -> dict[str, Any]:
        return {
            "mode": "daemon" if daemon else "single_round",
            "delivery_rounds": [],
            "rounds_executed": max_rounds or 1,
            "selected_webhooks": [item for item in webhook_names if str(item).strip()],
            "stop_when_idle": stop_when_idle,
            "interval_seconds": interval_seconds,
            "limit_per_webhook": limit_per_webhook,
            "max_runtime_seconds": max_runtime_seconds,
        }

    def run_defect_sync_worker(
        self,
        *,
        webhook_names: tuple[str, ...],
        limit_per_webhook: int,
        interval_seconds: int | None = None,
        max_rounds: int = 0,
        max_runtime_seconds: int = 0,
        stop_when_idle: bool = False,
        daemon: bool = True,
    ) -> dict[str, Any]:
        return {
            "mode": "daemon" if daemon else "single_round",
            "delivery_rounds": [],
            "rounds_executed": max_rounds or 1,
            "selected_webhooks": [item for item in webhook_names if str(item).strip()],
            "stop_when_idle": stop_when_idle,
            "interval_seconds": interval_seconds,
            "limit_per_webhook": limit_per_webhook,
            "max_runtime_seconds": max_runtime_seconds,
        }

    def run_release_sync_worker(
        self,
        *,
        webhook_names: tuple[str, ...],
        limit_per_webhook: int,
        interval_seconds: int | None = None,
        max_rounds: int = 0,
        max_runtime_seconds: int = 0,
        stop_when_idle: bool = False,
        daemon: bool = True,
    ) -> dict[str, Any]:
        return {
            "mode": "daemon" if daemon else "single_round",
            "delivery_rounds": [],
            "rounds_executed": max_rounds or 1,
            "selected_webhooks": [item for item in webhook_names if str(item).strip()],
            "stop_when_idle": stop_when_idle,
            "interval_seconds": interval_seconds,
            "limit_per_webhook": limit_per_webhook,
            "max_runtime_seconds": max_runtime_seconds,
        }

    def replay_dead_lettered_events(
        self,
        *,
        webhook_name: str,
        event_ids: tuple[str, ...],
        limit: int,
        now=None,
    ) -> dict[str, Any]:
        selected = {str(item).strip() for item in event_ids if str(item).strip()}
        replayed = []
        for event in self._events:
            if str(getattr(event, "delivery_status", "") or "") == "dead_letter":
                if selected and str(event.event_id) in selected:
                    event.delivery_status = "pending"
                    replayed.append(event.event_id)
        return {
            "webhook_name": webhook_name,
            "replayed_count": len(replayed),
            "replayed_event_ids": replayed[:limit] if limit > 0 else replayed,
            "remaining_dead_letter_count": sum(
                1
                for event in self._events
                if str(getattr(event, "delivery_status", "") or "") == "dead_letter"
            ),
        }


class _FakeReleaseSubmissionService:
    def __init__(self, outbox_service=None) -> None:
        self._outbox = outbox_service
        self._counter = 1
        self._records = {
            "release_submission_1": self._record(
                submission_id="release_submission_1",
                source_platform="release-center",
                source_request_id="REL-2026-001",
                package_name="com.hihonor.calculator",
                version_name="1.0.1",
                version_code="101",
                build_id="build-101",
                release_channel="beta",
                owner_team="android-client",
                submission_title="Release Submission com.hihonor.calculator 1.0.1",
                template_type="cold_start_loop",
                selected_device_ids=("device-1",),
                enabled_metrics=("cpu", "memory"),
                sampling_interval_seconds=5,
                monitoring_backend="solox",
                execute_immediately=True,
                submission_status="admission_synced",
                task_id="task-1",
                task_name="Calculator Cold Start",
                run_id="run-1",
                run_status="failed",
                report_paths={"instance-1": "runtime/report.md"},
                baseline_key="device_offline_default",
                admission_case_id="admission_case:device_offline_default:review_report_1",
                admission_status="open",
                admission_final_decision="conditional_pass",
                admission_error_code="CONDITIONAL_PASS",
                created_by="cli",
                updated_by="cli",
                metadata={"source": "seed"},
            )
        }

    @staticmethod
    def _record(**overrides):
        base_time = datetime(2025, 7, 23, 10, 0, 0)
        payload = {
            "submission_id": "",
            "source_platform": "",
            "source_request_id": "",
            "package_name": "",
            "version_name": "",
            "version_code": "",
            "build_id": "",
            "release_channel": "",
            "owner_team": "",
            "submission_title": "",
            "template_type": "cold_start_loop",
            "selected_device_ids": (),
            "enabled_metrics": (),
            "sampling_interval_seconds": 5,
            "monitoring_backend": "",
            "execute_immediately": False,
            "submission_status": "received",
            "task_id": "",
            "task_name": "",
            "run_id": "",
            "run_status": "",
            "report_paths": {},
            "baseline_key": "",
            "admission_case_id": "",
            "admission_status": "",
            "admission_final_decision": "",
            "admission_error_code": "",
            "created_at": base_time,
            "created_by": "cli",
            "updated_at": base_time,
            "updated_by": "cli",
            "metadata": {},
        }
        payload.update(overrides)
        return SimpleNamespace(**payload)

    def list_submissions(self, *, limit: int = 50):
        items = list(reversed(list(self._records.values())))
        return tuple(items[:limit] if limit > 0 else items)

    def get_submission(self, submission_id: str):
        key = str(submission_id or "").strip()
        if key not in self._records:
            raise ValueError(submission_id)
        return self._records[key]

    def create_submission(
        self,
        *,
        source_platform: str,
        source_request_id: str,
        package_name: str,
        version_name: str = "",
        version_code: str = "",
        build_id: str = "",
        release_channel: str = "",
        owner_team: str = "",
        submission_title: str = "",
        template_type: str = "",
        selected_device_ids=(),
        enabled_metrics=(),
        sampling_interval_seconds: int = 5,
        monitoring_backend: str = "",
        execute_immediately: bool = False,
        max_concurrency: int = 1,
        retry_count: int = 0,
        created_by: str = "",
        metadata=None,
        task_params=None,
    ):
        del max_concurrency, retry_count
        self._counter += 1
        submission_id = f"release_submission_{self._counter}"
        run_status = "success" if execute_immediately else "pending"
        record = self._record(
            submission_id=submission_id,
            source_platform=source_platform,
            source_request_id=source_request_id,
            package_name=package_name,
            version_name=version_name,
            version_code=version_code,
            build_id=build_id,
            release_channel=release_channel,
            owner_team=owner_team,
            submission_title=submission_title or f"Release Submission {package_name} {version_name or build_id or 'submission'}".strip(),
            template_type=template_type or "cold_start_loop",
            selected_device_ids=tuple(selected_device_ids or ()),
            enabled_metrics=tuple(enabled_metrics or ()),
            sampling_interval_seconds=int(sampling_interval_seconds or 0),
            monitoring_backend=monitoring_backend,
            execute_immediately=bool(execute_immediately),
            submission_status="executed" if execute_immediately else "run_created",
            task_id="task-write-1",
            task_name="Calculator Cold Start",
            run_id="run-write-1",
            run_status=run_status,
            report_paths={"instance-write-1": "runtime/report.md"} if execute_immediately else {},
            created_by=created_by or "web",
            updated_by=created_by or "web",
            metadata={**dict(metadata or {}), "task_params": dict(task_params or {})},
        )
        self._records[submission_id] = record
        if self._outbox is not None:
            self._outbox.publish_event(
                event_type="release_submission.created",
                target_type="release_submission",
                target_id=submission_id,
                created_by=record.created_by,
                payload={"submission_id": submission_id},
            )
            self._outbox.publish_event(
                event_type="release_submission.execution_updated",
                target_type="release_submission",
                target_id=submission_id,
                created_by=record.created_by,
                payload={"submission_id": submission_id, "run_status": run_status},
            )
        return record

    def sync_admission_result(
        self,
        *,
        submission_id: str,
        baseline_key: str,
        synced_by: str,
    ):
        record = self.get_submission(submission_id)
        updated = self._record(
            **{
                **record.__dict__,
                "baseline_key": baseline_key,
                "admission_case_id": f"admission_case:{baseline_key}:review_report_1",
                "admission_status": "open",
                "admission_final_decision": "conditional_pass",
                "admission_error_code": "CONDITIONAL_PASS",
                "submission_status": "admission_synced",
                "updated_by": synced_by or "web",
            }
        )
        self._records[submission_id] = updated
        if self._outbox is not None:
            self._outbox.publish_event(
                event_type="release_submission.admission_synced",
                target_type="release_submission",
                target_id=submission_id,
                created_by=updated.updated_by,
                payload={"submission_id": submission_id, "baseline_key": baseline_key},
            )
        return updated


