from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from collections.abc import Iterable
from typing import Any, Mapping, Sequence

from stability import create_v1_bootstrap, create_v1_persistent_bootstrap
from stability.app import (
    DeviceRecordNotFound,
    RunRecordNotFound,
    SnapshotRecordNotFound,
    UnattendedPatrolRunnerAlreadyRunning,
    UnattendedTaskRecordNotFound,
)
from stability.app.task_service import TaskRecordNotFound
from stability.domain import (
    AggregatedIssue,
    AnalysisSnapshotRecord,
    AnalysisSnapshotSummary,
    ComparedMetricTrend,
    ComparedIssue,
    ComparisonResult,
    IssueEventReference,
    IssueAttribution,
    MetricTrendSummary,
    PerformanceTrendComparison,
    RegressedIssue,
    RegressedMetric,
    RegressionResult,
    SamplingConfig,
    TaskDefinition,
    TaskRunStatus,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.cli.handlers.web import handle_serve_web as _web_handle_serve_web
from stability.cli.utils import _expand_multi_value, _parse_json_object
from stability.application import resolve_monitoring_backend_override as _resolve_monitoring_backend_override
from stability.time_utils import format_beijing_datetime_or_original
from stability.web import serve_web_portal

# Split from stability.cli.task_create; integration_commands.py owns this command/payload group.

# Split from stability/cli/handlers/integration_commands.py.

def _isoformat_or_none(value: object) -> str | None:
    return format_beijing_datetime_or_original(value)


def _handle_register_integration_webhook(args: argparse.Namespace) -> int:
    """Register one outbound webhook target for future outbox delivery rounds."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "integration_outbox_service", None)
    if service is None or not hasattr(service, "register_webhook"):
        raise SystemExit("Integration outbox service is unavailable.")
    webhook = service.register_webhook(
        name=args.name.strip(),
        url=args.url.strip(),
        subscribed_event_types=tuple(_expand_multi_value(args.event_types)),
        created_by=args.created_by.strip(),
        secret_hint=args.secret_hint.strip(),
        signing_secret=args.signing_secret.strip(),
        signature_key_id=args.signature_key_id.strip(),
        accepted_signature_key_ids=tuple(_expand_multi_value(args.accepted_signature_key_ids)),
        failure_policy=args.failure_policy.strip(),
        delivery_channel=args.delivery_channel.strip(),
    )
    payload = {
        "storage_mode": "persistent",
        "webhook": {
            "webhook_id": webhook.webhook_id,
            "name": webhook.name,
            "url": webhook.url,
            "subscribed_event_types": list(webhook.subscribed_event_types),
            "created_at": _isoformat_or_none(webhook.created_at),
            "created_by": webhook.created_by,
            "secret_hint": webhook.secret_hint,
            "signature_key_id": str(getattr(webhook, "signature_key_id", "") or "v1"),
            "accepted_signature_key_ids": list(getattr(webhook, "accepted_signature_key_ids", ()) or ()),
            "failure_policy": str(getattr(webhook, "failure_policy", "") or "retryable_http"),
            "delivery_channel": str(getattr(webhook, "delivery_channel", "") or "generic"),
            "callback_contract_version": "asl.webhook_callback.v1",
            "security_rules": [
                "non-local webhook requires https",
                "non-local webhook requires signing_secret",
                "delivery uses signature headers plus idempotency key",
            ],
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_register_im_webhook(args: argparse.Namespace) -> int:
    """Register one IM notification webhook with the stable IM contract."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "integration_outbox_service", None)
    if service is None:
        raise SystemExit("Integration outbox service is unavailable.")
    event_types = tuple(_expand_multi_value(args.event_types))
    if hasattr(service, "register_im_webhook"):
        webhook = service.register_im_webhook(
            name=args.name.strip(),
            url=args.url.strip(),
            created_by=args.created_by.strip(),
            secret_hint=args.secret_hint.strip(),
            signing_secret=args.signing_secret.strip(),
            signature_key_id=args.signature_key_id.strip(),
            accepted_signature_key_ids=tuple(_expand_multi_value(args.accepted_signature_key_ids)),
            failure_policy=args.failure_policy.strip(),
            subscribed_event_types=event_types,
        )
    elif hasattr(service, "register_webhook"):
        fallback_event_types = event_types
        if not fallback_event_types and hasattr(service, "im_notification_event_types"):
            fallback_event_types = tuple(service.im_notification_event_types())
        webhook = service.register_webhook(
            name=args.name.strip(),
            url=args.url.strip(),
            subscribed_event_types=fallback_event_types,
            created_by=args.created_by.strip(),
            secret_hint=args.secret_hint.strip(),
            signing_secret=args.signing_secret.strip(),
            signature_key_id=args.signature_key_id.strip(),
            accepted_signature_key_ids=tuple(_expand_multi_value(args.accepted_signature_key_ids)),
            failure_policy=args.failure_policy.strip(),
            delivery_channel="im_notify",
        )
    else:
        raise SystemExit("Integration outbox service webhook APIs are unavailable.")
    payload = {
        "storage_mode": "persistent",
        "webhook": {
            "webhook_id": webhook.webhook_id,
            "name": webhook.name,
            "url": webhook.url,
            "subscribed_event_types": list(webhook.subscribed_event_types),
            "created_at": _isoformat_or_none(webhook.created_at),
            "created_by": webhook.created_by,
            "secret_hint": webhook.secret_hint,
            "signature_key_id": str(getattr(webhook, "signature_key_id", "") or "v1"),
            "accepted_signature_key_ids": list(getattr(webhook, "accepted_signature_key_ids", ()) or ()),
            "failure_policy": str(getattr(webhook, "failure_policy", "") or "retryable_http"),
            "delivery_channel": str(getattr(webhook, "delivery_channel", "") or "im_notify"),
            "callback_contract_version": "asl.webhook_callback.v1",
            "delivery_contract_version": "asl.im_notify.v1",
            "security_rules": [
                "non-local webhook requires https",
                "non-local webhook requires signing_secret",
                "delivery uses signature headers plus idempotency key",
                "im delivery body follows asl.im_notify.v1",
            ],
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_register_feishu_webhook(args: argparse.Namespace) -> int:
    """Register one Feishu custom bot webhook with the Feishu bot contract."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "integration_outbox_service", None)
    if service is None:
        raise SystemExit("Integration outbox service is unavailable.")
    event_types = tuple(_expand_multi_value(args.event_types))
    if hasattr(service, "register_feishu_webhook"):
        webhook = service.register_feishu_webhook(
            name=args.name.strip(),
            url=args.url.strip(),
            created_by=args.created_by.strip(),
            secret_hint=args.secret_hint.strip(),
            signing_secret=args.signing_secret.strip(),
            signature_key_id=args.signature_key_id.strip(),
            accepted_signature_key_ids=tuple(_expand_multi_value(args.accepted_signature_key_ids)),
            failure_policy=args.failure_policy.strip(),
            subscribed_event_types=event_types,
        )
    elif hasattr(service, "register_webhook"):
        fallback_event_types = event_types
        if not fallback_event_types and hasattr(service, "feishu_bot_event_types"):
            fallback_event_types = tuple(service.feishu_bot_event_types())
        webhook = service.register_webhook(
            name=args.name.strip(),
            url=args.url.strip(),
            subscribed_event_types=fallback_event_types,
            created_by=args.created_by.strip(),
            secret_hint=args.secret_hint.strip(),
            signing_secret=args.signing_secret.strip(),
            signature_key_id=args.signature_key_id.strip(),
            accepted_signature_key_ids=tuple(_expand_multi_value(args.accepted_signature_key_ids)),
            failure_policy=args.failure_policy.strip(),
            delivery_channel="feishu_bot",
        )
    else:
        raise SystemExit("Integration outbox service webhook APIs are unavailable.")
    payload = {
        "storage_mode": "persistent",
        "webhook": {
            "webhook_id": webhook.webhook_id,
            "name": webhook.name,
            "url": webhook.url,
            "subscribed_event_types": list(webhook.subscribed_event_types),
            "created_at": _isoformat_or_none(webhook.created_at),
            "created_by": webhook.created_by,
            "secret_hint": webhook.secret_hint,
            "signature_key_id": str(getattr(webhook, "signature_key_id", "") or "feishu-bot"),
            "accepted_signature_key_ids": list(getattr(webhook, "accepted_signature_key_ids", ()) or ()),
            "failure_policy": str(getattr(webhook, "failure_policy", "") or "retryable_http"),
            "delivery_channel": str(getattr(webhook, "delivery_channel", "") or "feishu_bot"),
            "callback_contract_version": "asl.webhook_callback.v1",
            "delivery_contract_version": "feishu.custom_bot.v1",
            "security_rules": [
                "non-local webhook requires https",
                "signing_secret is the Feishu custom bot secret used for body sign",
                "ASL delivery headers keep idempotency and receipts but do not reuse the Feishu secret",
                "feishu delivery body contains timestamp/sign/msg_type/content",
            ],
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_register_defect_webhook(args: argparse.Namespace) -> int:
    """Register one defect sync webhook with the stable defect contract."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "integration_outbox_service", None)
    if service is None:
        raise SystemExit("Integration outbox service is unavailable.")
    event_types = tuple(_expand_multi_value(args.event_types))
    if hasattr(service, "register_defect_webhook"):
        webhook = service.register_defect_webhook(
            name=args.name.strip(),
            url=args.url.strip(),
            created_by=args.created_by.strip(),
            secret_hint=args.secret_hint.strip(),
            signing_secret=args.signing_secret.strip(),
            signature_key_id=args.signature_key_id.strip(),
            accepted_signature_key_ids=tuple(_expand_multi_value(args.accepted_signature_key_ids)),
            failure_policy=args.failure_policy.strip(),
            subscribed_event_types=event_types,
        )
    elif hasattr(service, "register_webhook"):
        fallback_event_types = event_types
        if not fallback_event_types and hasattr(service, "defect_sync_event_types"):
            fallback_event_types = tuple(service.defect_sync_event_types())
        webhook = service.register_webhook(
            name=args.name.strip(),
            url=args.url.strip(),
            subscribed_event_types=fallback_event_types,
            created_by=args.created_by.strip(),
            secret_hint=args.secret_hint.strip(),
            signing_secret=args.signing_secret.strip(),
            signature_key_id=args.signature_key_id.strip(),
            accepted_signature_key_ids=tuple(_expand_multi_value(args.accepted_signature_key_ids)),
            failure_policy=args.failure_policy.strip(),
            delivery_channel="defect_sync",
        )
    else:
        raise SystemExit("Integration outbox service webhook APIs are unavailable.")
    payload = {
        "storage_mode": "persistent",
        "webhook": {
            "webhook_id": webhook.webhook_id,
            "name": webhook.name,
            "url": webhook.url,
            "subscribed_event_types": list(webhook.subscribed_event_types),
            "created_at": _isoformat_or_none(webhook.created_at),
            "created_by": webhook.created_by,
            "secret_hint": webhook.secret_hint,
            "signature_key_id": str(getattr(webhook, "signature_key_id", "") or "v1"),
            "accepted_signature_key_ids": list(getattr(webhook, "accepted_signature_key_ids", ()) or ()),
            "failure_policy": str(getattr(webhook, "failure_policy", "") or "retryable_http"),
            "delivery_channel": str(getattr(webhook, "delivery_channel", "") or "defect_sync"),
            "callback_contract_version": "asl.webhook_callback.v1",
            "delivery_contract_version": "asl.defect_sync.v1",
            "security_rules": [
                "non-local webhook requires https",
                "non-local webhook requires signing_secret",
                "delivery uses signature headers plus idempotency key",
                "defect delivery body follows asl.defect_sync.v1",
            ],
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _release_submission_payload(record: object) -> dict[str, object]:
    return {
        "submission_id": str(getattr(record, "submission_id", "") or ""),
        "source_platform": str(getattr(record, "source_platform", "") or ""),
        "source_request_id": str(getattr(record, "source_request_id", "") or ""),
        "submission_title": str(getattr(record, "submission_title", "") or ""),
        "submission_status": str(getattr(record, "submission_status", "") or ""),
        "package_name": str(getattr(record, "package_name", "") or ""),
        "version_name": str(getattr(record, "version_name", "") or ""),
        "version_code": str(getattr(record, "version_code", "") or ""),
        "build_id": str(getattr(record, "build_id", "") or ""),
        "release_channel": str(getattr(record, "release_channel", "") or ""),
        "owner_team": str(getattr(record, "owner_team", "") or ""),
        "template_type": str(getattr(record, "template_type", "") or ""),
        "selected_device_ids": list(getattr(record, "selected_device_ids", ()) or ()),
        "enabled_metrics": list(getattr(record, "enabled_metrics", ()) or ()),
        "sampling_interval_seconds": int(getattr(record, "sampling_interval_seconds", 0) or 0),
        "monitoring_backend": str(getattr(record, "monitoring_backend", "") or ""),
        "execute_immediately": bool(getattr(record, "execute_immediately", False)),
        "task_id": str(getattr(record, "task_id", "") or ""),
        "task_name": str(getattr(record, "task_name", "") or ""),
        "run_id": str(getattr(record, "run_id", "") or ""),
        "run_status": str(getattr(record, "run_status", "") or ""),
        "report_paths": dict(getattr(record, "report_paths", {}) or {}),
        "baseline_key": str(getattr(record, "baseline_key", "") or ""),
        "admission_case_id": str(getattr(record, "admission_case_id", "") or ""),
        "admission_status": str(getattr(record, "admission_status", "") or ""),
        "admission_final_decision": str(getattr(record, "admission_final_decision", "") or ""),
        "admission_error_code": str(getattr(record, "admission_error_code", "") or ""),
        "created_at": _isoformat_or_none(getattr(record, "created_at", None)),
        "created_by": str(getattr(record, "created_by", "") or ""),
        "updated_at": _isoformat_or_none(getattr(record, "updated_at", None)),
        "updated_by": str(getattr(record, "updated_by", "") or ""),
        "metadata": dict(getattr(record, "metadata", {}) or {}),
    }


def _handle_create_release_submission(args: argparse.Namespace) -> int:
    """Create one release submission, its linked task/run, and optionally execute immediately."""
    metadata = _parse_json_object(args.metadata)
    task_params = _parse_json_object(args.task_params)
    selected_device_ids = _expand_multi_value(args.devices)
    enabled_metrics = _expand_multi_value(args.metrics)

    bundle = create_v1_persistent_bootstrap(
        monitoring_backend=_resolve_monitoring_backend_override(args.monitoring_backend),
    )
    service = getattr(bundle, "release_submission_service", None)
    if service is None:
        raise SystemExit("Release submission service is unavailable.")

    sync_payload = None
    if not args.skip_device_sync and bundle.device_service is not None:
        sync_result = bundle.device_service.sync_devices(include_unavailable=True, mark_missing_offline=True)
        sync_payload = {
            "scanned_count": sync_result.scanned_count,
            "created_count": len(sync_result.created),
            "updated_count": len(sync_result.updated),
            "refreshed_count": len(sync_result.refreshed),
            "marked_offline_count": len(sync_result.marked_offline),
        }

    record = service.create_submission(
        source_platform=args.source_platform.strip(),
        source_request_id=args.source_request_id.strip(),
        package_name=args.package_name.strip(),
        version_name=args.version_name.strip(),
        version_code=args.version_code.strip(),
        build_id=args.build_id.strip(),
        release_channel=args.release_channel.strip(),
        owner_team=args.owner_team.strip(),
        submission_title=args.submission_title.strip(),
        template_type=args.template_type.strip(),
        selected_device_ids=selected_device_ids,
        enabled_metrics=enabled_metrics,
        sampling_interval_seconds=args.sampling_interval,
        monitoring_backend=args.monitoring_backend.strip(),
        execute_immediately=not bool(args.skip_execute),
        max_concurrency=args.max_concurrency,
        retry_count=args.retry_count,
        created_by=args.created_by.strip(),
        metadata=metadata,
        task_params=task_params,
    )
    payload = {
        "storage_mode": "persistent",
        "release_submission": _release_submission_payload(record),
    }
    if sync_payload is not None:
        payload["device_sync"] = sync_payload
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_list_release_submissions(args: argparse.Namespace) -> int:
    """List persisted release submission records with lightweight status fields."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "release_submission_service", None)
    if service is None:
        raise SystemExit("Release submission service is unavailable.")
    records = list(service.list_submissions(limit=args.limit))
    payload = {
        "storage_mode": "persistent",
        "submission_count": len(records),
        "release_submissions": [_release_submission_payload(item) for item in records],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_show_release_submission(args: argparse.Namespace) -> int:
    """Show one persisted release submission record in detail."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "release_submission_service", None)
    if service is None:
        raise SystemExit("Release submission service is unavailable.")
    try:
        record = service.get_submission(args.submission_id.strip())
    except Exception as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "release_submission": _release_submission_payload(record),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_sync_release_submission_admission(args: argparse.Namespace) -> int:
    """Sync one release submission with the current AdmissionCase decision."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "release_submission_service", None)
    if service is None:
        raise SystemExit("Release submission service is unavailable.")
    try:
        record = service.sync_admission_result(
            submission_id=args.submission_id.strip(),
            baseline_key=args.baseline_key.strip(),
            synced_by=args.synced_by.strip(),
        )
    except Exception as exc:
        raise SystemExit(str(exc)) from exc
    payload = {
        "storage_mode": "persistent",
        "release_submission": _release_submission_payload(record),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_register_release_webhook(args: argparse.Namespace) -> int:
    """Register one release platform webhook with the stable release contract."""
    bundle = create_v1_persistent_bootstrap()
    service = getattr(bundle, "integration_outbox_service", None)
    if service is None:
        raise SystemExit("Integration outbox service is unavailable.")
    event_types = tuple(_expand_multi_value(args.event_types))
    if hasattr(service, "register_release_webhook"):
        webhook = service.register_release_webhook(
            name=args.name.strip(),
            url=args.url.strip(),
            created_by=args.created_by.strip(),
            secret_hint=args.secret_hint.strip(),
            signing_secret=args.signing_secret.strip(),
            signature_key_id=args.signature_key_id.strip(),
            accepted_signature_key_ids=tuple(_expand_multi_value(args.accepted_signature_key_ids)),
            failure_policy=args.failure_policy.strip(),
            subscribed_event_types=event_types,
        )
    elif hasattr(service, "register_webhook"):
        fallback_event_types = event_types
        if not fallback_event_types and hasattr(service, "release_submission_event_types"):
            fallback_event_types = tuple(service.release_submission_event_types())
        webhook = service.register_webhook(
            name=args.name.strip(),
            url=args.url.strip(),
            subscribed_event_types=fallback_event_types,
            created_by=args.created_by.strip(),
            secret_hint=args.secret_hint.strip(),
            signing_secret=args.signing_secret.strip(),
            signature_key_id=args.signature_key_id.strip(),
            accepted_signature_key_ids=tuple(_expand_multi_value(args.accepted_signature_key_ids)),
            failure_policy=args.failure_policy.strip(),
            delivery_channel="release_submission",
        )
    else:
        raise SystemExit("Integration outbox service webhook APIs are unavailable.")
    payload = {
        "storage_mode": "persistent",
        "webhook": {
            "webhook_id": webhook.webhook_id,
            "name": webhook.name,
            "url": webhook.url,
            "subscribed_event_types": list(webhook.subscribed_event_types),
            "created_at": _isoformat_or_none(webhook.created_at),
            "created_by": webhook.created_by,
            "secret_hint": webhook.secret_hint,
            "signature_key_id": str(getattr(webhook, "signature_key_id", "") or "v1"),
            "accepted_signature_key_ids": list(getattr(webhook, "accepted_signature_key_ids", ()) or ()),
            "failure_policy": str(getattr(webhook, "failure_policy", "") or "retryable_http"),
            "delivery_channel": str(getattr(webhook, "delivery_channel", "") or "release_submission"),
            "callback_contract_version": "asl.webhook_callback.v1",
            "delivery_contract_version": "asl.release_submission.v1",
            "security_rules": [
                "non-local webhook requires https",
                "non-local webhook requires signing_secret",
                "delivery uses signature headers plus idempotency key",
                "release delivery body follows asl.release_submission.v1",
            ],
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
