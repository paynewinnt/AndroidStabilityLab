from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping

from stability.domain import (
    IntegrationConsumerReceipt,
    IntegrationOperatorReceipt,
    IntegrationOutboxEvent,
    IntegrationReplayReceipt,
    WebhookSubscription,
)
from stability.domain.value_objects import new_id


class ReceiptMixin:
    def _consumer_receipt_for_delivery(
        self,
        *,
        event: IntegrationOutboxEvent,
        webhook: WebhookSubscription,
        current_time: datetime,
        response_text: str,
        status_code: int,
    ) -> IntegrationConsumerReceipt:
        parsed: dict[str, Any] = {}
        try:
            maybe = json.loads(response_text) if response_text.strip().startswith("{") else {}
            parsed = dict(maybe) if isinstance(maybe, Mapping) else {}
        except Exception:
            parsed = {}
        consumer_id = str(parsed.get("consumer_id", "") or parsed.get("receiver", "") or webhook.name)
        consumer_receipt_id = str(parsed.get("receipt_id", "") or parsed.get("consumer_receipt_id", "") or "")
        return IntegrationConsumerReceipt(
            receipt_id=new_id("consumer_receipt"),
            event_id=event.event_id,
            webhook_name=webhook.name,
            idempotency_key=event.idempotency_key,
            received_at=current_time,
            status="delivered",
            response_code=status_code,
            consumer_id=consumer_id,
            consumer_receipt_id=consumer_receipt_id,
            response_excerpt=response_text[:200],
        )

    def _replay_receipt(
        self,
        *,
        event: IntegrationOutboxEvent,
        webhook_name: str,
        replayed_by: str,
        current_time: datetime,
    ) -> IntegrationReplayReceipt:
        return IntegrationReplayReceipt(
            receipt_id=new_id("replay_receipt"),
            event_id=event.event_id,
            webhook_name=webhook_name,
            idempotency_key=event.idempotency_key,
            replayed_at=current_time,
            replayed_by=replayed_by,
            replay_token=f"asl.outbox.replay.v1:{event.event_id}:{int(current_time.timestamp())}",
            notes="Replay queued back to pending delivery.",
        )

    def _operator_receipt(
        self,
        *,
        event: IntegrationOutboxEvent,
        webhook_name: str,
        action: str,
        operator_id: str,
        current_time: datetime,
        notes: str,
    ) -> IntegrationOperatorReceipt:
        return IntegrationOperatorReceipt(
            receipt_id=new_id("operator_receipt"),
            event_id=event.event_id,
            webhook_name=webhook_name,
            action=action,
            operator_id=operator_id,
            recorded_at=current_time,
            session_source="system:integration_outbox",
            audit_source={"idempotency_key": event.idempotency_key},
            notes=notes,
        )

    @staticmethod
    def _has_delivered_receipt(event: IntegrationOutboxEvent, *, webhook_name: str) -> bool:
        return any(
            str(item.webhook_name or "") == webhook_name
            and str(item.idempotency_key or "") == str(event.idempotency_key or "")
            for item in (event.consumer_receipts or ())
        )
