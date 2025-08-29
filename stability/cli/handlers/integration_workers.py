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
from stability.cli.utils import _expand_multi_value
from stability.time_utils import format_beijing_datetime_or_original
from stability.web import serve_web_portal

# Split from stability.cli.task_create; integration_workers.py owns this command/payload group.


def _isoformat_or_none(value: object) -> str | None:
    return format_beijing_datetime_or_original(value)

def _run_integration_outbox_worker_rounds(
    service: object,
    *,
    webhook_names: Sequence[str],
    event_types: Sequence[str],
    limit_per_webhook: int,
    rounds: int,
    interval_seconds: int,
    stop_when_idle: bool,
    daemon: bool = False,
    max_runtime_seconds: int = 0,
    chain_name: str = "integration_outbox",
) -> dict[str, object]:
    selected_webhooks = _select_webhook_names(
        service=service,
        webhook_names=tuple(_expand_multi_value(webhook_names)),
    )
    if daemon and hasattr(service, "run_delivery_daemon"):
        return dict(
            service.run_delivery_daemon(
                webhook_names=tuple(selected_webhooks),
                event_types=tuple(event_types),
                limit_per_webhook=max(int(limit_per_webhook), 0),
                interval_seconds=max(int(interval_seconds), 0),
                max_rounds=max(int(rounds), 0),
                max_runtime_seconds=max(int(max_runtime_seconds), 0),
                stop_when_idle=bool(stop_when_idle),
                chain_name=chain_name,
            )
        )
    if hasattr(service, "run_delivery_worker"):
        return _run_integration_outbox_worker_rounds_new_api(
            service,
            webhook_names=tuple(selected_webhooks),
            event_types=tuple(event_types),
            limit_per_webhook=max(int(limit_per_webhook), 0),
            rounds=max(int(rounds), 1),
            interval_seconds=max(int(interval_seconds), 0),
            stop_when_idle=bool(stop_when_idle),
        )
    if not hasattr(service, "deliver_pending_events"):
        raise SystemExit("Integration outbox service cannot deliver events.")
    target_names = [item for item in selected_webhooks if str(item).strip()]
    per_round: list[dict[str, object]] = []
    aggregate = {
        "attempted_count": 0,
        "delivered_count": 0,
        "failed_count": 0,
        "dead_lettered_count": 0,
        "skipped_count": 0,
        "alert_emitted_count": 0,
        "remaining_pending_count": 0,
    }
    rounds_executed = 0
    idle_stop = False
    for round_index in range(max(int(rounds), 1)):
        round_results: list[dict[str, object]] = []
        round_attempted = 0
        round_remaining = 0
        for webhook_name in target_names:
            result = dict(
                service.deliver_pending_events(
                    webhook_name=webhook_name,
                    event_types=tuple(event_types),
                    limit=max(int(limit_per_webhook), 0),
                )
            )
            round_payload = _integration_delivery_result_payload(result)
            round_results.append(round_payload)
            round_attempted += int(round_payload.get("attempted_count", 0) or 0)
            round_remaining += int(round_payload.get("remaining_pending_count", 0) or 0)
            for key in aggregate:
                aggregate[key] += int(round_payload.get(key, 0) or 0)
        rounds_executed += 1
        per_round.append(
            {
                "round_index": rounds_executed,
                "webhook_count": len(target_names),
                "attempted_count": round_attempted,
                "remaining_pending_count": round_remaining,
                "results": round_results,
            }
        )
        if stop_when_idle and round_attempted <= 0 and round_remaining <= 0:
            idle_stop = True
            break
        if interval_seconds > 0 and round_index + 1 < max(int(rounds), 1):
            time.sleep(interval_seconds)
    return {
        "mode": "delivery_worker_loop",
        "selected_webhooks": target_names,
        "requested_rounds": max(int(rounds), 1),
        "rounds_executed": rounds_executed,
        "stopped_when_idle": idle_stop,
        "event_types": list(event_types),
        "limit_per_webhook": max(int(limit_per_webhook), 0),
        "aggregate": aggregate,
        "rounds": per_round,
    }


def _run_integration_outbox_worker_rounds_new_api(
    service: object,
    *,
    webhook_names: tuple[str, ...],
    event_types: tuple[str, ...],
    limit_per_webhook: int,
    rounds: int,
    interval_seconds: int,
    stop_when_idle: bool,
) -> dict[str, object]:
    target_names = [item for item in webhook_names if str(item).strip()]
    per_round: list[dict[str, object]] = []
    aggregate = {
        "attempted_count": 0,
        "delivered_count": 0,
        "failed_count": 0,
        "dead_lettered_count": 0,
        "skipped_count": 0,
        "deduplicated_count": 0,
        "alert_emitted_count": 0,
    }
    rounds_executed = 0
    idle_stop = False
    for round_index in range(max(int(rounds), 1)):
        result = dict(
            service.run_delivery_worker(  # type: ignore[attr-defined]
                webhook_names=tuple(target_names),
                event_types=tuple(event_types),
                limit_per_webhook=limit_per_webhook,
            )
        )
        deliveries = [dict(item) for item in (result.get("delivery_rounds") or ()) if isinstance(item, Mapping)]
        round_attempted = 0
        round_remaining = 0
        for delivery in deliveries:
            for key in aggregate:
                aggregate[key] += int(delivery.get(key, 0) or 0)
            round_attempted += int(delivery.get("attempted_count", 0) or 0)
            round_remaining += int(delivery.get("remaining_pending_count", 0) or 0)
        rounds_executed += 1
        per_round.append(
            {
                "round_index": rounds_executed,
                "webhook_count": len(target_names),
                "attempted_count": round_attempted,
                "remaining_pending_count": round_remaining,
                "results": deliveries,
                "worker": result.get("worker"),
            }
        )
        if stop_when_idle and round_attempted <= 0 and round_remaining <= 0:
            idle_stop = True
            break
        if interval_seconds > 0 and round_index + 1 < max(int(rounds), 1):
            time.sleep(interval_seconds)
    aggregate["remaining_pending_count"] = (
        sum(int(item.get("remaining_pending_count", 0) or 0) for item in (per_round[-1].get("results", ()) if per_round else ()))
    )
    return {
        "mode": "delivery_worker_loop",
        "selected_webhooks": target_names,
        "requested_rounds": max(int(rounds), 1),
        "rounds_executed": rounds_executed,
        "stopped_when_idle": bool(idle_stop),
        "event_types": list(event_types),
        "limit_per_webhook": max(int(limit_per_webhook), 0),
        "aggregate": aggregate,
        "rounds": per_round,
    }


def _select_webhook_names(service: object, webhook_names: Sequence[str]) -> list[str]:
    requested = {str(item).strip() for item in webhook_names if str(item).strip()}
    if hasattr(service, "list_webhooks"):
        available_webhooks = list(getattr(service, "list_webhooks")())
        names = [str(getattr(item, "name", "") or "") for item in available_webhooks if str(getattr(item, "name", "") or "")]
    else:
        names = [str(item).strip() for item in webhook_names if str(item).strip()]
    selected = [name for name in names if not requested or name in requested]
    if requested and not selected:
        raise SystemExit("No matching integration webhook registrations were found.")
    return selected or names


def _replay_dead_letter_events(
    service: object,
    *,
    event_ids: Sequence[str],
    event_types: Sequence[str],
    limit: int,
    execute: bool,
    replayed_by: str,
) -> dict[str, object]:
    event_id_filter = {item for item in event_ids if str(item).strip()}
    event_type_filter = {item for item in event_types if str(item).strip()}
    all_events = list(service.list_events(limit=0))
    dead_letters = [
        item
        for item in all_events
        if str(getattr(item, "delivery_status", "") or "") == "dead_letter"
        and (not event_id_filter or str(getattr(item, "event_id", "") or "") in event_id_filter)
        and (not event_type_filter or str(getattr(item, "event_type", "") or "") in event_type_filter)
    ]
    if limit > 0:
        dead_letters = dead_letters[:limit]
    selected_ids = [str(getattr(item, "event_id", "") or "") for item in dead_letters]
    preview_events = [_integration_outbox_event_ops_payload(item) for item in dead_letters]
    if not execute:
        return {
            "mode": "preview",
            "matched_count": len(preview_events),
            "selected_event_ids": selected_ids,
            "events": preview_events,
        }

    if hasattr(service, "replay_dead_lettered_events"):
        replay_webhook_name = _resolve_replay_webhook_name(service)
        raw_result = dict(
            service.replay_dead_lettered_events(  # type: ignore[attr-defined]
                webhook_name=replay_webhook_name,
                event_ids=tuple(selected_ids),
                limit=limit,
                replayed_by=replayed_by,
            )
        )
        replayed_event_ids = list(raw_result.get("replayed_event_ids") or ())
        raw_result.setdefault("mode", "execute")
        raw_result.setdefault("matched_count", len(preview_events))
        raw_result.setdefault("selected_event_ids", selected_ids)
        raw_result.setdefault("events", preview_events)
        raw_result.setdefault("replayed_count", len(replayed_event_ids))
        raw_result["receipts"] = [
            _integration_outbox_replay_receipt_payload(
                event_id=event_id,
                event=next(
                    (item for item in dead_letters if str(getattr(item, "event_id", "") or "") == event_id),
                    None,
                ),
                replayed_by=replayed_by,
            )
            for event_id in replayed_event_ids
        ]
        return raw_result

    if hasattr(service, "requeue_dead_letters"):
        raw_result = dict(
            service.requeue_dead_letters(
                event_ids=tuple(selected_ids),
                replayed_by=replayed_by,
            )
        )
        raw_result.setdefault("mode", "execute")
        raw_result.setdefault("matched_count", len(preview_events))
        raw_result.setdefault("selected_event_ids", selected_ids)
        raw_result.setdefault("events", preview_events)
        return raw_result

    required_attrs = ("_load_event_registry", "_save_registry", "_events_path")
    if not all(hasattr(service, name) for name in required_attrs):
        raise SystemExit("Integration outbox service does not expose a dead-letter replay API yet.")

    raw_registry = list(service._load_event_registry())  # type: ignore[attr-defined]
    replayed_ids: list[str] = []
    updated_registry: list[dict[str, object]] = []
    selected_id_set = set(selected_ids)
    for entry in raw_registry:
        item = dict(entry)
        event_id = str(item.get("event_id", "") or "")
        if event_id in selected_id_set and str(item.get("delivery_status", "") or "") == "dead_letter":
            item["delivery_status"] = "pending"
            item["attempt_count"] = 0
            item["last_attempt_at"] = None
            item["delivered_at"] = None
            item["last_error"] = ""
            item["next_retry_at"] = None
            item["signature"] = ""
            item["retry_backoff_seconds"] = 0
            item["last_response_code"] = None
            item["dead_lettered_at"] = None
            item["alert_status"] = "replayed"
            item["alert_count"] = 0
            item["last_alert_at"] = None
            replayed_ids.append(event_id)
        updated_registry.append(item)
    service._save_registry(service._events_path, updated_registry)  # type: ignore[attr-defined]
    receipt_items = [
        _integration_outbox_replay_receipt_payload(
            event_id=event_id,
            event=next(
                (item for item in dead_letters if str(getattr(item, "event_id", "") or "") == event_id),
                None,
            ),
            replayed_by=replayed_by,
        )
        for event_id in replayed_ids
    ]
    return {
        "mode": "execute",
        "matched_count": len(preview_events),
        "replayed_count": len(replayed_ids),
        "selected_event_ids": selected_ids,
        "replayed_event_ids": replayed_ids,
        "events": preview_events,
        "receipts": receipt_items,
    }


def _resolve_replay_webhook_name(service: object) -> str:
    webhooks = getattr(service, "list_webhooks", lambda: ())()
    first_webhook = next(iter(webhooks), None)
    if first_webhook is None:
        return "integration_outbox_worker"
    return str(getattr(first_webhook, "name", "") or "integration_outbox_worker")


def _integration_outbox_replay_receipt_payload(
    *, event_id: str, event: object | None, replayed_by: str
) -> dict[str, object]:
    raw_event_id = str(event_id or "").strip()
    event_payload = _integration_outbox_event_ops_payload(event) if event is not None else {}
    return {
        "event_id": raw_event_id,
        "replayed_by": replayed_by,
        "receipt_key": f"asl.outbox.replay_receipt.v1:{raw_event_id}",
        "idempotency_key": str(
            event_payload.get("idempotency_key", f"asl.outbox.idempotency.v1:{raw_event_id}")
        ),
        "status": "requeued_pending",
    }


def _integration_worker_payload(
    service: object,
    *,
    mode: str,
    webhook_names: Sequence[str],
    event_types: Sequence[str],
    rounds_executed: int,
    stop_when_idle: bool,
    interval_seconds: int | None = None,
) -> dict[str, object]:
    available_webhooks = list(getattr(service, "list_webhooks", lambda: ())())
    worker_status = {}
    worker_status_getter = getattr(service, "get_worker_status", None)
    if callable(worker_status_getter):
        try:
            worker_status = _normalize_integration_worker_status(worker_status_getter())
        except Exception:
            worker_status = {}
    return {
        "mode": mode,
        "scope": "local_ops",
        "supports_run_delivery_worker": callable(getattr(service, "run_delivery_worker", None)),
        "supports_run_delivery_daemon": callable(getattr(service, "run_delivery_daemon", None)),
        "supports_replay_dead_letter_api": callable(getattr(service, "replay_dead_lettered_events", None)),
        "supports_delivery_receipts": True,
        "supports_consumer_receipts": True,
        "supports_operator_receipts": True,
        "supports_replay_receipts": True,
        "selected_webhooks": [item for item in webhook_names if str(item).strip()],
        "registered_webhook_names": [
            str(getattr(item, "name", "") or "")
            for item in available_webhooks
            if str(getattr(item, "name", "") or "")
        ],
        "event_types": [item for item in event_types if str(item).strip()],
        "delivery_interval_seconds": getattr(service, "_delivery_interval", None),
        "retry_delay_seconds": getattr(service, "_retry_delay", None),
        "max_retry_delay_seconds": getattr(service, "_max_retry_delay", None),
        "dead_letter_threshold": getattr(service, "_dead_letter_threshold", None),
        "retry_alert_threshold": getattr(service, "_retry_alert_threshold", None),
        "worker_status": worker_status,
        "rounds_executed": int(rounds_executed),
        "stop_when_idle": bool(stop_when_idle),
        "interval_seconds": interval_seconds,
        "worker_commands": {
            "single_round": "python -m stability.cli deliver-integration-outbox --webhook-name <name>",
            "worker_loop": "python -m stability.cli run-integration-outbox-worker --webhook-name <name>",
            "daemon_loop": "python -m stability.cli run-integration-outbox-worker --daemon --webhook-name <name>",
            "ci_callback_daemon": "python -m stability.cli run-ci-admission-sync-worker --webhook-name <name>",
            "register_im_webhook": "python -m stability.cli register-im-webhook --name <name> --url <https-url>",
            "im_notification_daemon": "python -m stability.cli run-im-notify-worker --daemon --webhook-name <name>",
            "register_feishu_webhook": "python -m stability.cli register-feishu-webhook --name <name> --url <https-url>",
            "feishu_notify_daemon": "python -m stability.cli run-feishu-notify-worker --daemon --webhook-name <name>",
            "register_defect_webhook": "python -m stability.cli register-defect-webhook --name <name> --url <https-url>",
            "defect_sync_daemon": "python -m stability.cli run-defect-sync-worker --daemon --webhook-name <name>",
            "create_release_submission": "python -m stability.cli create-release-submission --source-platform <platform> --source-request-id <id> --package-name <pkg>",
            "register_release_webhook": "python -m stability.cli register-release-webhook --name <name> --url <https-url>",
            "release_submission_daemon": "python -m stability.cli run-release-sync-worker --daemon --webhook-name <name>",
            "dead_letter_replay": "python -m stability.cli replay-integration-dead-letters --execute",
        },
    }


def _normalize_integration_worker_status(item: object) -> dict[str, object]:
    if isinstance(item, Mapping):
        return {str(key): value for key, value in item.items()}
    return {
        "worker_name": str(getattr(item, "worker_name", "") or ""),
        "status": str(getattr(item, "status", "") or ""),
        "worker_mode": str(getattr(item, "worker_mode", "") or ""),
        "daemon_enabled": bool(getattr(item, "daemon_enabled", False)),
        "daemon_pid": getattr(item, "daemon_pid", None),
        "daemon_heartbeat_at": _isoformat_or_none(getattr(item, "daemon_heartbeat_at", None)),
        "last_started_at": _isoformat_or_none(getattr(item, "last_started_at", None)),
        "last_finished_at": _isoformat_or_none(getattr(item, "last_finished_at", None)),
        "last_success_at": _isoformat_or_none(getattr(item, "last_success_at", None)),
        "last_error": str(getattr(item, "last_error", "") or ""),
        "run_count": int(getattr(item, "run_count", 0) or 0),
        "delivered_count": int(getattr(item, "delivered_count", 0) or 0),
        "failed_count": int(getattr(item, "failed_count", 0) or 0),
        "replay_count": int(getattr(item, "replay_count", 0) or 0),
        "configured_webhooks": list(getattr(item, "configured_webhooks", ()) or ()),
        "configured_event_types": list(getattr(item, "configured_event_types", ()) or ()),
        "schedule_interval_seconds": int(getattr(item, "schedule_interval_seconds", 0) or 0),
        "chain_name": str(getattr(item, "chain_name", "") or ""),
        "last_delivery_receipt_id": str(getattr(item, "last_delivery_receipt_id", "") or ""),
        "last_operator_receipt_id": str(getattr(item, "last_operator_receipt_id", "") or ""),
        "last_run_summary": dict(getattr(item, "last_run_summary", {}) or {}),
    }


def _integration_delivery_result_payload(result: dict[str, object]) -> dict[str, object]:
    webhook_name = str(result.get("webhook_name", "") or "")
    delivered_event_ids = [str(item) for item in (result.get("delivered_event_ids", []) or []) if str(item).strip()]
    return {
        **result,
        "webhook_name": webhook_name,
        "delivered_event_ids": delivered_event_ids,
        "receipt_keys": [f"asl.outbox.receipt.v1:{webhook_name}:{event_id}" for event_id in delivered_event_ids],
        "idempotency_scope": "event_id_per_webhook",
    }


def _integration_outbox_event_ops_payload(event: object) -> dict[str, object]:
    event_id = str(getattr(event, "event_id", "") or "")
    idempotency_key = str(
        getattr(event, "idempotency_key", "")
        or f"asl.outbox.idempotency.v1:{event_id}"
    )
    webhook_receipt_status = "transport_ack" if str(getattr(event, "delivery_status", "") or "") == "delivered" else "not_acknowledged"
    consumer_receipts = [
        _normalize_outbox_consumer_receipt(item)
        for item in (getattr(event, "consumer_receipts", ()) or ())
        if item is not None
    ]
    replay_receipts = [
        {
            "receipt_id": str(getattr(item, "receipt_id", "") or ""),
            "event_id": str(getattr(item, "event_id", "") or ""),
            "webhook_name": str(getattr(item, "webhook_name", "") or ""),
            "idempotency_key": str(getattr(item, "idempotency_key", "") or ""),
            "replayed_at": _isoformat_or_none(getattr(item, "replayed_at", None)),
            "replayed_by": str(getattr(item, "replayed_by", "") or ""),
            "status": str(getattr(item, "status", "") or ""),
            "replay_token": str(getattr(item, "replay_token", "") or ""),
            "notes": str(getattr(item, "notes", "") or ""),
        }
        for item in (getattr(event, "replay_receipts", ()) or ())
        if item is not None
    ]
    operator_receipts = [
        {
            "receipt_id": str(getattr(item, "receipt_id", "") or ""),
            "event_id": str(getattr(item, "event_id", "") or ""),
            "webhook_name": str(getattr(item, "webhook_name", "") or ""),
            "action": str(getattr(item, "action", "") or ""),
            "operator_id": str(getattr(item, "operator_id", "") or ""),
            "recorded_at": _isoformat_or_none(getattr(item, "recorded_at", None)),
            "status": str(getattr(item, "status", "") or ""),
            "session_source": str(getattr(item, "session_source", "") or ""),
            "audit_source": dict(getattr(item, "audit_source", {}) or {}),
            "notes": str(getattr(item, "notes", "") or ""),
        }
        for item in (getattr(event, "operator_receipts", ()) or ())
        if item is not None
    ]
    return {
        "event_id": event_id,
        "event_type": str(getattr(event, "event_type", "") or ""),
        "target_type": str(getattr(event, "target_type", "") or ""),
        "target_id": str(getattr(event, "target_id", "") or ""),
        "delivery_status": str(getattr(event, "delivery_status", "") or "pending"),
        "attempt_count": int(getattr(event, "attempt_count", 0) or 0),
        "last_response_code": getattr(event, "last_response_code", None),
        "last_error": str(getattr(event, "last_error", "") or ""),
        "next_retry_at": _isoformat_or_none(getattr(event, "next_retry_at", None)),
        "dead_lettered_at": _isoformat_or_none(getattr(event, "dead_lettered_at", None)),
        "failure_category": str(getattr(event, "failure_category", "") or ""),
        "signature": str(getattr(event, "signature", "") or ""),
        "idempotency_key": idempotency_key,
        "consumer_receipts": consumer_receipts,
        "consumer_receipt_count": len(consumer_receipts),
        "replay_receipts": replay_receipts,
        "replay_receipt_count": len(replay_receipts),
        "operator_receipts": operator_receipts,
        "operator_receipt_count": len(operator_receipts),
        "receipt_keys": [f"asl.outbox.receipt.v1:{event_id}"],
        "receipt": {
            "receipt_key": f"asl.outbox.receipt.v1:{event_id}",
            "receipt_status": webhook_receipt_status,
            "contract": "webhook_transport_ack_only",
        },
    }


def _normalize_outbox_consumer_receipt(receipt: Any) -> dict[str, object]:
    if isinstance(receipt, Mapping):
        raw = dict(receipt)
        received_at = raw.get("received_at")
    else:
        raw = None
        received_at = getattr(receipt, "received_at", None)
    return {
        "receipt_id": str((raw or {}).get("receipt_id", getattr(receipt, "receipt_id", "")) or ""),
        "event_id": str((raw or {}).get("event_id", getattr(receipt, "event_id", "")) or ""),
        "webhook_name": str((raw or {}).get("webhook_name", getattr(receipt, "webhook_name", "")) or ""),
        "idempotency_key": str((raw or {}).get("idempotency_key", getattr(receipt, "idempotency_key", "")) or ""),
        "received_at": _isoformat_or_none(received_at),
        "status": str((raw or {}).get("status", getattr(receipt, "status", "")) or "delivered"),
        "response_code": (raw or {}).get("response_code", getattr(receipt, "response_code", None)),
        "consumer_id": str((raw or {}).get("consumer_id", getattr(receipt, "consumer_id", "")) or ""),
        "consumer_receipt_id": str(
            (raw or {}).get("consumer_receipt_id", getattr(receipt, "consumer_receipt_id", "")) or ""
        ),
        "response_excerpt": str((raw or {}).get("response_excerpt", getattr(receipt, "response_excerpt", "")) or ""),
        "receipt_key": (
            "asl.outbox.consumer_receipt.v1:"
            f"{str((raw or {}).get('event_id', getattr(receipt, 'event_id', '') ) or '')}:"
            f"{str((raw or {}).get('receipt_id', getattr(receipt, 'receipt_id', '') ) or '')}"
        ),
    }


def _ci_admission_decision_payload(event: object) -> dict[str, object]:
    event_payload = dict(getattr(event, "payload", {}) or {})
    return {
        "event_id": str(getattr(event, "event_id", "")),
        "event_type": str(getattr(event, "event_type", "")),
        "target_type": str(getattr(event, "target_type", "")),
        "target_id": str(getattr(event, "target_id", "")),
        "baseline_key": str(getattr(event, "target_id", "")),
        "created_at": _isoformat_or_none(getattr(event, "created_at", None)),
        "created_by": str(getattr(event, "created_by", "")),
        "session_source": str(getattr(event, "session_source", "")),
        "audit_source": dict(getattr(event, "audit_source", {}) or {}),
        "case_id": str(event_payload.get("case_id", "") or ""),
        "case_revision": int(event_payload.get("case_revision", 0) or 0),
        "status": str(event_payload.get("status", "") or ""),
        "assignee": dict(event_payload.get("assignee", {}) or {}),
        "final_reviewer": dict(event_payload.get("final_reviewer", {}) or {}),
        "automatic_decision": str(event_payload.get("automatic_decision", "") or ""),
        "final_decision": str(event_payload.get("final_decision", "") or ""),
        "reason": str(event_payload.get("reason", "") or event_payload.get("final_review_opinion", "") or ""),
        "comment": str(event_payload.get("comment", "") or ""),
        "evidence_paths": list(event_payload.get("evidence_paths") or ()),
        "case_trace_summary": dict(event_payload.get("case_trace_summary", {}) or {}),
        "source_refs": dict(event_payload.get("source_refs", {}) or {}),
        "delivery_status": str(getattr(event, "delivery_status", "")),
        "attempt_count": int(getattr(event, "attempt_count", 0) or 0),
    }


def _is_local_web_host(host: str) -> bool:
    value = str(host or "").strip().lower()
    if value in {"127.0.0.1", "localhost", "::1"}:
        return True
    return value.startswith("127.")
