from __future__ import annotations

import base64
import calendar
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from stability.domain import IntegrationOutboxEvent, WebhookSubscription


class PayloadBuilderMixin:
    @staticmethod
    def _delivery_body(event: IntegrationOutboxEvent) -> bytes:
        payload = {
            "event_id": event.event_id,
            "idempotency_key": event.idempotency_key,
            "event_type": event.event_type,
            "target_type": event.target_type,
            "target_id": event.target_id,
            "created_at": event.created_at.isoformat(),
            "created_by": event.created_by,
            "session_source": event.session_source,
            "audit_source": dict(event.audit_source),
            "payload": dict(event.payload),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")

    def _delivery_body_for_webhook(
        self,
        event: IntegrationOutboxEvent,
        *,
        webhook: WebhookSubscription,
        current_time: datetime | None = None,
    ) -> bytes:
        delivery_channel = str(getattr(webhook, "delivery_channel", "") or "").strip()
        if delivery_channel == "feishu_bot":
            payload = self._feishu_bot_payload(event, webhook=webhook, current_time=current_time)
            return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if delivery_channel == "im_notify":
            payload = self._im_notification_payload(event, webhook=webhook)
            return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if delivery_channel == "defect_sync":
            payload = self._defect_sync_payload(event, webhook=webhook)
            return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if delivery_channel == "release_submission":
            payload = self._release_submission_payload(event, webhook=webhook)
            return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return self._delivery_body(event)

    def _defect_sync_payload(
        self,
        event: IntegrationOutboxEvent,
        *,
        webhook: WebhookSubscription,
    ) -> dict[str, Any]:
        original_payload = dict(event.payload or {})
        return {
            "contract_version": "asl.defect_sync.v1",
            "delivery_channel": "defect_sync",
            "action": self._defect_sync_action(event.event_type),
            "issue": {
                "fingerprint": event.target_id,
                "event_type": event.event_type,
                "created_by": event.created_by,
                "created_at": event.created_at.isoformat(),
                "session_source": event.session_source,
            },
            "defect": {
                "system_key": str(original_payload.get("system_key", "") or ""),
                "link_id": str(original_payload.get("link_id", "") or ""),
                "defect_id": str(original_payload.get("defect_id", "") or ""),
                "title": str(original_payload.get("title", "") or ""),
                "url": str(original_payload.get("url", "") or ""),
                "status": str(original_payload.get("status", "") or ""),
                "acceptable_for_close": bool(original_payload.get("acceptable_for_close", False)),
            },
            "routing": {
                "webhook_name": webhook.name,
                "idempotency_key": event.idempotency_key,
            },
            "original_payload": original_payload,
        }

    @staticmethod
    def _defect_sync_action(event_type: str) -> str:
        normalized = str(event_type or "")
        if normalized == "issue.defect_create_requested":
            return "create_defect"
        if normalized == "issue.defect_linked":
            return "link_defect"
        if normalized == "issue.defect_status_synced":
            return "sync_defect_status"
        if normalized == "outbox.retry_alert":
            return "delivery_alert"
        return "sync_defect"

    def _release_submission_payload(
        self,
        event: IntegrationOutboxEvent,
        *,
        webhook: WebhookSubscription,
    ) -> dict[str, Any]:
        original_payload = dict(event.payload or {})
        return {
            "contract_version": "asl.release_submission.v1",
            "delivery_channel": "release_submission",
            "action": self._release_submission_action(event.event_type),
            "submission": {
                "submission_id": str(original_payload.get("submission_id", "") or event.target_id),
                "source_platform": str(original_payload.get("source_platform", "") or ""),
                "source_request_id": str(original_payload.get("source_request_id", "") or ""),
                "submission_title": str(original_payload.get("submission_title", "") or ""),
                "submission_status": str(original_payload.get("submission_status", "") or ""),
                "package_name": str(original_payload.get("package_name", "") or ""),
                "version_name": str(original_payload.get("version_name", "") or ""),
                "version_code": str(original_payload.get("version_code", "") or ""),
                "build_id": str(original_payload.get("build_id", "") or ""),
                "release_channel": str(original_payload.get("release_channel", "") or ""),
                "owner_team": str(original_payload.get("owner_team", "") or ""),
            },
            "task": {
                "task_id": str(original_payload.get("task_id", "") or ""),
                "task_name": str(original_payload.get("task_name", "") or ""),
                "template_type": str(original_payload.get("template_type", "") or ""),
                "selected_device_ids": list(original_payload.get("selected_device_ids", []) or []),
            },
            "run": {
                "run_id": str(original_payload.get("run_id", "") or ""),
                "run_status": str(original_payload.get("run_status", "") or ""),
                "report_paths": dict(original_payload.get("report_paths", {}) or {}),
            },
            "admission": {
                "baseline_key": str(original_payload.get("baseline_key", "") or ""),
                "admission_case_id": str(original_payload.get("admission_case_id", "") or ""),
                "status": str(original_payload.get("admission_status", "") or ""),
                "final_decision": str(original_payload.get("admission_final_decision", "") or ""),
                "error_code": str(original_payload.get("admission_error_code", "") or ""),
            },
            "routing": {
                "webhook_name": webhook.name,
                "idempotency_key": event.idempotency_key,
            },
            "original_payload": original_payload,
        }

    @staticmethod
    def _release_submission_action(event_type: str) -> str:
        normalized = str(event_type or "")
        if normalized == "release_submission.created":
            return "create_submission"
        if normalized == "release_submission.execution_updated":
            return "sync_execution_status"
        if normalized == "release_submission.admission_synced":
            return "sync_admission_result"
        if normalized == "outbox.retry_alert":
            return "delivery_alert"
        return "sync_submission"

    def _im_notification_payload(
        self,
        event: IntegrationOutboxEvent,
        *,
        webhook: WebhookSubscription,
    ) -> dict[str, Any]:
        original_payload = dict(event.payload or {})
        title = self._im_notification_title(event, payload=original_payload)
        summary = self._im_notification_summary(event, payload=original_payload)
        message = self._im_notification_message(event, payload=original_payload, webhook=webhook)
        return {
            "contract_version": "asl.im_notify.v1",
            "delivery_channel": "im_notify",
            "message_type": "markdown",
            "title": title,
            "summary": summary,
            "message": message,
            "event": {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "created_at": event.created_at.isoformat(),
                "created_by": event.created_by,
                "session_source": event.session_source,
                "idempotency_key": event.idempotency_key,
                "delivery_status": event.delivery_status,
            },
            "original_payload": original_payload,
        }

    def _feishu_bot_payload(
        self,
        event: IntegrationOutboxEvent,
        *,
        webhook: WebhookSubscription,
        current_time: datetime | None = None,
    ) -> dict[str, Any]:
        im_payload = self._im_notification_payload(event, webhook=webhook)
        timestamp = str(self._feishu_timestamp(current_time or event.created_at))
        text = "\n".join(
            item
            for item in (
                str(im_payload.get("title", "") or ""),
                str(im_payload.get("summary", "") or ""),
                str(im_payload.get("message", "") or ""),
                f"event_id: {event.event_id}",
                f"idempotency_key: {event.idempotency_key}",
            )
            if item
        )
        return {
            "timestamp": timestamp,
            "sign": self._feishu_bot_sign(timestamp, str(getattr(webhook, "signing_secret", "") or "")),
            "msg_type": "text",
            "content": {
                "text": text,
            },
        }

    @staticmethod
    def _feishu_timestamp(value: datetime) -> int:
        if value.tzinfo is None:
            return calendar.timegm(value.utctimetuple())
        return int(value.astimezone(timezone.utc).timestamp())

    @staticmethod
    def _feishu_bot_sign(timestamp: str, signing_secret: str) -> str:
        string_to_sign = f"{timestamp}\n{signing_secret}"
        digest = hmac.new(
            string_to_sign.encode("utf-8"),
            b"",
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    @staticmethod
    def _im_notification_title(
        event: IntegrationOutboxEvent,
        *,
        payload: Mapping[str, Any],
    ) -> str:
        event_type = str(event.event_type or "")
        target = f"{event.target_type}:{event.target_id}"
        if event_type == "admission_case.updated":
            decision = str(payload.get("final_decision", "") or "unknown")
            return f"准入单更新: {target} / {decision}"
        if event_type == "admission.override_recorded":
            decision = str(payload.get("final_decision", "") or "unknown")
            return f"准入人工覆盖: {target} / {decision}"
        if event_type.endswith(".assigned"):
            assignee_id = str(payload.get("assignee_id", "") or "unassigned")
            return f"已认领: {target} -> {assignee_id}"
        if event_type.endswith(".transitioned"):
            target_state = str(payload.get("to_state", "") or "unknown")
            return f"状态更新: {target} -> {target_state}"
        if event_type.endswith(".commented"):
            return f"新增评论: {target}"
        if event_type == "outbox.retry_alert":
            return f"投递告警: {target}"
        return f"平台通知: {event_type}"

    @staticmethod
    def _im_notification_summary(
        event: IntegrationOutboxEvent,
        *,
        payload: Mapping[str, Any],
    ) -> str:
        event_type = str(event.event_type or "")
        if event_type == "admission_case.updated":
            decision = str(payload.get("final_decision", "") or "")
            status = str(payload.get("status", "") or "")
            parts = [item for item in (decision, status) if item]
            return " / ".join(parts) or "准入结论已更新"
        if event_type == "admission.override_recorded":
            reason = str(payload.get("reason", "") or "")
            return reason or "人工覆盖已记录"
        if event_type.endswith(".assigned"):
            assignee_id = str(payload.get("assignee_id", "") or "")
            return f"负责人: {assignee_id}" if assignee_id else "认领关系已更新"
        if event_type.endswith(".transitioned"):
            from_state = str(payload.get("from_state", "") or "")
            to_state = str(payload.get("to_state", "") or "")
            if from_state or to_state:
                return f"{from_state or 'unknown'} -> {to_state or 'unknown'}"
        if event_type.endswith(".commented"):
            comment_id = str(payload.get("comment_id", "") or "")
            return f"comment_id={comment_id}" if comment_id else "新增评论"
        if event_type == "outbox.retry_alert":
            return str(payload.get("last_error", "") or "Outbox delivery requires operator attention.")
        return f"{event.target_type}:{event.target_id}"

    @staticmethod
    def _im_notification_message(
        event: IntegrationOutboxEvent,
        *,
        payload: Mapping[str, Any],
        webhook: WebhookSubscription,
    ) -> str:
        lines = [
            f"# {PayloadBuilderMixin._im_notification_title(event, payload=payload)}",
            "",
            f"- 事件类型: `{event.event_type}`",
            f"- 目标对象: `{event.target_type}:{event.target_id}`",
            f"- 触发人: `{event.created_by or 'system'}`",
            f"- 触发时间: `{event.created_at.isoformat()}`",
            f"- Webhook: `{webhook.name}`",
        ]
        summary = PayloadBuilderMixin._im_notification_summary(event, payload=payload)
        if summary:
            lines.append(f"- 摘要: {summary}")
        detail_lines = PayloadBuilderMixin._im_payload_detail_lines(event, payload=payload)
        if detail_lines:
            lines.extend(["", "## 关键字段", *detail_lines])
        return "\n".join(lines)

    @staticmethod
    def _im_payload_detail_lines(
        event: IntegrationOutboxEvent,
        *,
        payload: Mapping[str, Any],
    ) -> list[str]:
        event_type = str(event.event_type or "")
        if event_type in {"admission_case.updated", "admission.override_recorded"}:
            keys = (
                "final_decision",
                "status",
                "error_code",
                "assignee",
                "final_reviewer",
                "reason",
                "comment",
            )
            return [
                f"- `{key}`: `{str(payload.get(key, '') or '')}`"
                for key in keys
                if str(payload.get(key, "") or "").strip()
            ]
        if event_type.endswith(".assigned"):
            return [
                f"- `assignee_id`: `{str(payload.get('assignee_id', '') or '')}`"
            ] if str(payload.get("assignee_id", "") or "").strip() else []
        if event_type.endswith(".transitioned"):
            details: list[str] = []
            if str(payload.get("from_state", "") or "").strip() or str(payload.get("to_state", "") or "").strip():
                details.append(
                    f"- `workflow_state`: `{str(payload.get('from_state', '') or 'unknown')} -> {str(payload.get('to_state', '') or 'unknown')}`"
                )
            if str(payload.get("reason", "") or "").strip():
                details.append(f"- `reason`: `{str(payload.get('reason', '') or '')}`")
            return details
        if event_type.endswith(".commented"):
            return [
                f"- `comment_id`: `{str(payload.get('comment_id', '') or '')}`"
            ] if str(payload.get("comment_id", "") or "").strip() else []
        if event_type == "outbox.retry_alert":
            details: list[str] = []
            for key in ("delivery_status", "attempt_count", "last_response_code", "next_retry_at", "last_error"):
                value = payload.get(key, "")
                if value in ("", None):
                    continue
                details.append(f"- `{key}`: `{value}`")
            return details
        return []
