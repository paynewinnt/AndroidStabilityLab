from __future__ import annotations

from typing import Any, Mapping, Sequence


class IntegrationAcceptancePayloadMixin:
    def _integration_im_acceptance_payload(
        self,
        service: object | None,
        *,
        events: Sequence[Mapping[str, Any]],
        webhooks: Sequence[object],
    ) -> dict[str, Any]:
        im_event_types = set()
        feishu_event_types = set()
        if service is not None:
            im_event_types.update(str(item) for item in getattr(service, "im_notification_event_types", lambda: ())() or ())
            feishu_event_types.update(str(item) for item in getattr(service, "feishu_bot_event_types", lambda: ())() or ())
        target_event_types = {item for item in im_event_types | feishu_event_types if item.strip()}
        scoped_events = [
            dict(item)
            for item in events
            if not target_event_types or str(dict(item).get("event_type", "") or "") in target_event_types
        ]
        status_counts: dict[str, int] = {}
        retry_count = 0
        dead_letter_count = 0
        delivered_count = 0
        failed_count = 0
        consumer_receipt_count = 0
        idempotency_seen: set[tuple[str, str]] = set()
        duplicate_candidate_count = 0
        for item in scoped_events:
            status = str(item.get("delivery_status", "") or "pending")
            status_counts[status] = status_counts.get(status, 0) + 1
            attempts = int(item.get("attempt_count", 0) or 0)
            retry_count += max(attempts - 1, 0)
            if status == "delivered":
                delivered_count += 1
            if status in {"failed", "retry_pending", "dead_letter"}:
                failed_count += 1
            if status == "dead_letter":
                dead_letter_count += 1
            receipts = [dict(receipt) for receipt in list(item.get("consumer_receipts", []) or []) if isinstance(receipt, Mapping)]
            consumer_receipt_count += len(receipts)
            for receipt in receipts:
                key = (str(receipt.get("webhook_name", "") or ""), str(receipt.get("idempotency_key", "") or ""))
                if key[1] and key in idempotency_seen:
                    duplicate_candidate_count += 1
                if key[1]:
                    idempotency_seen.add(key)

        worker_status = {}
        if service is not None and callable(getattr(service, "get_worker_status", None)):
            try:
                worker_status = self._integration_worker_status_payload(service.get_worker_status())
            except Exception:
                worker_status = {}
        last_run_summary = dict(worker_status.get("last_run_summary", {}) or {})
        deduplicated_count = int(last_run_summary.get("deduplicated_count", 0) or 0)
        aggregate = last_run_summary.get("aggregate")
        if isinstance(aggregate, Mapping):
            deduplicated_count += int(aggregate.get("deduplicated_count", 0) or 0)
        for key in ("delivery_rounds", "rounds"):
            for round_item in list(last_run_summary.get(key, []) or []):
                if isinstance(round_item, Mapping):
                    deduplicated_count += int(round_item.get("deduplicated_count", 0) or 0)

        duplicate_risk_level = "low"
        duplicate_risk_reasons = []
        if deduplicated_count > 0 or duplicate_candidate_count > 0:
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

        target_webhooks = [
            item
            for item in webhooks
            if str(getattr(item, "delivery_channel", "") or "") in {"im_notify", "feishu_bot"}
        ]
        return {
            "contract_version": "asl.im_feishu_acceptance_summary.v1",
            "webhook_names": [str(getattr(item, "name", "") or "") for item in target_webhooks],
            "event_types": sorted(target_event_types),
            "total_event_count": len(scoped_events),
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
                "duplicate_candidate_count": duplicate_candidate_count,
                "reasons": duplicate_risk_reasons,
            },
            "noise_check": {
                "placeholder": True,
                "unexpected_group_message_count": None,
                "non_acceptance_event_count": None,
                "manual_spot_check_required": True,
                "notes": "真实 2h/24h 联调后填写飞书群噪声、非验收事件和人工抽检结果。",
            },
            "checklist": {
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
            },
        }


__all__ = ["IntegrationAcceptancePayloadMixin"]
