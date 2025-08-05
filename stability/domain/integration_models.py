from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class IntegrationConsumerReceipt:
    """One local receipt describing what one downstream consumer acknowledged."""

    receipt_id: str
    event_id: str
    webhook_name: str
    idempotency_key: str
    received_at: datetime
    status: str = "delivered"
    response_code: int | None = None
    consumer_id: str = ""
    consumer_receipt_id: str = ""
    response_excerpt: str = ""


@dataclass(frozen=True)
class IntegrationReplayReceipt:
    """One operator-visible receipt describing a dead-letter replay action."""

    receipt_id: str
    event_id: str
    webhook_name: str
    idempotency_key: str
    replayed_at: datetime
    replayed_by: str
    status: str = "requeued_pending"
    replay_token: str = ""
    notes: str = ""


@dataclass(frozen=True)
class IntegrationOperatorReceipt:
    """One explicit operator action recorded against an outbox event."""

    receipt_id: str
    event_id: str
    webhook_name: str
    action: str
    operator_id: str
    recorded_at: datetime
    status: str = "recorded"
    session_source: str = ""
    audit_source: Mapping[str, Any] = field(default_factory=dict)
    notes: str = ""


@dataclass(frozen=True)
class IntegrationDeliveryWorkerStatus:
    """Minimal local delivery-worker runtime status."""

    worker_name: str
    status: str = "idle"
    worker_mode: str = "single_round"
    daemon_enabled: bool = False
    daemon_pid: int | None = None
    daemon_heartbeat_at: datetime | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str = ""
    run_count: int = 0
    delivered_count: int = 0
    failed_count: int = 0
    replay_count: int = 0
    configured_webhooks: Sequence[str] = field(default_factory=tuple)
    configured_event_types: Sequence[str] = field(default_factory=tuple)
    schedule_interval_seconds: int = 0
    chain_name: str = "integration_outbox"
    last_delivery_receipt_id: str = ""
    last_operator_receipt_id: str = ""
    last_run_summary: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IntegrationOutboxEvent:
    """One durable outbox event ready for external integration handling."""

    event_id: str
    event_type: str
    target_type: str
    target_id: str
    created_at: datetime
    created_by: str
    session_source: str = ""
    audit_source: Mapping[str, Any] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    delivery_status: str = "pending"
    attempt_count: int = 0
    last_attempt_at: datetime | None = None
    delivered_at: datetime | None = None
    last_error: str = ""
    next_retry_at: datetime | None = None
    signature: str = ""
    retry_backoff_seconds: int = 0
    last_response_code: int | None = None
    dead_lettered_at: datetime | None = None
    failure_category: str = ""
    alert_status: str = "none"
    alert_count: int = 0
    last_alert_at: datetime | None = None
    consumer_receipts: Sequence[IntegrationConsumerReceipt] = field(default_factory=tuple)
    replay_receipts: Sequence[IntegrationReplayReceipt] = field(default_factory=tuple)
    operator_receipts: Sequence[IntegrationOperatorReceipt] = field(default_factory=tuple)


@dataclass(frozen=True)
class WebhookSubscription:
    """Stored webhook registration for future external callback delivery."""

    webhook_id: str
    name: str
    url: str
    subscribed_event_types: Sequence[str] = field(default_factory=tuple)
    created_at: datetime | None = None
    created_by: str = ""
    secret_hint: str = ""
    signing_secret: str = ""
    signature_key_id: str = "v1"
    accepted_signature_key_ids: Sequence[str] = field(default_factory=tuple)
    failure_policy: str = "retryable_http"
    delivery_channel: str = "generic"


@dataclass(frozen=True)
class ReleaseSubmissionRecord:
    """One inbound release-submission request plus its linked execution and admission state."""

    submission_id: str
    source_platform: str
    source_request_id: str
    package_name: str
    version_name: str = ""
    version_code: str = ""
    build_id: str = ""
    release_channel: str = ""
    owner_team: str = ""
    submission_title: str = ""
    template_type: str = "cold_start_loop"
    selected_device_ids: Sequence[str] = field(default_factory=tuple)
    enabled_metrics: Sequence[str] = field(default_factory=tuple)
    sampling_interval_seconds: int = 5
    monitoring_backend: str = ""
    execute_immediately: bool = False
    submission_status: str = "received"
    task_id: str = ""
    task_name: str = ""
    run_id: str = ""
    run_status: str = ""
    report_paths: Mapping[str, str] = field(default_factory=dict)
    baseline_key: str = ""
    admission_case_id: str = ""
    admission_status: str = ""
    admission_final_decision: str = ""
    admission_error_code: str = ""
    created_at: datetime | None = None
    created_by: str = ""
    updated_at: datetime | None = None
    updated_by: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
