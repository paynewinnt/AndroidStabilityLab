from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from stability.domain import (
    IntegrationConsumerReceipt,
    IntegrationDeliveryWorkerStatus,
    IntegrationOperatorReceipt,
    IntegrationOutboxEvent,
    IntegrationReplayReceipt,
    WebhookSubscription,
)
from stability.domain.value_objects import utcnow


class SerializationMixin:
    @staticmethod
    def _event_payload(item: IntegrationOutboxEvent) -> dict[str, Any]:
        return {
            "event_id": item.event_id,
            "event_type": item.event_type,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "created_at": item.created_at.isoformat(),
            "created_by": item.created_by,
            "session_source": item.session_source,
            "audit_source": dict(item.audit_source),
            "payload": dict(item.payload),
            "idempotency_key": item.idempotency_key,
            "delivery_status": item.delivery_status,
            "attempt_count": int(item.attempt_count),
            "last_attempt_at": item.last_attempt_at.isoformat() if item.last_attempt_at else None,
            "delivered_at": item.delivered_at.isoformat() if item.delivered_at else None,
            "last_error": item.last_error,
            "next_retry_at": item.next_retry_at.isoformat() if item.next_retry_at else None,
            "signature": item.signature,
            "retry_backoff_seconds": int(item.retry_backoff_seconds),
            "last_response_code": item.last_response_code,
            "dead_lettered_at": item.dead_lettered_at.isoformat() if item.dead_lettered_at else None,
            "failure_category": item.failure_category,
            "alert_status": item.alert_status,
            "alert_count": int(item.alert_count),
            "last_alert_at": item.last_alert_at.isoformat() if item.last_alert_at else None,
            "consumer_receipts": [
                {
                    "receipt_id": receipt.receipt_id,
                    "event_id": receipt.event_id,
                    "webhook_name": receipt.webhook_name,
                    "idempotency_key": receipt.idempotency_key,
                    "received_at": receipt.received_at.isoformat(),
                    "status": receipt.status,
                    "response_code": receipt.response_code,
                    "consumer_id": receipt.consumer_id,
                    "consumer_receipt_id": receipt.consumer_receipt_id,
                    "response_excerpt": receipt.response_excerpt,
                }
                for receipt in (item.consumer_receipts or ())
            ],
            "replay_receipts": [
                {
                    "receipt_id": receipt.receipt_id,
                    "event_id": receipt.event_id,
                    "webhook_name": receipt.webhook_name,
                    "idempotency_key": receipt.idempotency_key,
                    "replayed_at": receipt.replayed_at.isoformat(),
                    "replayed_by": receipt.replayed_by,
                    "status": receipt.status,
                    "replay_token": receipt.replay_token,
                    "notes": receipt.notes,
                }
                for receipt in (item.replay_receipts or ())
            ],
            "operator_receipts": [
                {
                    "receipt_id": receipt.receipt_id,
                    "event_id": receipt.event_id,
                    "webhook_name": receipt.webhook_name,
                    "action": receipt.action,
                    "operator_id": receipt.operator_id,
                    "recorded_at": receipt.recorded_at.isoformat(),
                    "status": receipt.status,
                    "session_source": receipt.session_source,
                    "audit_source": dict(receipt.audit_source),
                    "notes": receipt.notes,
                }
                for receipt in (item.operator_receipts or ())
            ],
        }

    @staticmethod
    def _event_from_payload(payload: Mapping[str, Any]) -> IntegrationOutboxEvent:
        created_at_raw = str(payload.get("created_at", "") or "")
        last_attempt_at_raw = str(payload.get("last_attempt_at", "") or "")
        delivered_at_raw = str(payload.get("delivered_at", "") or "")
        next_retry_at_raw = str(payload.get("next_retry_at", "") or "")
        dead_lettered_at_raw = str(payload.get("dead_lettered_at", "") or "")
        last_alert_at_raw = str(payload.get("last_alert_at", "") or "")
        return IntegrationOutboxEvent(
            event_id=str(payload.get("event_id", "") or ""),
            event_type=str(payload.get("event_type", "") or ""),
            target_type=str(payload.get("target_type", "") or ""),
            target_id=str(payload.get("target_id", "") or ""),
            created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else utcnow(),
            created_by=str(payload.get("created_by", "") or ""),
            session_source=str(payload.get("session_source", "") or ""),
            audit_source=dict(payload.get("audit_source", {}) or {}),
            payload=dict(payload.get("payload", {}) or {}),
            idempotency_key=str(payload.get("idempotency_key", "") or ""),
            delivery_status=str(payload.get("delivery_status", "") or "pending"),
            attempt_count=int(payload.get("attempt_count", 0) or 0),
            last_attempt_at=datetime.fromisoformat(last_attempt_at_raw) if last_attempt_at_raw else None,
            delivered_at=datetime.fromisoformat(delivered_at_raw) if delivered_at_raw else None,
            last_error=str(payload.get("last_error", "") or ""),
            next_retry_at=datetime.fromisoformat(next_retry_at_raw) if next_retry_at_raw else None,
            signature=str(payload.get("signature", "") or ""),
            retry_backoff_seconds=int(payload.get("retry_backoff_seconds", 0) or 0),
            last_response_code=(
                int(payload.get("last_response_code", 0))
                if payload.get("last_response_code", None) is not None
                else None
            ),
            dead_lettered_at=datetime.fromisoformat(dead_lettered_at_raw) if dead_lettered_at_raw else None,
            failure_category=str(payload.get("failure_category", "") or ""),
            alert_status=str(payload.get("alert_status", "") or "none"),
            alert_count=int(payload.get("alert_count", 0) or 0),
            last_alert_at=datetime.fromisoformat(last_alert_at_raw) if last_alert_at_raw else None,
            consumer_receipts=tuple(
                IntegrationConsumerReceipt(
                    receipt_id=str(item.get("receipt_id", "") or ""),
                    event_id=str(item.get("event_id", "") or ""),
                    webhook_name=str(item.get("webhook_name", "") or ""),
                    idempotency_key=str(item.get("idempotency_key", "") or ""),
                    received_at=datetime.fromisoformat(str(item.get("received_at", "") or ""))
                    if str(item.get("received_at", "") or "")
                    else utcnow(),
                    status=str(item.get("status", "") or "delivered"),
                    response_code=(
                        int(item.get("response_code")) if item.get("response_code", None) is not None else None
                    ),
                    consumer_id=str(item.get("consumer_id", "") or ""),
                    consumer_receipt_id=str(item.get("consumer_receipt_id", "") or ""),
                    response_excerpt=str(item.get("response_excerpt", "") or ""),
                )
                for item in list(payload.get("consumer_receipts", ()) or ())
                if isinstance(item, Mapping)
            ),
            replay_receipts=tuple(
                IntegrationReplayReceipt(
                    receipt_id=str(item.get("receipt_id", "") or ""),
                    event_id=str(item.get("event_id", "") or ""),
                    webhook_name=str(item.get("webhook_name", "") or ""),
                    idempotency_key=str(item.get("idempotency_key", "") or ""),
                    replayed_at=datetime.fromisoformat(str(item.get("replayed_at", "") or ""))
                    if str(item.get("replayed_at", "") or "")
                    else utcnow(),
                    replayed_by=str(item.get("replayed_by", "") or ""),
                    status=str(item.get("status", "") or "requeued_pending"),
                    replay_token=str(item.get("replay_token", "") or ""),
                    notes=str(item.get("notes", "") or ""),
                )
                for item in list(payload.get("replay_receipts", ()) or ())
                if isinstance(item, Mapping)
            ),
            operator_receipts=tuple(
                IntegrationOperatorReceipt(
                    receipt_id=str(item.get("receipt_id", "") or ""),
                    event_id=str(item.get("event_id", "") or ""),
                    webhook_name=str(item.get("webhook_name", "") or ""),
                    action=str(item.get("action", "") or ""),
                    operator_id=str(item.get("operator_id", "") or ""),
                    recorded_at=datetime.fromisoformat(str(item.get("recorded_at", "") or ""))
                    if str(item.get("recorded_at", "") or "")
                    else utcnow(),
                    status=str(item.get("status", "") or "recorded"),
                    session_source=str(item.get("session_source", "") or ""),
                    audit_source=dict(item.get("audit_source", {}) or {}),
                    notes=str(item.get("notes", "") or ""),
                )
                for item in list(payload.get("operator_receipts", ()) or ())
                if isinstance(item, Mapping)
            ),
        )

    @staticmethod
    def _worker_status_payload(item: IntegrationDeliveryWorkerStatus) -> dict[str, Any]:
        return {
            "worker_name": item.worker_name,
            "status": item.status,
            "worker_mode": item.worker_mode,
            "daemon_enabled": bool(item.daemon_enabled),
            "daemon_pid": item.daemon_pid,
            "daemon_heartbeat_at": item.daemon_heartbeat_at.isoformat() if item.daemon_heartbeat_at else None,
            "last_started_at": item.last_started_at.isoformat() if item.last_started_at else None,
            "last_finished_at": item.last_finished_at.isoformat() if item.last_finished_at else None,
            "last_success_at": item.last_success_at.isoformat() if item.last_success_at else None,
            "last_error": item.last_error,
            "run_count": int(item.run_count),
            "delivered_count": int(item.delivered_count),
            "failed_count": int(item.failed_count),
            "replay_count": int(item.replay_count),
            "configured_webhooks": list(item.configured_webhooks),
            "configured_event_types": list(item.configured_event_types),
            "schedule_interval_seconds": int(item.schedule_interval_seconds),
            "chain_name": item.chain_name,
            "last_delivery_receipt_id": item.last_delivery_receipt_id,
            "last_operator_receipt_id": item.last_operator_receipt_id,
            "last_run_summary": dict(item.last_run_summary),
        }

    @staticmethod
    def _worker_status_from_payload(payload: Mapping[str, Any]) -> IntegrationDeliveryWorkerStatus:
        def _dt(key: str) -> datetime | None:
            raw = str(payload.get(key, "") or "")
            return datetime.fromisoformat(raw) if raw else None

        return IntegrationDeliveryWorkerStatus(
            worker_name=str(payload.get("worker_name", "") or "integration_outbox_worker"),
            status=str(payload.get("status", "") or "idle"),
            worker_mode=str(payload.get("worker_mode", "") or "single_round"),
            daemon_enabled=bool(payload.get("daemon_enabled", False)),
            daemon_pid=(int(payload.get("daemon_pid")) if payload.get("daemon_pid", None) is not None else None),
            daemon_heartbeat_at=_dt("daemon_heartbeat_at"),
            last_started_at=_dt("last_started_at"),
            last_finished_at=_dt("last_finished_at"),
            last_success_at=_dt("last_success_at"),
            last_error=str(payload.get("last_error", "") or ""),
            run_count=int(payload.get("run_count", 0) or 0),
            delivered_count=int(payload.get("delivered_count", 0) or 0),
            failed_count=int(payload.get("failed_count", 0) or 0),
            replay_count=int(payload.get("replay_count", 0) or 0),
            configured_webhooks=tuple(
                str(item) for item in (payload.get("configured_webhooks", ()) or ()) if str(item).strip()
            ),
            configured_event_types=tuple(
                str(item) for item in (payload.get("configured_event_types", ()) or ()) if str(item).strip()
            ),
            schedule_interval_seconds=int(payload.get("schedule_interval_seconds", 0) or 0),
            chain_name=str(payload.get("chain_name", "") or "integration_outbox"),
            last_delivery_receipt_id=str(payload.get("last_delivery_receipt_id", "") or ""),
            last_operator_receipt_id=str(payload.get("last_operator_receipt_id", "") or ""),
            last_run_summary=dict(payload.get("last_run_summary", {}) or {}),
        )

    @staticmethod
    def _webhook_payload(item: WebhookSubscription) -> dict[str, Any]:
        return {
            "webhook_id": item.webhook_id,
            "name": item.name,
            "url": item.url,
            "subscribed_event_types": list(item.subscribed_event_types),
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "created_by": item.created_by,
            "secret_hint": item.secret_hint,
            "signing_secret": item.signing_secret,
            "signature_key_id": item.signature_key_id,
            "accepted_signature_key_ids": list(item.accepted_signature_key_ids),
            "failure_policy": item.failure_policy,
            "delivery_channel": item.delivery_channel,
        }

    @staticmethod
    def _webhook_from_payload(payload: Mapping[str, Any]) -> WebhookSubscription:
        created_at_raw = str(payload.get("created_at", "") or "")
        return WebhookSubscription(
            webhook_id=str(payload.get("webhook_id", "") or ""),
            name=str(payload.get("name", "") or ""),
            url=str(payload.get("url", "") or ""),
            subscribed_event_types=tuple(
                str(item) for item in (payload.get("subscribed_event_types", ()) or ()) if str(item).strip()
            ),
            created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else None,
            created_by=str(payload.get("created_by", "") or ""),
            secret_hint=str(payload.get("secret_hint", "") or ""),
            signing_secret=str(payload.get("signing_secret", "") or ""),
            signature_key_id=str(payload.get("signature_key_id", "") or "v1"),
            accepted_signature_key_ids=tuple(
                str(item) for item in (payload.get("accepted_signature_key_ids", ()) or ()) if str(item).strip()
            ),
            failure_policy=str(payload.get("failure_policy", "") or "retryable_http"),
            delivery_channel=str(payload.get("delivery_channel", "") or "generic"),
        )
