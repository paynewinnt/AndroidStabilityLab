from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from stability.app.integration_outbox import (
    DeliveryMixin,
    PayloadBuilderMixin,
    ReceiptMixin,
    RepositoryMixin,
    RetryPolicyMixin,
    SecurityMixin,
    SerializationMixin,
    WorkerMixin,
)
from stability.domain import IntegrationOutboxEvent, WebhookSubscription
from stability.domain.value_objects import new_id, utcnow


class IntegrationOutboxService(
    WorkerMixin,
    DeliveryMixin,
    PayloadBuilderMixin,
    ReceiptMixin,
    RetryPolicyMixin,
    SecurityMixin,
    RepositoryMixin,
    SerializationMixin,
):
    """Persist collaboration and admission events as a local outbox."""

    _retryable_http_statuses = frozenset({408, 409, 425, 429})
    _allowed_failure_policies = frozenset({"retryable_http", "best_effort", "fail_closed"})
    _im_notification_event_types = (
        "issue.assigned",
        "issue.transitioned",
        "issue.commented",
        "admission_case.assigned",
        "admission_case.commented",
        "admission_case.transitioned",
        "admission_case.updated",
        "admission.override_recorded",
        "outbox.retry_alert",
    )
    _feishu_bot_event_types = _im_notification_event_types
    _defect_sync_event_types = (
        "issue.defect_create_requested",
        "issue.defect_linked",
        "issue.defect_status_synced",
        "outbox.retry_alert",
    )
    _release_submission_event_types = (
        "release_submission.created",
        "release_submission.execution_updated",
        "release_submission.admission_synced",
        "outbox.retry_alert",
    )

    def __init__(
        self,
        *,
        root_dir: str | Path = "runtime/integration_outbox",
        retry_delay_seconds: int = 300,
        delivery_interval_seconds: int | None = None,
        max_retry_delay_seconds: int = 3600,
        dead_letter_threshold: int = 5,
        retry_alert_threshold: int = 3,
        delivery_transport: Callable[[str, Mapping[str, str], bytes], tuple[int, str]] | None = None,
    ) -> None:
        self._root_dir = Path(root_dir)
        self._events_path = self._root_dir / "events.json"
        self._webhooks_path = self._root_dir / "webhooks.json"
        self._worker_status_path = self._root_dir / "worker_status.json"
        self._retry_delay = max(int(retry_delay_seconds), 0)
        interval_seconds = delivery_interval_seconds if delivery_interval_seconds is not None else retry_delay_seconds
        self._delivery_interval = max(int(interval_seconds), 0)
        self._max_retry_delay = max(int(max_retry_delay_seconds), self._retry_delay, self._delivery_interval)
        self._dead_letter_threshold = max(int(dead_letter_threshold), 1)
        self._retry_alert_threshold = max(int(retry_alert_threshold), 1)
        self._delivery_transport = delivery_transport or self._post_webhook

    def publish_event(
        self,
        *,
        event_type: str,
        target_type: str,
        target_id: str,
        created_by: str,
        session_source: str = "",
        audit_source: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> IntegrationOutboxEvent:
        if not event_type.strip():
            raise ValueError("event_type is required.")
        if not target_type.strip():
            raise ValueError("target_type is required.")
        if not target_id.strip():
            raise ValueError("target_id is required.")
        event = IntegrationOutboxEvent(
            event_id=new_id("outbox_event"),
            event_type=event_type.strip(),
            target_type=target_type.strip(),
            target_id=target_id.strip(),
            created_at=utcnow(),
            created_by=created_by.strip() or "system",
            session_source=session_source.strip(),
            audit_source=dict(audit_source or {}),
            payload=dict(payload or {}),
            idempotency_key=self._idempotency_key(
                event_type=event_type.strip(),
                target_type=target_type.strip(),
                target_id=target_id.strip(),
                payload=dict(payload or {}),
            ),
            delivery_status="pending",
            signature="",
        )
        events = self._load_event_registry()
        events.append(self._event_payload(event))
        self._save_registry(self._events_path, events)
        return event

    def list_events(self, *, limit: int = 50) -> tuple[IntegrationOutboxEvent, ...]:
        items = [self._event_from_payload(item) for item in self._load_event_registry()]
        items.sort(key=lambda item: item.created_at, reverse=True)
        if limit > 0:
            items = items[:limit]
        return tuple(items)

    def register_webhook(
        self,
        *,
        name: str,
        url: str,
        subscribed_event_types: Sequence[str],
        created_by: str,
        secret_hint: str = "",
        signing_secret: str = "",
        signature_key_id: str = "v1",
        accepted_signature_key_ids: Sequence[str] = (),
        failure_policy: str = "retryable_http",
        delivery_channel: str = "generic",
    ) -> WebhookSubscription:
        label = name.strip()
        endpoint = url.strip()
        if not label:
            raise ValueError("Webhook name is required.")
        if not endpoint:
            raise ValueError("Webhook url is required.")
        normalized = self._validated_webhook_security(
            url=endpoint,
            signing_secret=signing_secret,
            signature_key_id=signature_key_id,
            accepted_signature_key_ids=accepted_signature_key_ids,
            failure_policy=failure_policy,
        )
        subscription = WebhookSubscription(
            webhook_id=new_id("webhook"),
            name=label,
            url=str(normalized["url"]),
            subscribed_event_types=tuple(
                item.strip() for item in subscribed_event_types if str(item).strip()
            ),
            created_at=utcnow(),
            created_by=created_by.strip() or "cli",
            secret_hint=secret_hint.strip(),
            signing_secret=str(normalized["signing_secret"]),
            signature_key_id=str(normalized["signature_key_id"]),
            accepted_signature_key_ids=tuple(str(item) for item in normalized["accepted_signature_key_ids"]),
            failure_policy=str(normalized["failure_policy"]),
            delivery_channel=delivery_channel.strip() or "generic",
        )
        registry = self._load_webhook_registry()
        registry.append(self._webhook_payload(subscription))
        self._save_registry(self._webhooks_path, registry)
        return subscription

    def list_webhooks(self) -> tuple[WebhookSubscription, ...]:
        items = [self._webhook_from_payload(item) for item in self._load_webhook_registry()]
        items.sort(key=lambda item: item.created_at or datetime.min, reverse=True)
        return tuple(items)

    @classmethod
    def im_notification_event_types(cls) -> tuple[str, ...]:
        return tuple(cls._im_notification_event_types)

    def register_im_webhook(
        self,
        *,
        name: str,
        url: str,
        created_by: str,
        secret_hint: str = "",
        signing_secret: str = "",
        signature_key_id: str = "v1",
        accepted_signature_key_ids: Sequence[str] = (),
        failure_policy: str = "retryable_http",
        subscribed_event_types: Sequence[str] = (),
    ) -> WebhookSubscription:
        event_types = tuple(
            str(item).strip()
            for item in (subscribed_event_types or self.im_notification_event_types())
            if str(item).strip()
        )
        return self.register_webhook(
            name=name,
            url=url,
            subscribed_event_types=event_types,
            created_by=created_by,
            secret_hint=secret_hint,
            signing_secret=signing_secret,
            signature_key_id=signature_key_id,
            accepted_signature_key_ids=accepted_signature_key_ids,
            failure_policy=failure_policy,
            delivery_channel="im_notify",
        )

    @classmethod
    def feishu_bot_event_types(cls) -> tuple[str, ...]:
        return tuple(cls._feishu_bot_event_types)

    def register_feishu_webhook(
        self,
        *,
        name: str,
        url: str,
        created_by: str,
        secret_hint: str = "",
        signing_secret: str = "",
        signature_key_id: str = "feishu-bot",
        accepted_signature_key_ids: Sequence[str] = (),
        failure_policy: str = "retryable_http",
        subscribed_event_types: Sequence[str] = (),
    ) -> WebhookSubscription:
        event_types = tuple(
            str(item).strip()
            for item in (subscribed_event_types or self.feishu_bot_event_types())
            if str(item).strip()
        )
        return self.register_webhook(
            name=name,
            url=url,
            subscribed_event_types=event_types,
            created_by=created_by,
            secret_hint=secret_hint,
            signing_secret=signing_secret,
            signature_key_id=signature_key_id,
            accepted_signature_key_ids=accepted_signature_key_ids,
            failure_policy=failure_policy,
            delivery_channel="feishu_bot",
        )

    @classmethod
    def defect_sync_event_types(cls) -> tuple[str, ...]:
        return tuple(cls._defect_sync_event_types)

    def register_defect_webhook(
        self,
        *,
        name: str,
        url: str,
        created_by: str,
        secret_hint: str = "",
        signing_secret: str = "",
        signature_key_id: str = "v1",
        accepted_signature_key_ids: Sequence[str] = (),
        failure_policy: str = "retryable_http",
        subscribed_event_types: Sequence[str] = (),
    ) -> WebhookSubscription:
        event_types = tuple(
            str(item).strip()
            for item in (subscribed_event_types or self.defect_sync_event_types())
            if str(item).strip()
        )
        return self.register_webhook(
            name=name,
            url=url,
            subscribed_event_types=event_types,
            created_by=created_by,
            secret_hint=secret_hint,
            signing_secret=signing_secret,
            signature_key_id=signature_key_id,
            accepted_signature_key_ids=accepted_signature_key_ids,
            failure_policy=failure_policy,
            delivery_channel="defect_sync",
        )

    @classmethod
    def release_submission_event_types(cls) -> tuple[str, ...]:
        return tuple(cls._release_submission_event_types)

    def register_release_webhook(
        self,
        *,
        name: str,
        url: str,
        created_by: str,
        secret_hint: str = "",
        signing_secret: str = "",
        signature_key_id: str = "v1",
        accepted_signature_key_ids: Sequence[str] = (),
        failure_policy: str = "retryable_http",
        subscribed_event_types: Sequence[str] = (),
    ) -> WebhookSubscription:
        event_types = tuple(
            str(item).strip()
            for item in (subscribed_event_types or self.release_submission_event_types())
            if str(item).strip()
        )
        return self.register_webhook(
            name=name,
            url=url,
            subscribed_event_types=event_types,
            created_by=created_by,
            secret_hint=secret_hint,
            signing_secret=signing_secret,
            signature_key_id=signature_key_id,
            accepted_signature_key_ids=accepted_signature_key_ids,
            failure_policy=failure_policy,
            delivery_channel="release_submission",
        )
