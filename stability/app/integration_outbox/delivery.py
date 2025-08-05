from __future__ import annotations

import ssl
import json
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from stability.domain import IntegrationOutboxEvent, WebhookSubscription
from stability.domain.value_objects import new_id


class DeliveryMixin:
    def deliver_pending_events(
        self,
        *,
        webhook_name: str,
        limit: int = 20,
        event_types: Sequence[str] = (),
        now: datetime | None = None,
    ) -> dict[str, Any]:
        target_name = webhook_name.strip()
        if not target_name:
            raise ValueError("webhook_name is required.")
        current_time = now or self._utcnow()
        allowed_event_types = {str(item).strip() for item in event_types if str(item).strip()}
        webhook = next(
            (item for item in self.list_webhooks() if str(getattr(item, "name", "") or "") == target_name),
            None,
        )
        if webhook is None:
            raise ValueError(f"Webhook '{target_name}' is not registered.")

        registry = self._load_event_registry()
        updated_registry: list[dict[str, Any]] = []
        delivered_event_ids: list[str] = []
        alert_event_ids: list[str] = []
        deduplicated = 0
        attempted = 0
        delivered = 0
        failed = 0
        retry = 0
        skipped = 0
        dead_lettered = 0
        alerts_emitted = 0
        emitted_events: list[IntegrationOutboxEvent] = []
        delivery_receipt_ids: list[str] = []
        for raw_event in registry:
            event = self._event_from_payload(raw_event)
            if (
                not allowed_event_types or event.event_type in allowed_event_types
            ) and self._webhook_accepts_event(webhook, event) and self._has_delivered_receipt(
                event,
                webhook_name=target_name,
            ):
                deduplicated += 1
                skipped += 1
                latest_receipt = next(reversed(tuple(event.consumer_receipts or ())), None)
                if latest_receipt is not None:
                    delivery_receipt_ids.append(str(getattr(latest_receipt, "receipt_id", "") or ""))
                updated_registry.append(self._event_payload(event))
                continue
            if limit > 0 and attempted >= limit:
                updated_registry.append(self._event_payload(event))
                continue
            if allowed_event_types and event.event_type not in allowed_event_types:
                updated_registry.append(self._event_payload(event))
                continue
            if not self._is_due_for_delivery(event, current_time):
                updated_registry.append(self._event_payload(event))
                continue
            if not self._webhook_accepts_event(webhook, event):
                skipped += 1
                updated_registry.append(self._event_payload(event))
                continue
            attempted += 1
            delivered_event, alert_event = self._deliver_event_to_webhook(
                event,
                webhook=webhook,
                current_time=current_time,
            )
            if alert_event is not None:
                delivered_event = replace(
                    delivered_event,
                    alert_status="emitted",
                    alert_count=int(delivered_event.alert_count) + 1,
                    last_alert_at=current_time,
                )
                emitted_events.append(alert_event)
                alert_event_ids.append(alert_event.event_id)
                alerts_emitted += 1
            updated_registry.append(self._event_payload(delivered_event))
            if delivered_event.delivery_status == "delivered":
                delivered += 1
                delivered_event_ids.append(delivered_event.event_id)
                latest_receipt = next(reversed(tuple(delivered_event.consumer_receipts or ())), None)
                if latest_receipt is not None:
                    delivery_receipt_ids.append(str(getattr(latest_receipt, "receipt_id", "") or ""))
            else:
                failed += 1
                if delivered_event.delivery_status == "retry_pending":
                    retry += 1
                if delivered_event.delivery_status == "dead_letter":
                    dead_lettered += 1
        delivery_receipt_ids = [item for item in delivery_receipt_ids if item]
        receipt_count = len(delivery_receipt_ids)
        if emitted_events:
            updated_registry.extend(self._event_payload(item) for item in emitted_events)
        self._save_registry(self._events_path, updated_registry)
        return {
            "webhook_name": target_name,
            "attempted_count": attempted,
            "delivered_count": delivered,
            "failed_count": failed,
            "retry_count": retry,
            "dead_letter_count": dead_lettered,
            "dead_lettered_count": dead_lettered,
            "skipped_count": skipped,
            "deduplicated_count": deduplicated,
            "receipt_count": receipt_count,
            "alert_emitted_count": alerts_emitted,
            "delivered_event_ids": delivered_event_ids,
            "delivery_receipt_ids": delivery_receipt_ids,
            "alert_event_ids": alert_event_ids,
            "remaining_pending_count": sum(
                1
                for item in updated_registry
                if str(item.get("delivery_status", "") or "pending") in {"pending", "retry_pending"}
            ),
        }

    def build_im_delivery_acceptance_summary(self) -> dict[str, Any]:
        return self._delivery_acceptance_summary(
            name="im_notify",
            delivery_channels=("im_notify",),
            event_types=self.im_notification_event_types(),
        )

    def build_feishu_delivery_acceptance_summary(self) -> dict[str, Any]:
        return self._delivery_acceptance_summary(
            name="feishu_bot",
            delivery_channels=("feishu_bot",),
            event_types=self.feishu_bot_event_types(),
        )

    def build_delivery_acceptance_summary(
        self,
        *,
        delivery_channels: Sequence[str] = (),
        event_types: Sequence[str] = (),
        name: str = "integration_delivery",
    ) -> dict[str, Any]:
        return self._delivery_acceptance_summary(
            name=name,
            delivery_channels=delivery_channels,
            event_types=event_types,
        )

    def _delivery_acceptance_summary(
        self,
        *,
        name: str,
        delivery_channels: Sequence[str],
        event_types: Sequence[str],
    ) -> dict[str, Any]:
        channels = tuple(str(item).strip() for item in delivery_channels if str(item).strip())
        event_type_filter = {str(item).strip() for item in event_types if str(item).strip()}
        webhook_names = self._webhook_names_for_acceptance(channels)
        events = [
            self._event_from_payload(item)
            for item in self._load_event_registry()
            if not event_type_filter or str(item.get("event_type", "") or "") in event_type_filter
        ]
        if webhook_names:
            receipt_event_ids = {
                receipt.event_id
                for event in events
                for receipt in (event.consumer_receipts or ())
                if receipt.webhook_name in webhook_names
            }
            events = [
                event
                for event in events
                if event.event_id in receipt_event_ids
                or str(event.delivery_status or "pending") in {"pending", "retry_pending", "dead_letter", "failed"}
            ]
        total = len(events)
        delivered_events = [event for event in events if str(event.delivery_status or "") == "delivered"]
        retry_events = [event for event in events if str(event.delivery_status or "") == "retry_pending"]
        dead_letter_events = [event for event in events if str(event.delivery_status or "") == "dead_letter"]
        failed_events = [
            event
            for event in events
            if str(event.delivery_status or "") in {"failed", "retry_pending", "dead_letter"}
        ]
        consumer_receipts = [
            receipt
            for event in events
            for receipt in (event.consumer_receipts or ())
            if not webhook_names or receipt.webhook_name in webhook_names
        ]
        worker_summary = self._acceptance_worker_summary()
        error_coverage = self._acceptance_field_coverage(failed_events, "last_error")
        failure_category_coverage = self._acceptance_field_coverage(failed_events, "failure_category")
        next_retry_coverage = self._acceptance_field_coverage(retry_events, "next_retry_at")
        return {
            "name": name,
            "delivery_channels": list(channels),
            "webhook_names": list(webhook_names),
            "event_types": sorted(event_type_filter),
            "total_event_count": total,
            "success_count": len(delivered_events),
            "failed_count": len(failed_events),
            "retry_count": len(retry_events),
            "dead_letter_count": len(dead_letter_events),
            "consumer_receipt_count": len(consumer_receipts),
            "deduplicated_count": int(worker_summary.get("deduplicated_count", 0) or 0),
            "coverage": {
                "last_error": error_coverage,
                "failure_category": failure_category_coverage,
                "next_retry_at": next_retry_coverage,
            },
            "worker_counters": worker_summary,
            "status_counts": self._acceptance_status_counts(events),
            "last_error_samples": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "delivery_status": event.delivery_status,
                    "last_error": event.last_error,
                    "failure_category": event.failure_category,
                    "next_retry_at": event.next_retry_at.isoformat() if event.next_retry_at else None,
                }
                for event in failed_events[:10]
            ],
        }

    def _webhook_names_for_acceptance(self, channels: Sequence[str]) -> tuple[str, ...]:
        channel_filter = {str(item).strip() for item in channels if str(item).strip()}
        return tuple(
            item.name
            for item in self.list_webhooks()
            if item.name and (not channel_filter or str(getattr(item, "delivery_channel", "") or "") in channel_filter)
        )

    def _acceptance_worker_summary(self) -> dict[str, int]:
        worker = self.get_worker_status()
        summary = dict(getattr(worker, "last_run_summary", {}) or {})
        aggregate = dict(summary.get("aggregate", {}) or {})
        deliveries = list(summary.get("deliveries", ()) or ())
        keys = (
            "attempted_count",
            "delivered_count",
            "failed_count",
            "retry_count",
            "dead_letter_count",
            "dead_lettered_count",
            "deduplicated_count",
            "receipt_count",
        )
        result = {key: int(aggregate.get(key, 0) or 0) for key in keys}
        if not aggregate:
            for item in deliveries:
                if not isinstance(item, Mapping):
                    continue
                for key in keys:
                    result[key] += int(item.get(key, 0) or 0)
        if result["dead_letter_count"] <= 0:
            result["dead_letter_count"] = result["dead_lettered_count"]
        return result

    @staticmethod
    def _acceptance_status_counts(events: Sequence[IntegrationOutboxEvent]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in events:
            status = str(event.delivery_status or "pending")
            counts[status] = counts.get(status, 0) + 1
        return counts

    @staticmethod
    def _acceptance_field_coverage(events: Sequence[IntegrationOutboxEvent], field_name: str) -> dict[str, Any]:
        missing_event_ids: list[str] = []
        covered = 0
        for event in events:
            value = getattr(event, field_name)
            if value in (None, ""):
                missing_event_ids.append(event.event_id)
            else:
                covered += 1
        total = len(events)
        return {
            "covered_count": covered,
            "missing_count": len(missing_event_ids),
            "total_count": total,
            "is_complete": len(missing_event_ids) == 0,
            "missing_event_ids": missing_event_ids,
        }

    @staticmethod
    def _webhook_accepts_event(webhook: WebhookSubscription, event: IntegrationOutboxEvent) -> bool:
        subscribed_event_types = {
            str(item).strip()
            for item in (getattr(webhook, "subscribed_event_types", ()) or ())
            if str(item).strip()
        }
        return not subscribed_event_types or event.event_type in subscribed_event_types

    @staticmethod
    def _should_attempt_delivery(event: IntegrationOutboxEvent, current_time: datetime) -> bool:
        status = str(event.delivery_status or "pending")
        if status == "delivered":
            return False
        if status == "failed":
            return False
        if status == "dead_letter":
            return False
        if event.next_retry_at is not None and event.next_retry_at > current_time:
            return False
        return True

    def _is_due_for_delivery(self, event: IntegrationOutboxEvent, current_time: datetime) -> bool:
        if not self._should_attempt_delivery(event, current_time):
            return False
        if event.last_attempt_at is None:
            return True
        interval_seconds = max(self._delivery_interval, 0)
        if interval_seconds <= 0:
            return True
        return current_time >= event.last_attempt_at + timedelta(seconds=interval_seconds)

    def _deliver_event_to_webhook(
        self,
        event: IntegrationOutboxEvent,
        *,
        webhook: WebhookSubscription,
        current_time: datetime,
    ) -> tuple[IntegrationOutboxEvent, IntegrationOutboxEvent | None]:
        body = self._delivery_body_for_webhook(event, webhook=webhook, current_time=current_time)
        signature = self._signature(body, webhook=webhook)
        headers = {
            "Content-Type": "application/json",
            "X-ASL-Event-Id": event.event_id,
            "X-ASL-Event-Type": event.event_type,
            "X-ASL-Delivery-Attempt": str(int(event.attempt_count) + 1),
            "X-ASL-Idempotency-Key": str(event.idempotency_key or ""),
            "X-ASL-Signature": signature,
            "X-ASL-Signature-Alg": self._signature_algorithm(webhook),
            "X-ASL-Signature-Key-Id": str(getattr(webhook, "signature_key_id", "") or "v1"),
            "X-ASL-Delivery-Contract": "asl.webhook_delivery.v1",
            "X-ASL-Callback-Contract-Version": "asl.webhook_callback.v1",
            "X-ASL-Webhook-Name": str(getattr(webhook, "name", "") or ""),
            "X-ASL-Failure-Policy": str(getattr(webhook, "failure_policy", "") or "retryable_http"),
            "X-ASL-Target-Type": event.target_type,
            "X-ASL-Target-Id": event.target_id,
        }
        try:
            status_code, response_text = self._delivery_transport(str(webhook.url), headers, body)
        except Exception as exc:
            failed_event = self._failed_delivery_event(
                event,
                current_time=current_time,
                signature=signature,
                error_text=str(exc),
                status_code=None,
            )
            return failed_event, self._maybe_emit_retry_alert(failed_event, current_time=current_time)
        if 200 <= int(status_code) < 300:
            business_error = self._webhook_business_error(webhook, str(response_text or ""))
            if business_error:
                failed_event = self._failed_delivery_event(
                    event,
                    current_time=current_time,
                    signature=signature,
                    error_text=business_error,
                    status_code=400,
                )
                return failed_event, self._maybe_emit_retry_alert(failed_event, current_time=current_time)
            receipt = self._consumer_receipt_for_delivery(
                event=event,
                webhook=webhook,
                current_time=current_time,
                response_text=str(response_text or ""),
                status_code=int(status_code),
            )
            return replace(
                event,
                delivery_status="delivered",
                attempt_count=int(event.attempt_count) + 1,
                last_attempt_at=current_time,
                delivered_at=current_time,
                last_error="",
                next_retry_at=None,
                signature=signature,
                retry_backoff_seconds=0,
                last_response_code=int(status_code),
                dead_lettered_at=None,
                failure_category="",
                consumer_receipts=tuple(list(event.consumer_receipts) + [receipt]),
            ), None
        error_text = str(response_text or f"HTTP {status_code}")
        failed_event = self._failed_delivery_event(
            event,
            current_time=current_time,
            signature=signature,
            error_text=error_text,
            status_code=int(status_code),
        )
        return failed_event, self._maybe_emit_retry_alert(failed_event, current_time=current_time)

    def _failed_delivery_event(
        self,
        event: IntegrationOutboxEvent,
        *,
        current_time: datetime,
        signature: str,
        error_text: str,
        status_code: int | None,
    ) -> IntegrationOutboxEvent:
        next_attempt_count = int(event.attempt_count) + 1
        should_retry = self._is_retryable_failure(status_code)
        failure_category = self._failure_category(status_code=status_code, should_retry=should_retry)
        if should_retry and next_attempt_count < self._dead_letter_threshold:
            backoff_seconds = self._compute_retry_backoff(next_attempt_count)
            return replace(
                event,
                delivery_status="retry_pending",
                attempt_count=next_attempt_count,
                last_attempt_at=current_time,
                last_error=error_text,
                next_retry_at=current_time + timedelta(seconds=backoff_seconds),
                signature=signature,
                retry_backoff_seconds=backoff_seconds,
                last_response_code=status_code,
                failure_category=failure_category,
            )
        terminal_error = error_text
        if status_code is not None and not should_retry:
            terminal_error = f"{error_text} (non-retryable)"
        if next_attempt_count >= self._dead_letter_threshold and should_retry:
            terminal_error = f"{error_text} (dead-letter threshold reached)"
        return replace(
            event,
            delivery_status="dead_letter",
            attempt_count=next_attempt_count,
            last_attempt_at=current_time,
            last_error=terminal_error,
            next_retry_at=None,
            signature=signature,
            retry_backoff_seconds=0,
            last_response_code=status_code,
            dead_lettered_at=current_time,
            failure_category=f"{failure_category}:dead_letter",
        )

    def _maybe_emit_retry_alert(
        self,
        event: IntegrationOutboxEvent,
        *,
        current_time: datetime,
    ) -> IntegrationOutboxEvent | None:
        if self._is_system_alert_event(event.event_type):
            return None
        if int(event.alert_count) > 0 or str(event.alert_status or "none") == "emitted":
            return None
        should_alert = str(event.delivery_status or "") == "dead_letter" or int(event.attempt_count) >= self._retry_alert_threshold
        if not should_alert:
            return None
        alert_reason = "dead_letter" if str(event.delivery_status or "") == "dead_letter" else "retry_threshold"
        alert_event = IntegrationOutboxEvent(
            event_id=new_id("outbox_event"),
            event_type="outbox.retry_alert",
            target_type="outbox_event",
            target_id=event.event_id,
            created_at=current_time,
            created_by="system",
            session_source="system:integration_outbox",
            audit_source={
                "alert_reason": alert_reason,
                "original_event_type": event.event_type,
                "original_target_type": event.target_type,
                "original_target_id": event.target_id,
            },
            payload={
                "event_id": event.event_id,
                "event_type": event.event_type,
                "delivery_status": event.delivery_status,
                "attempt_count": int(event.attempt_count),
                "last_error": event.last_error,
                "last_response_code": event.last_response_code,
                "dead_lettered": bool(event.dead_lettered_at is not None),
                "next_retry_at": event.next_retry_at.isoformat() if event.next_retry_at else None,
            },
            delivery_status="pending",
            alert_status="self",
        )
        return alert_event

    @staticmethod
    def _post_webhook(url: str, headers: Mapping[str, str], body: bytes) -> tuple[int, str]:
        request = Request(url=url, data=body, headers=dict(headers), method="POST")
        try:
            with urlopen(request, timeout=5, context=_webhook_ssl_context()) as response:
                return int(getattr(response, "status", 200) or 200), response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            return int(exc.code), exc.read().decode("utf-8", errors="replace")
        except URLError as exc:
            raise RuntimeError(f"Webhook delivery failed: {exc.reason}") from exc

    @staticmethod
    def _webhook_business_error(webhook: WebhookSubscription, response_text: str) -> str:
        if str(getattr(webhook, "delivery_channel", "") or "").strip() != "feishu_bot":
            return ""
        try:
            payload = json.loads(response_text) if response_text.strip().startswith("{") else {}
        except json.JSONDecodeError:
            return ""
        if not isinstance(payload, Mapping):
            return ""
        code = payload.get("code")
        if code in (None, 0, "0"):
            return ""
        message = str(payload.get("msg", "") or payload.get("message", "") or "unknown feishu error")
        return f"Feishu bot delivery failed: code={code}, msg={message}"


def _webhook_ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())
