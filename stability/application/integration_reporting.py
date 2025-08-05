from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence


def build_im_acceptance_summary(
    service: object | None,
    *,
    channel: str = "all",
    delivery_result: Mapping[str, object] | None = None,
    selected_webhooks: Sequence[str] = (),
    limit: int = 0,
) -> dict[str, object]:
    if service is None:
        raise ValueError("Integration outbox service is unavailable.")
    channel_key = str(channel or "all").strip() or "all"
    webhooks = list(getattr(service, "list_webhooks", lambda: ())())
    selected_webhook_names = {str(item).strip() for item in selected_webhooks if str(item).strip()}
    channels = {"im_notify", "feishu_bot"} if channel_key in {"", "all", "im"} else {channel_key}
    target_webhooks = [
        item
        for item in webhooks
        if str(getattr(item, "delivery_channel", "") or "") in channels
        and (not selected_webhook_names or str(getattr(item, "name", "") or "") in selected_webhook_names)
    ]
    target_webhook_names = [str(getattr(item, "name", "") or "") for item in target_webhooks]
    target_event_types = _im_acceptance_event_types(service, channel_key)
    events = _im_acceptance_events(
        service,
        target_event_types=target_event_types,
        target_webhook_names=target_webhook_names,
        limit=limit,
    )
    if not selected_webhooks and limit <= 0:
        service_summary = _service_im_acceptance_summary(service, channel=channel_key)
        if service_summary is not None:
            result = _operator_acceptance_summary_fields(
                service_summary,
                channel=channel_key,
                delivery_result=delivery_result,
            )
            result["acceptance_status"] = _im_acceptance_status_payload(
                events=events,
                delivered_count=int(result.get("delivered_count", result.get("success_count", 0)) or 0),
                retry_pending_count=int(result.get("retry_pending_count", 0) or 0),
                dead_letter_count=int(result.get("dead_letter_count", 0) or 0),
                consumer_receipt_count=int(result.get("consumer_receipt_count", 0) or 0),
                duplicate_risk_level=str(
                    dict(result.get("duplicate_risk", {}) or {}).get("level", "unknown") or "unknown"
                ),
            )
            return result
    return _events_acceptance_summary(
        events=events,
        target_webhooks=target_webhooks,
        target_event_types=target_event_types,
        channel_key=channel_key,
        delivery_result=delivery_result,
    )


def _events_acceptance_summary(
    *,
    events: Sequence[object],
    target_webhooks: Sequence[object],
    target_event_types: set[str],
    channel_key: str,
    delivery_result: Mapping[str, object] | None,
) -> dict[str, object]:
    status_counts: dict[str, int] = {}
    consumer_receipt_count = 0
    retry_count = 0
    dead_letter_count = 0
    delivered_count = 0
    failed_count = 0
    deduplicated_count = _deduplicated_count_from_delivery_result(dict(delivery_result or {}))
    idempotency_seen: set[tuple[str, str]] = set()
    duplicate_candidates = 0
    for item in events:
        status = str(getattr(item, "delivery_status", "") or "pending")
        status_counts[status] = status_counts.get(status, 0) + 1
        attempts = int(getattr(item, "attempt_count", 0) or 0)
        retry_count += max(attempts - 1, 0)
        if status == "delivered":
            delivered_count += 1
        if status in {"failed", "retry_pending"}:
            failed_count += 1
        if status == "dead_letter":
            failed_count += 1
            dead_letter_count += 1
        receipts = list(getattr(item, "consumer_receipts", ()) or ())
        consumer_receipt_count += len(receipts)
        for receipt in receipts:
            key = (
                str(getattr(receipt, "webhook_name", "") or ""),
                str(getattr(receipt, "idempotency_key", "") or ""),
            )
            if key[1] and key in idempotency_seen:
                duplicate_candidates += 1
            if key[1]:
                idempotency_seen.add(key)

    duplicate_risk_level = "low"
    duplicate_risk_reasons: list[str] = []
    if deduplicated_count > 0 or duplicate_candidates > 0:
        duplicate_risk_level = "medium"
        duplicate_risk_reasons.append("检测到幂等命中或疑似重复 receipt，请核对飞书侧消息是否重复。")
    if retry_count > 0 and consumer_receipt_count < delivered_count:
        duplicate_risk_level = "medium"
        duplicate_risk_reasons.append("存在重试且部分 delivered 事件缺 consumer_receipt，需用飞书消息时间线交叉确认。")
    if dead_letter_count > 0:
        duplicate_risk_level = "high"
        duplicate_risk_reasons.append("存在 dead-letter，回放前需确认不会对真实群产生重复通知。")
    if not duplicate_risk_reasons:
        duplicate_risk_reasons.append("当前摘要未发现明显重复投递风险。")

    return {
        "contract_version": "asl.im_feishu_acceptance_summary.v1",
        "channel": channel_key,
        "webhook_names": [str(getattr(item, "name", "") or "") for item in target_webhooks],
        "event_types": sorted(target_event_types),
        "total_event_count": len(events),
        "delivered_count": delivered_count,
        "failed_count": failed_count,
        "retry_count": retry_count,
        "retry_pending_count": status_counts.get("retry_pending", 0),
        "dead_letter_count": dead_letter_count,
        "consumer_receipt_count": consumer_receipt_count,
        "deduplicated_count": deduplicated_count,
        "status_counts": status_counts,
        "duplicate_risk": {
            "level": duplicate_risk_level,
            "duplicate_candidate_count": duplicate_candidates,
            "reasons": duplicate_risk_reasons,
        },
        "noise_check": _noise_check_payload(),
        "acceptance_status": _im_acceptance_status_payload(
            events=events,
            delivered_count=delivered_count,
            retry_pending_count=status_counts.get("retry_pending", 0),
            dead_letter_count=dead_letter_count,
            consumer_receipt_count=consumer_receipt_count,
            duplicate_risk_level=duplicate_risk_level,
        ),
        "checklist": _im_acceptance_checklist_payload(),
    }


def _service_im_acceptance_summary(service: object, *, channel: str) -> dict[str, object] | None:
    if channel == "feishu_bot" and callable(getattr(service, "build_feishu_delivery_acceptance_summary", None)):
        return dict(service.build_feishu_delivery_acceptance_summary())
    if channel == "im_notify" and callable(getattr(service, "build_im_delivery_acceptance_summary", None)):
        return dict(service.build_im_delivery_acceptance_summary())
    if channel in {"", "all", "im"} and callable(getattr(service, "build_delivery_acceptance_summary", None)):
        event_types = _im_acceptance_event_types(service, channel)
        return dict(
            service.build_delivery_acceptance_summary(
                name="im_feishu",
                delivery_channels=("im_notify", "feishu_bot"),
                event_types=tuple(sorted(event_types)),
            )
        )
    return None


def _operator_acceptance_summary_fields(
    summary: Mapping[str, object],
    *,
    channel: str,
    delivery_result: Mapping[str, object] | None = None,
) -> dict[str, object]:
    result = dict(summary)
    delivered_count = int(result.get("delivered_count", result.get("success_count", 0)) or 0)
    retry_count = int(result.get("retry_count", 0) or 0)
    dead_letter_count = int(result.get("dead_letter_count", 0) or 0)
    consumer_receipt_count = int(result.get("consumer_receipt_count", 0) or 0)
    deduplicated_count = int(result.get("deduplicated_count", 0) or 0)
    deduplicated_count += _deduplicated_count_from_delivery_result(dict(delivery_result or {}))
    duplicate_risk_level = "low"
    duplicate_risk_reasons: list[str] = []
    if deduplicated_count > 0:
        duplicate_risk_level = "medium"
        duplicate_risk_reasons.append("检测到幂等命中，请核对飞书侧消息是否重复。")
    if retry_count > 0 and consumer_receipt_count < delivered_count:
        duplicate_risk_level = "medium"
        duplicate_risk_reasons.append("存在重试且部分 delivered 事件缺 consumer_receipt，需用飞书消息时间线交叉确认。")
    if dead_letter_count > 0:
        duplicate_risk_level = "high"
        duplicate_risk_reasons.append("存在 dead-letter，回放前需确认不会对真实群产生重复通知。")
    if not duplicate_risk_reasons:
        duplicate_risk_reasons.append("当前摘要未发现明显重复投递风险。")
    result.update(
        {
            "contract_version": "asl.im_feishu_acceptance_summary.v1",
            "channel": channel,
            "delivered_count": delivered_count,
            "success_count": delivered_count,
            "deduplicated_count": deduplicated_count,
            "duplicate_risk": {
                "level": duplicate_risk_level,
                "duplicate_candidate_count": 0,
                "reasons": duplicate_risk_reasons,
            },
            "noise_check": _noise_check_payload(),
            "acceptance_status": _im_acceptance_status_payload(
                events=(),
                delivered_count=delivered_count,
                retry_pending_count=int(result.get("retry_pending_count", 0) or 0),
                dead_letter_count=dead_letter_count,
                consumer_receipt_count=consumer_receipt_count,
                duplicate_risk_level=duplicate_risk_level,
            ),
            "checklist": _im_acceptance_checklist_payload(),
        }
    )
    return result


def _im_acceptance_events(
    service: object,
    *,
    target_event_types: set[str],
    target_webhook_names: Sequence[str],
    limit: int,
) -> list[object]:
    if not hasattr(service, "list_events"):
        return []
    raw_events = list(service.list_events(limit=max(int(limit), 0)))  # type: ignore[attr-defined]
    webhook_filter = {str(item).strip() for item in target_webhook_names if str(item).strip()}
    events: list[object] = []
    for item in raw_events:
        if target_event_types and str(getattr(item, "event_type", "") or "") not in target_event_types:
            continue
        if not webhook_filter:
            events.append(item)
            continue
        receipts = list(getattr(item, "consumer_receipts", ()) or ())
        if any(str(getattr(receipt, "webhook_name", "") or "") in webhook_filter for receipt in receipts):
            events.append(item)
            continue
        if str(getattr(item, "delivery_status", "") or "pending") in {"pending", "retry_pending", "failed", "dead_letter"}:
            events.append(item)
    return events


def _im_acceptance_status_payload(
    *,
    events: Sequence[object],
    delivered_count: int,
    retry_pending_count: int,
    dead_letter_count: int,
    consumer_receipt_count: int,
    duplicate_risk_level: str,
) -> dict[str, object]:
    window = _im_acceptance_window_payload(events)
    base_reasons = _im_acceptance_blocking_reasons(
        delivered_count=delivered_count,
        retry_pending_count=retry_pending_count,
        dead_letter_count=dead_letter_count,
        consumer_receipt_count=consumer_receipt_count,
        duplicate_risk_level=duplicate_risk_level,
        window_seconds=int(window["window_seconds"]),
    )
    return {
        "contract_version": "asl.im_feishu_acceptance_status.v1",
        "window": window,
        "two_hour": _im_acceptance_stage_payload(
            target_seconds=2 * 60 * 60,
            base_blocking_reasons=base_reasons,
            window_seconds=int(window["window_seconds"]),
        ),
        "twenty_four_hour": _im_acceptance_stage_payload(
            target_seconds=24 * 60 * 60,
            base_blocking_reasons=base_reasons,
            window_seconds=int(window["window_seconds"]),
        ),
        "manual_noise_review_required": True,
        "notes": (
            "机器状态只判断 delivery/receipt/dead-letter/retry/窗口时长；"
            "真实飞书群噪声、重复刷屏和人工抽检结论仍必须写入验收记录。"
        ),
    }


def _im_acceptance_window_payload(events: Sequence[object]) -> dict[str, object]:
    timestamps: list[datetime] = []
    for event in events:
        event_timestamps: list[datetime] = []
        for value in (getattr(event, "delivered_at", None), getattr(event, "last_attempt_at", None)):
            if isinstance(value, datetime):
                event_timestamps.append(value)
        for receipt in list(getattr(event, "consumer_receipts", ()) or ()):
            received_at = getattr(receipt, "received_at", None)
            if isinstance(received_at, datetime):
                event_timestamps.append(received_at)
        if event_timestamps and str(getattr(event, "delivery_status", "") or "") == "delivered":
            created_at = getattr(event, "created_at", None)
            if isinstance(created_at, datetime):
                event_timestamps.append(created_at)
        timestamps.extend(event_timestamps)
    if not timestamps:
        return {"start_at": None, "end_at": None, "window_seconds": 0, "evidence_event_count": len(events)}
    start_at = min(timestamps)
    end_at = max(timestamps)
    return {
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "window_seconds": max(int((end_at - start_at).total_seconds()), 0),
        "evidence_event_count": len(events),
    }


def _im_acceptance_blocking_reasons(
    *,
    delivered_count: int,
    retry_pending_count: int,
    dead_letter_count: int,
    consumer_receipt_count: int,
    duplicate_risk_level: str,
    window_seconds: int,
) -> list[str]:
    reasons: list[str] = []
    if delivered_count <= 0:
        reasons.append("缺少真实 delivered 事件。")
    if consumer_receipt_count < delivered_count:
        reasons.append("consumer_receipt 数量少于 delivered 事件，无法证明下游真实确认。")
    if dead_letter_count > 0:
        reasons.append("存在 dead-letter，必须先完成失败分级和 replay 风险评估。")
    if retry_pending_count > 0:
        reasons.append("存在 retry_pending，必须先解释或消除重试积压。")
    if duplicate_risk_level not in {"low", "none"}:
        reasons.append("重复投递风险不是 low，需要人工核对飞书侧消息。")
    if window_seconds <= 0:
        reasons.append("缺少可计算的真实投递时间窗口。")
    return reasons


def _im_acceptance_stage_payload(
    *,
    target_seconds: int,
    base_blocking_reasons: Sequence[str],
    window_seconds: int,
) -> dict[str, object]:
    reasons = list(base_blocking_reasons)
    if window_seconds < target_seconds:
        reasons.append(f"真实投递窗口不足 {target_seconds} 秒。")
    return {
        "target_seconds": target_seconds,
        "window_seconds": window_seconds,
        "remaining_seconds": max(target_seconds - window_seconds, 0),
        "machine_status": "ready_for_manual_noise_review" if not reasons else "not_ready",
        "blocking_reasons": reasons,
    }


def _im_acceptance_event_types(service: object, channel: str) -> set[str]:
    event_types: set[str] = set()
    if channel in {"all", "im", "im_notify"}:
        event_types.update(str(item) for item in getattr(service, "im_notification_event_types", lambda: ())() or ())
    if channel in {"all", "im", "feishu_bot"}:
        event_types.update(str(item) for item in getattr(service, "feishu_bot_event_types", lambda: ())() or ())
    return {item for item in event_types if item.strip()}


def _deduplicated_count_from_delivery_result(result: Mapping[str, object]) -> int:
    total = int(result.get("deduplicated_count", 0) or 0)
    aggregate = result.get("aggregate")
    if isinstance(aggregate, Mapping):
        total += int(aggregate.get("deduplicated_count", 0) or 0)
    for key in ("delivery_rounds", "rounds"):
        for item in list(result.get(key, []) or []):
            if isinstance(item, Mapping):
                total += int(item.get("deduplicated_count", 0) or 0)
    return total


def _noise_check_payload() -> dict[str, object]:
    return {
        "placeholder": True,
        "unexpected_group_message_count": None,
        "non_acceptance_event_count": None,
        "manual_spot_check_required": True,
        "notes": "真实 2h/24h 联调后填写飞书群噪声、非验收事件和人工抽检结果。",
    }


def _im_acceptance_checklist_payload() -> dict[str, object]:
    return {
        "two_hour": [
            {"item": "Feishu webhook 已注册且 secret/key 记录在值班交接中", "status": "manual"},
            {"item": "worker 连续运行 2h，无 dead-letter，retry_pending 可解释", "status": "manual"},
            {"item": "consumer_receipt 与飞书侧消息抽检一致", "status": "manual"},
            {"item": "重复风险为 low 或已记录豁免", "status": "manual"},
            {"item": "噪声检查字段已补充真实群观察结果", "status": "manual"},
        ],
        "twenty_four_hour": [
            {"item": "worker 连续运行 24h，heartbeat/last_success_at 正常", "status": "manual"},
            {"item": "总事件、成功、失败、重试、dead-letter 趋势已截图留档", "status": "manual"},
            {"item": "dead-letter 为 0；如不为 0，已完成 replay 风险评估", "status": "manual"},
            {"item": "飞书群无非预期刷屏或重复通知", "status": "manual"},
            {"item": "验收结论、风险和后续 owner 已写入交接记录", "status": "manual"},
        ],
    }
