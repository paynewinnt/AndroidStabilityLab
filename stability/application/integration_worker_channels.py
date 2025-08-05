from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .integration_outbox import (
    _filter_callable_kwargs,
    integration_worker_payload,
    run_integration_outbox_worker_rounds,
)
from .integration_reporting import build_im_acceptance_summary


@dataclass(frozen=True)
class ChannelWorkerCommand:
    webhook_names: Sequence[str] = ()
    limit_per_webhook: int = 20
    interval_seconds: int = 300
    max_rounds: int = 0
    max_runtime_seconds: int = 0
    stop_when_idle: bool = False
    daemon: bool = True


def run_im_notification_worker(service: object | None, command: ChannelWorkerCommand) -> dict[str, Any]:
    return _run_channel_worker(
        service,
        command,
        service_method_name="run_im_notification_worker",
        event_types_method_name="im_notification_event_types",
        chain_name="im_notification",
        mode="im_notify_worker",
        daemon_mode="im_notification_daemon",
        loop_mode="im_notification_worker_loop",
    )


def run_feishu_notify_worker(service: object | None, command: ChannelWorkerCommand) -> dict[str, Any]:
    payload = _run_channel_worker(
        service,
        command,
        service_method_name="run_feishu_notify_worker",
        event_types_method_name="feishu_bot_event_types",
        chain_name="feishu_bot",
        mode="feishu_notify_worker",
        daemon_mode="feishu_notify_daemon",
        loop_mode="feishu_notify_worker_loop",
    )
    payload["acceptance_summary"] = build_im_acceptance_summary(
        service,
        channel="feishu_bot",
        delivery_result=dict(payload.get("delivery", {}) or {}),
        selected_webhooks=tuple(payload.get("worker", {}).get("selected_webhooks", ()) or ()),
    )
    return payload


def run_defect_sync_worker(service: object | None, command: ChannelWorkerCommand) -> dict[str, Any]:
    return _run_channel_worker(
        service,
        command,
        service_method_name="run_defect_sync_worker",
        event_types_method_name="defect_sync_event_types",
        chain_name="defect_sync",
        mode="defect_sync_worker",
        daemon_mode="defect_sync_daemon",
        loop_mode="defect_sync_worker_loop",
    )


def run_release_sync_worker(service: object | None, command: ChannelWorkerCommand) -> dict[str, Any]:
    return _run_channel_worker(
        service,
        command,
        service_method_name="run_release_sync_worker",
        event_types_method_name="release_submission_event_types",
        chain_name="release_submission",
        mode="release_submission_worker",
        daemon_mode="release_submission_daemon",
        loop_mode="release_submission_worker_loop",
    )


def _run_channel_worker(
    service: object | None,
    command: ChannelWorkerCommand,
    *,
    service_method_name: str,
    event_types_method_name: str,
    chain_name: str,
    mode: str,
    daemon_mode: str,
    loop_mode: str,
) -> dict[str, Any]:
    if service is None:
        raise ValueError("Integration outbox service is unavailable.")
    webhook_names = _clean_values(command.webhook_names)
    event_types = tuple(_event_types(service, event_types_method_name))
    worker_method = getattr(service, service_method_name, None)
    if callable(worker_method):
        worker_result = dict(
            worker_method(
                **_filter_callable_kwargs(
                    worker_method,
                    webhook_names=tuple(webhook_names),
                    limit_per_webhook=max(int(command.limit_per_webhook), 0),
                    interval_seconds=max(int(command.interval_seconds), 0),
                    max_rounds=max(int(command.max_rounds), 0),
                    max_runtime_seconds=max(int(command.max_runtime_seconds), 0),
                    stop_when_idle=bool(command.stop_when_idle),
                    daemon=bool(command.daemon),
                )
            )
        )
        selected_webhooks = _selected_webhooks(worker_result, webhook_names)
        rounds_executed = _rounds_executed(worker_result, command.daemon)
    else:
        worker_result = run_integration_outbox_worker_rounds(
            service,
            webhook_names=tuple(webhook_names),
            event_types=event_types,
            limit_per_webhook=max(int(command.limit_per_webhook), 0),
            rounds=max(int(command.max_rounds), 1) if int(command.max_rounds) > 0 else 1,
            interval_seconds=max(int(command.interval_seconds), 0),
            stop_when_idle=bool(command.stop_when_idle),
            daemon=bool(command.daemon),
            max_runtime_seconds=max(int(command.max_runtime_seconds), 0),
            chain_name=chain_name,
        )
        selected_webhooks = list(worker_result.get("selected_webhooks", []) or ())
        rounds_executed = int(worker_result.get("rounds_executed", 0) or 0)
    return {
        "storage_mode": "persistent",
        "mode": mode,
        "worker": integration_worker_payload(
            service,
            mode=daemon_mode if bool(command.daemon) else loop_mode,
            webhook_names=selected_webhooks,
            event_types=event_types,
            rounds_executed=rounds_executed,
            stop_when_idle=bool(command.stop_when_idle),
            interval_seconds=max(int(command.interval_seconds), 0),
        ),
        "delivery": worker_result,
    }


def _event_types(service: object, method_name: str) -> list[str]:
    method = getattr(service, method_name, None)
    if not callable(method):
        return []
    return [str(item).strip() for item in (method() or ()) if str(item).strip()]


def _selected_webhooks(worker_result: dict[str, Any], requested_names: Sequence[str]) -> list[str]:
    selected = [str(item).strip() for item in (worker_result.get("selected_webhooks", ()) or ()) if str(item).strip()]
    if selected:
        return selected
    selected = [str(item).strip() for item in requested_names if str(item).strip()]
    if selected:
        return selected
    return [
        str(item.get("webhook_name", "") or "").strip()
        for item in (worker_result.get("delivery_rounds", ()) or ())
        if isinstance(item, dict) and str(item.get("webhook_name", "") or "").strip()
    ]


def _rounds_executed(worker_result: dict[str, Any], daemon: bool) -> int:
    rounds = int(worker_result.get("rounds_executed", 1 if not daemon else 0) or 0)
    return rounds if rounds > 0 else 1


def _clean_values(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        for item in str(raw or "").split(","):
            value = item.strip()
            if value and value not in seen:
                result.append(value)
                seen.add(value)
    return result
