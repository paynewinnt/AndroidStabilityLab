from __future__ import annotations

import json
import os
import time
from dataclasses import replace
from datetime import datetime
from typing import Any, Mapping, Sequence

from stability.domain import IntegrationDeliveryWorkerStatus
from stability.domain.value_objects import utcnow


class WorkerMixin:
    @staticmethod
    def _utcnow() -> datetime:
        return utcnow()

    def get_worker_status(self) -> IntegrationDeliveryWorkerStatus:
        if not self._worker_status_path.exists():
            return IntegrationDeliveryWorkerStatus(worker_name="integration_outbox_worker")
        try:
            payload = json.loads(self._worker_status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return IntegrationDeliveryWorkerStatus(worker_name="integration_outbox_worker")
        if not isinstance(payload, Mapping):
            return IntegrationDeliveryWorkerStatus(worker_name="integration_outbox_worker")
        return self._worker_status_from_payload(payload)

    def _save_worker_status(self, item: IntegrationDeliveryWorkerStatus) -> None:
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._worker_status_path.write_text(
            json.dumps(self._worker_status_payload(item), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def run_delivery_worker(
        self,
        *,
        webhook_names: Sequence[str] = (),
        event_types: Sequence[str] = (),
        limit_per_webhook: int = 20,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current_time = now or utcnow()
        previous = self.get_worker_status()
        started = replace(
            previous,
            status="running",
            last_started_at=current_time,
            last_error="",
        )
        self._save_worker_status(started)
        targets = [item for item in self.list_webhooks() if not webhook_names or item.name in set(webhook_names)]
        deliveries: list[dict[str, Any]] = []
        total_attempted = 0
        total_delivered = 0
        total_failed = 0
        total_retry = 0
        total_dead_letter = 0
        total_deduplicated = 0
        total_receipts = 0
        last_delivery_receipt_id = str(getattr(previous, "last_delivery_receipt_id", "") or "")
        try:
            for webhook in targets:
                result = self.deliver_pending_events(
                    webhook_name=webhook.name,
                    limit=limit_per_webhook,
                    event_types=event_types,
                    now=current_time,
                )
                deliveries.append(dict(result))
                total_attempted += int(result.get("attempted_count", 0) or 0)
                total_delivered += int(result.get("delivered_count", 0) or 0)
                total_failed += int(result.get("failed_count", 0) or 0)
                total_retry += int(result.get("retry_count", 0) or 0)
                total_dead_letter += int(result.get("dead_letter_count", result.get("dead_lettered_count", 0)) or 0)
                total_deduplicated += int(result.get("deduplicated_count", 0) or 0)
                total_receipts += int(result.get("receipt_count", 0) or 0)
                receipt_ids = [str(item) for item in (result.get("delivery_receipt_ids", []) or ()) if str(item).strip()]
                if receipt_ids:
                    last_delivery_receipt_id = receipt_ids[-1]
            finished = replace(
                started,
                status="idle",
                last_finished_at=current_time,
                last_success_at=current_time,
                run_count=int(previous.run_count) + 1,
                delivered_count=int(previous.delivered_count) + total_delivered,
                failed_count=int(previous.failed_count) + total_failed,
                last_delivery_receipt_id=last_delivery_receipt_id,
                last_run_summary={
                    "webhook_count": len(targets),
                    "deliveries": deliveries,
                    "event_types": list(event_types),
                    "aggregate": {
                        "attempted_count": total_attempted,
                        "delivered_count": total_delivered,
                        "failed_count": total_failed,
                        "retry_count": total_retry,
                        "dead_letter_count": total_dead_letter,
                        "dead_lettered_count": total_dead_letter,
                        "deduplicated_count": total_deduplicated,
                        "receipt_count": total_receipts,
                    },
                },
            )
            self._save_worker_status(finished)
            return {
                "worker": self._worker_status_payload(finished),
                "delivery_rounds": deliveries,
            }
        except Exception as exc:
            failed = replace(
                started,
                status="failed",
                last_finished_at=current_time,
                last_error=str(exc),
                run_count=int(previous.run_count) + 1,
            )
            self._save_worker_status(failed)
            raise

    def run_delivery_daemon(
        self,
        *,
        webhook_names: Sequence[str] = (),
        event_types: Sequence[str] = (),
        limit_per_webhook: int = 20,
        interval_seconds: int | None = None,
        max_rounds: int = 0,
        max_runtime_seconds: int = 0,
        stop_when_idle: bool = False,
        chain_name: str = "integration_outbox",
    ) -> dict[str, Any]:
        started_at = utcnow()
        interval = max(int(interval_seconds if interval_seconds is not None else self._delivery_interval), 0)
        target_webhooks = tuple(str(item).strip() for item in webhook_names if str(item).strip())
        target_event_types = tuple(str(item).strip() for item in event_types if str(item).strip())
        rounds_executed = 0
        idle_stop = False
        per_round: list[dict[str, Any]] = []
        aggregate = {
            "attempted_count": 0,
            "delivered_count": 0,
            "failed_count": 0,
            "retry_count": 0,
            "dead_letter_count": 0,
            "dead_lettered_count": 0,
            "skipped_count": 0,
            "deduplicated_count": 0,
            "receipt_count": 0,
            "alert_emitted_count": 0,
            "remaining_pending_count": 0,
        }
        heartbeat_status = replace(
            self.get_worker_status(),
            status="running",
            worker_mode="daemon",
            daemon_enabled=True,
            daemon_pid=os.getpid(),
            daemon_heartbeat_at=started_at,
            configured_webhooks=target_webhooks,
            configured_event_types=target_event_types,
            schedule_interval_seconds=interval,
            chain_name=chain_name.strip() or "integration_outbox",
        )
        self._save_worker_status(heartbeat_status)
        while True:
            current_time = utcnow()
            round_result = self.run_delivery_worker(
                webhook_names=target_webhooks,
                event_types=target_event_types,
                limit_per_webhook=limit_per_webhook,
                now=current_time,
            )
            deliveries = [dict(item) for item in (round_result.get("delivery_rounds") or ()) if isinstance(item, Mapping)]
            round_attempted = sum(int(item.get("attempted_count", 0) or 0) for item in deliveries)
            round_delivered = sum(int(item.get("delivered_count", 0) or 0) for item in deliveries)
            round_failed = sum(int(item.get("failed_count", 0) or 0) for item in deliveries)
            round_retry = sum(int(item.get("retry_count", 0) or 0) for item in deliveries)
            round_dead_letter = sum(
                int(item.get("dead_letter_count", item.get("dead_lettered_count", 0)) or 0)
                for item in deliveries
            )
            round_deduplicated = sum(int(item.get("deduplicated_count", 0) or 0) for item in deliveries)
            round_receipts = sum(int(item.get("receipt_count", 0) or 0) for item in deliveries)
            round_remaining = sum(int(item.get("remaining_pending_count", 0) or 0) for item in deliveries)
            rounds_executed += 1
            per_round.append(
                {
                    "round_index": rounds_executed,
                    "started_at": current_time.isoformat(),
                    "attempted_count": round_attempted,
                    "delivered_count": round_delivered,
                    "failed_count": round_failed,
                    "retry_count": round_retry,
                    "dead_letter_count": round_dead_letter,
                    "dead_lettered_count": round_dead_letter,
                    "deduplicated_count": round_deduplicated,
                    "receipt_count": round_receipts,
                    "remaining_pending_count": round_remaining,
                    "results": deliveries,
                    "worker": round_result.get("worker"),
                }
            )
            for item in deliveries:
                for key in aggregate:
                    aggregate[key] += int(item.get(key, 0) or 0)
            aggregate["remaining_pending_count"] = round_remaining
            latest_worker = self.get_worker_status()
            self._save_worker_status(
                replace(
                    latest_worker,
                    worker_mode="daemon",
                    daemon_enabled=True,
                    daemon_pid=os.getpid(),
                    daemon_heartbeat_at=current_time,
                    configured_webhooks=target_webhooks,
                    configured_event_types=target_event_types,
                    schedule_interval_seconds=interval,
                    chain_name=chain_name.strip() or "integration_outbox",
                )
            )
            if stop_when_idle and round_attempted <= 0 and round_remaining <= 0:
                idle_stop = True
                break
            if max_rounds > 0 and rounds_executed >= max_rounds:
                break
            if max_runtime_seconds > 0 and int((utcnow() - started_at).total_seconds()) >= max_runtime_seconds:
                break
            if interval > 0:
                time.sleep(interval)
            else:
                break
        finished = replace(
            self.get_worker_status(),
            status="idle",
            worker_mode="daemon",
            daemon_enabled=False,
            daemon_pid=None,
            daemon_heartbeat_at=utcnow(),
            configured_webhooks=target_webhooks,
            configured_event_types=target_event_types,
            schedule_interval_seconds=interval,
            chain_name=chain_name.strip() or "integration_outbox",
            last_run_summary={
                "mode": "daemon",
                "rounds_executed": rounds_executed,
                "stopped_when_idle": idle_stop,
                "aggregate": dict(aggregate),
            },
        )
        self._save_worker_status(finished)
        return {
            "mode": "daemon",
            "selected_webhooks": list(target_webhooks),
            "event_types": list(target_event_types),
            "rounds_executed": rounds_executed,
            "stopped_when_idle": idle_stop,
            "aggregate": aggregate,
            "rounds": per_round,
            "worker": self._worker_status_payload(finished),
        }

    def run_im_notification_worker(
        self,
        *,
        webhook_names: Sequence[str] = (),
        limit_per_webhook: int = 20,
        interval_seconds: int | None = None,
        max_rounds: int = 0,
        max_runtime_seconds: int = 0,
        stop_when_idle: bool = False,
        daemon: bool = True,
    ) -> dict[str, Any]:
        event_types = self.im_notification_event_types()
        if daemon:
            return self.run_delivery_daemon(
                webhook_names=webhook_names,
                event_types=event_types,
                limit_per_webhook=limit_per_webhook,
                interval_seconds=interval_seconds,
                max_rounds=max_rounds,
                max_runtime_seconds=max_runtime_seconds,
                stop_when_idle=stop_when_idle,
                chain_name="im_notification",
            )
        return self.run_delivery_worker(
            webhook_names=webhook_names,
            event_types=event_types,
            limit_per_webhook=limit_per_webhook,
        )

    def run_feishu_notify_worker(
        self,
        *,
        webhook_names: Sequence[str] = (),
        limit_per_webhook: int = 20,
        interval_seconds: int | None = None,
        max_rounds: int = 0,
        max_runtime_seconds: int = 0,
        stop_when_idle: bool = False,
        daemon: bool = True,
    ) -> dict[str, Any]:
        event_types = self.feishu_bot_event_types()
        target_webhook_names = tuple(str(item).strip() for item in webhook_names if str(item).strip())
        if not target_webhook_names:
            target_webhook_names = tuple(
                str(getattr(item, "name", "") or "")
                for item in self.list_webhooks()
                if str(getattr(item, "delivery_channel", "") or "").strip() == "feishu_bot"
                and str(getattr(item, "name", "") or "").strip()
            )
        if daemon:
            return self.run_delivery_daemon(
                webhook_names=target_webhook_names,
                event_types=event_types,
                limit_per_webhook=limit_per_webhook,
                interval_seconds=interval_seconds,
                max_rounds=max_rounds,
                max_runtime_seconds=max_runtime_seconds,
                stop_when_idle=stop_when_idle,
                chain_name="feishu_bot",
            )
        return self.run_delivery_worker(
            webhook_names=target_webhook_names,
            event_types=event_types,
            limit_per_webhook=limit_per_webhook,
        )

    def run_defect_sync_worker(
        self,
        *,
        webhook_names: Sequence[str] = (),
        limit_per_webhook: int = 20,
        interval_seconds: int | None = None,
        max_rounds: int = 0,
        max_runtime_seconds: int = 0,
        stop_when_idle: bool = False,
        daemon: bool = True,
    ) -> dict[str, Any]:
        event_types = self.defect_sync_event_types()
        if daemon:
            return self.run_delivery_daemon(
                webhook_names=webhook_names,
                event_types=event_types,
                limit_per_webhook=limit_per_webhook,
                interval_seconds=interval_seconds,
                max_rounds=max_rounds,
                max_runtime_seconds=max_runtime_seconds,
                stop_when_idle=stop_when_idle,
                chain_name="defect_sync",
            )
        return self.run_delivery_worker(
            webhook_names=webhook_names,
            event_types=event_types,
            limit_per_webhook=limit_per_webhook,
        )

    def run_release_sync_worker(
        self,
        *,
        webhook_names: Sequence[str] = (),
        limit_per_webhook: int = 20,
        interval_seconds: int = 300,
        max_rounds: int = 1,
        max_runtime_seconds: int = 0,
        stop_when_idle: bool = False,
        daemon: bool = True,
    ) -> dict[str, Any]:
        event_types = self.release_submission_event_types()
        if daemon:
            rounds = max(int(max_rounds), 1) if int(max_rounds) > 0 else 1
            return self.run_delivery_daemon(
                webhook_names=webhook_names,
                event_types=event_types,
                limit_per_webhook=max(int(limit_per_webhook), 0),
                interval_seconds=max(int(interval_seconds), 0),
                max_rounds=rounds,
                stop_when_idle=bool(stop_when_idle),
                max_runtime_seconds=max(int(max_runtime_seconds), 0),
                chain_name="release_submission",
            )
        return self.run_delivery_worker(
            webhook_names=webhook_names,
            event_types=event_types,
            limit_per_webhook=limit_per_webhook,
        )

    def replay_dead_lettered_events(
        self,
        *,
        webhook_name: str,
        event_ids: Sequence[str] = (),
        limit: int = 20,
        now: datetime | None = None,
        replayed_by: str = "system:replay",
    ) -> dict[str, Any]:
        target_name = webhook_name.strip()
        if not target_name:
            raise ValueError("webhook_name is required.")
        event_id_filter = {str(item).strip() for item in event_ids if str(item).strip()}
        current_time = now or utcnow()
        registry = self._load_event_registry()
        replayed_event_ids: list[str] = []
        replay_receipt_ids: list[str] = []
        operator_receipt_ids: list[str] = []
        updated_registry: list[dict[str, Any]] = []
        replayed = 0
        for raw_event in registry:
            event = self._event_from_payload(raw_event)
            if event.delivery_status != "dead_letter":
                updated_registry.append(self._event_payload(event))
                continue
            if event_id_filter and event.event_id not in event_id_filter:
                updated_registry.append(self._event_payload(event))
                continue
            if limit > 0 and replayed >= limit:
                updated_registry.append(self._event_payload(event))
                continue
            replayed += 1
            replayed_event_ids.append(event.event_id)
            replay_receipt = self._replay_receipt(
                event=event,
                webhook_name=target_name,
                replayed_by=replayed_by,
                current_time=current_time,
            )
            operator_receipt = self._operator_receipt(
                event=event,
                webhook_name=target_name,
                action="replay_dead_letter",
                operator_id=replayed_by,
                current_time=current_time,
                notes="Dead-letter replayed back into pending delivery.",
            )
            replay_receipt_ids.append(replay_receipt.receipt_id)
            operator_receipt_ids.append(operator_receipt.receipt_id)
            updated_registry.append(
                self._event_payload(
                    replace(
                        event,
                        delivery_status="pending",
                        last_attempt_at=None,
                        delivered_at=None,
                        next_retry_at=current_time,
                        dead_lettered_at=None,
                        last_error="",
                        last_response_code=None,
                        alert_status="none",
                        retry_backoff_seconds=0,
                        replay_receipts=tuple(list(event.replay_receipts) + [replay_receipt]),
                        operator_receipts=tuple(list(event.operator_receipts) + [operator_receipt]),
                    )
                )
            )
        self._save_registry(self._events_path, updated_registry)
        if replayed:
            worker = self.get_worker_status()
            self._save_worker_status(
                replace(
                    worker,
                    replay_count=int(worker.replay_count) + replayed,
                    last_operator_receipt_id=operator_receipt_ids[-1] if operator_receipt_ids else str(getattr(worker, "last_operator_receipt_id", "") or ""),
                    last_run_summary={
                        **dict(worker.last_run_summary or {}),
                        "last_replay": {
                            "webhook_name": target_name,
                            "replayed_event_ids": replayed_event_ids,
                            "replayed_count": replayed,
                        },
                    },
                )
            )
        return {
            "webhook_name": target_name,
            "replayed_count": replayed,
            "replayed_event_ids": replayed_event_ids,
            "replay_receipt_ids": replay_receipt_ids,
            "operator_receipt_ids": operator_receipt_ids,
            "remaining_dead_letter_count": sum(
                1
                for item in updated_registry
                if str(item.get("delivery_status", "") or "") == "dead_letter"
            ),
        }
