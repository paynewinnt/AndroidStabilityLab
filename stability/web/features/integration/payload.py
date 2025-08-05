from __future__ import annotations

from ...application_common import *
from ...application_payload_integration_acceptance import ApplicationPayloadIntegrationAcceptanceMixin
from stability.time_utils import now_beijing_string


def _generated_at_now() -> str:
    return now_beijing_string()


class IntegrationPayloadMixin(ApplicationPayloadIntegrationAcceptanceMixin):
    def _integration_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "integration_outbox_service", None)
        if service is None:
            return {
                "page": "integration_outbox",
                "title": "Integration Outbox",
                "generated_at": _generated_at_now(),
                "current_actor": dict(request_context or {}).get("current_actor", {}),
                "summary": {"event_count": 0, "webhook_count": 0},
                "worker": self._integration_worker_payload(None),
                "im_acceptance": self._integration_im_acceptance_payload(None, events=[], webhooks=[]),
                "delivery_receipts": [],
                "consumer_receipts": [],
                "replay_receipts": [],
                "operator_receipts": [],
                "idempotency_contract": self._integration_idempotency_contract_payload(),
                "callback_contract": self._integration_callback_contract_payload(),
                "events": [],
                "webhooks": [],
            }
        limit = self._int_query(query, "limit", default=20)
        events = list(service.list_events(limit=limit)) if hasattr(service, "list_events") else []
        webhooks = list(service.list_webhooks()) if hasattr(service, "list_webhooks") else []
        delivery_status_counts: dict[str, int] = {}
        delivery_channel_counts: dict[str, int] = {}
        dead_letter_count = 0
        retry_pending_count = 0
        delivered_count = 0
        alerting_count = 0
        im_webhook_count = 0
        ci_webhook_count = 0
        defect_webhook_count = 0
        release_webhook_count = 0
        feishu_webhook_count = 0
        for item in events:
            status_key = str(getattr(item, "delivery_status", "") or "pending")
            delivery_status_counts[status_key] = delivery_status_counts.get(status_key, 0) + 1
            if status_key == "dead_letter":
                dead_letter_count += 1
            if status_key == "retry_pending":
                retry_pending_count += 1
            if status_key == "delivered":
                delivered_count += 1
            if str(getattr(item, "alert_status", "") or "") not in {"", "none", "self"}:
                alerting_count += 1
        for item in webhooks:
            channel = str(getattr(item, "delivery_channel", "") or "generic")
            delivery_channel_counts[channel] = delivery_channel_counts.get(channel, 0) + 1
            if channel == "im_notify":
                im_webhook_count += 1
            if channel == "feishu_bot":
                feishu_webhook_count += 1
            if channel == "ci_callback":
                ci_webhook_count += 1
            if channel == "defect_sync":
                defect_webhook_count += 1
            if channel == "release_submission":
                release_webhook_count += 1
        event_payloads = [self._integration_event_payload(item) for item in events]
        consumer_receipts = [
            dict(item)
            for event_payload in event_payloads
            for item in event_payload.get("consumer_receipts", [])
            if isinstance(item, dict)
        ]
        replay_receipts = [
            dict(item)
            for event_payload in event_payloads
            for item in event_payload.get("replay_receipts", [])
            if isinstance(item, dict)
        ]
        operator_receipts = [
            dict(item)
            for event_payload in event_payloads
            for item in event_payload.get("operator_receipts", [])
            if isinstance(item, dict)
        ]
        delivery_receipts = [
            dict(item["delivery_receipt"])
            for item in event_payloads
            if isinstance(item.get("delivery_receipt"), dict)
        ]
        return {
            "page": "integration_outbox",
            "title": "Integration Outbox",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "summary": {
                "event_count": len(events),
                "webhook_count": len(webhooks),
                "delivery_status_counts": delivery_status_counts,
                "delivery_channel_counts": delivery_channel_counts,
                "dead_letter_count": dead_letter_count,
                "retry_pending_count": retry_pending_count,
                "delivered_count": delivered_count,
                "alerting_event_count": alerting_count,
                "im_webhook_count": im_webhook_count,
                "feishu_webhook_count": feishu_webhook_count,
                "ci_webhook_count": ci_webhook_count,
                "defect_webhook_count": defect_webhook_count,
                "release_webhook_count": release_webhook_count,
                "consumer_receipt_count": len(consumer_receipts),
                "replay_receipt_count": len(replay_receipts),
                "operator_receipt_count": len(operator_receipts),
            },
            "worker": self._integration_worker_payload(service, webhooks=webhooks),
            "im_acceptance": self._integration_im_acceptance_payload(service, events=event_payloads, webhooks=webhooks),
            "consumer_receipts": consumer_receipts,
            "replay_receipts": replay_receipts,
            "operator_receipts": operator_receipts,
            "delivery_receipts": delivery_receipts,
            "idempotency_contract": self._integration_idempotency_contract_payload(),
            "callback_contract": self._integration_callback_contract_payload(),
            "events": event_payloads,
            "webhooks": [self._integration_webhook_payload(item) for item in webhooks],
        }

    def _release_submissions_payload(
        self,
        query: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "release_submission_service", None)
        if service is None or not hasattr(service, "list_submissions"):
            raise ValueError("Release submission service is unavailable.")
        limit = self._int_query(query, "limit", default=20)
        records = list(service.list_submissions(limit=limit))
        payloads = [self._release_submission_payload(record) for record in records]
        status_counts: dict[str, int] = {}
        run_status_counts: dict[str, int] = {}
        decision_counts: dict[str, int] = {}
        executed_count = 0
        admission_synced_count = 0
        for item in payloads:
            submission_status = str(item.get("submission_status", "") or "received")
            status_counts[submission_status] = status_counts.get(submission_status, 0) + 1
            run_status = str(item.get("run_status", "") or "")
            if run_status:
                run_status_counts[run_status] = run_status_counts.get(run_status, 0) + 1
            decision = str(item.get("admission_final_decision", "") or "")
            if decision:
                decision_counts[decision] = decision_counts.get(decision, 0) + 1
            if bool(item.get("execute_immediately", False)):
                executed_count += 1
            if submission_status == "admission_synced":
                admission_synced_count += 1
        return {
            "page": "release_submissions",
            "title": "提测请求",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "summary": {
                "submission_count": len(payloads),
                "submission_status_counts": status_counts,
                "run_status_counts": run_status_counts,
                "admission_decision_counts": decision_counts,
                "executed_count": executed_count,
                "admission_synced_count": admission_synced_count,
            },
            "release_submissions": payloads,
        }

    def _release_submission_detail_payload(
        self,
        submission_id: str,
        *,
        query: dict[str, list[str]] | None = None,
        request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        del query
        service = getattr(self._bundle, "release_submission_service", None)
        if service is None or not hasattr(service, "get_submission"):
            raise ValueError("Release submission service is unavailable.")
        record = service.get_submission(submission_id.strip())
        return {
            "page": "release_submission_detail",
            "title": f"提测请求 · {submission_id.strip()}",
            "generated_at": _generated_at_now(),
            "current_actor": dict(request_context or {}).get("current_actor", {}),
            "release_submission": self._release_submission_payload(record),
        }

    def _integration_worker_payload(self, service: object | None, *, webhooks: Sequence[object] = ()) -> dict[str, Any]:
        worker_status: dict[str, Any] = {}
        if service is not None:
            worker_status_getter = getattr(service, "get_worker_status", None)
            if callable(worker_status_getter):
                try:
                    worker_status = self._integration_worker_status_payload(worker_status_getter())
                except Exception:
                    worker_status = {}
        return {
            "mode": "local_ops_worker_surface",
            "supports_run_delivery_worker": callable(getattr(service, "run_delivery_worker", None)),
            "supports_run_delivery_daemon": callable(getattr(service, "run_delivery_daemon", None)),
            "supports_run_im_notification_worker": callable(getattr(service, "run_im_notification_worker", None)),
            "supports_run_feishu_notify_worker": callable(getattr(service, "run_feishu_notify_worker", None)),
            "supports_run_defect_sync_worker": callable(getattr(service, "run_defect_sync_worker", None)),
            "supports_run_release_sync_worker": callable(getattr(service, "run_release_sync_worker", None)),
            "supports_replay_dead_letter_api": callable(getattr(service, "replay_dead_lettered_events", None)),
            "supports_delivery_receipts": True,
            "supports_consumer_receipts": True,
            "supports_operator_receipts": True,
            "supports_replay_receipts": True,
            "worker_status": worker_status,
            "delivery_interval_seconds": getattr(service, "_delivery_interval", None) if service is not None else None,
            "retry_delay_seconds": getattr(service, "_retry_delay", None) if service is not None else None,
            "max_retry_delay_seconds": getattr(service, "_max_retry_delay", None) if service is not None else None,
            "dead_letter_threshold": getattr(service, "_dead_letter_threshold", None) if service is not None else None,
            "retry_alert_threshold": getattr(service, "_retry_alert_threshold", None) if service is not None else None,
            "registered_webhook_names": [
                str(getattr(item, "name", "") or "")
                for item in webhooks
                if str(getattr(item, "name", "") or "")
            ],
            "commands": {
                "deliver_single_round": "python -m stability.cli deliver-integration-outbox --webhook-name <name>",
                "run_worker_loop": "python -m stability.cli run-integration-outbox-worker --webhook-name <name>",
                "run_daemon_loop": "python -m stability.cli run-integration-outbox-worker --daemon --webhook-name <name>",
                "run_ci_callback_daemon": "python -m stability.cli run-ci-admission-sync-worker --webhook-name <name>",
                "register_im_webhook": "python -m stability.cli register-im-webhook --name <name> --url <https-url>",
                "run_im_notification_daemon": "python -m stability.cli run-im-notify-worker --daemon --webhook-name <name>",
                "register_feishu_webhook": "python -m stability.cli register-feishu-webhook --name <name> --url <https-url>",
                "run_feishu_notify_daemon": "python -m stability.cli run-feishu-notify-worker --daemon --webhook-name <name>",
                "show_im_acceptance_summary": "python -m stability.cli show-im-acceptance-summary --channel feishu_bot --webhook-name <name>",
                "register_defect_webhook": "python -m stability.cli register-defect-webhook --name <name> --url <https-url>",
                "run_defect_sync_daemon": "python -m stability.cli run-defect-sync-worker --daemon --webhook-name <name>",
                "register_release_webhook": "python -m stability.cli register-release-webhook --name <name> --url <https-url>",
                "run_release_sync_daemon": "python -m stability.cli run-release-sync-worker --daemon --webhook-name <name>",
                "replay_dead_letters": "python -m stability.cli replay-integration-dead-letters --execute",
            },
            "receipt_contract": "webhook_transport_ack_only_plus_operator_receipts",
        }

    def _integration_idempotency_contract_payload(self) -> dict[str, Any]:
        return {
            "strategy": "event_id_per_delivery_target",
            "idempotency_key_template": "asl.outbox.idempotency.v1:<event_id>",
            "receipt_key_template": "asl.outbox.receipt.v1:<event_id>",
            "consumer_receipt_mode": "transport_and_consumer",
            "receipt_modes": ["transport", "consumer"],
            "notes": "Current webhook chain confirms transport-level delivery, persists consumer receipts when downstream responds, and records operator/replay receipts for local ops actions.",
        }

    def _integration_callback_contract_payload(self) -> dict[str, Any]:
        return {
            "contract_version": "asl.webhook_callback.v1",
            "delivery_contract_header": "X-ASL-Delivery-Contract: asl.webhook_delivery.v1",
            "signature_headers": [
                "X-ASL-Signature",
                "X-ASL-Signature-Alg",
                "X-ASL-Signature-Key-Id",
            ],
            "routing_headers": [
                "X-ASL-Event-Id",
                "X-ASL-Event-Type",
                "X-ASL-Target-Type",
                "X-ASL-Target-Id",
                "X-ASL-Webhook-Name",
                "X-ASL-Failure-Policy",
                "X-ASL-Idempotency-Key",
            ],
            "receiver_ack_fields": [
                "receipt_id",
                "consumer_receipt_id",
                "consumer_id",
                "signature_verified",
            ],
            "security_rules": [
                "non-local webhook 必须使用 https",
                "non-local webhook 必须配置 signing_secret",
                "signature_key_id 必须稳定可追溯，轮转时 accepted_signature_key_ids 需保留旧值",
            ],
            "delivery_channels": {
                "generic": "通用 JSON webhook，适合自定义接收端。",
                "ci_callback": "CI 准入回写链路，当前以 admission_case.updated 为主。",
                "im_notify": "IM 通知链路，消息体使用 asl.im_notify.v1。",
                "feishu_bot": "飞书自定义机器人链路，消息体使用 feishu.custom_bot.v1。",
                "defect_sync": "缺陷系统同步链路，消息体使用 asl.defect_sync.v1。",
                "release_submission": "提测平台回写链路，消息体使用 asl.release_submission.v1。",
            },
            "channel_contracts": {
                "im_notify": {
                    "contract_version": "asl.im_notify.v1",
                    "message_fields": ["title", "summary", "message", "event", "original_payload"],
                },
                "feishu_bot": {
                    "contract_version": "feishu.custom_bot.v1",
                    "message_fields": ["timestamp", "sign", "msg_type", "content"],
                },
                "defect_sync": {
                    "contract_version": "asl.defect_sync.v1",
                    "message_fields": ["action", "issue", "defect", "routing", "original_payload"],
                },
                "release_submission": {
                    "contract_version": "asl.release_submission.v1",
                    "message_fields": ["action", "release_submission", "routing", "original_payload"],
                },
            },
        }

    @staticmethod
    def _integration_webhook_security_boundary(url: str) -> str:
        return "local_callback" if not IntegrationPayloadMixin._integration_webhook_requires_tls(url) else "shared_remote_callback"

    @staticmethod
    def _integration_webhook_requires_tls(url: str) -> bool:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(str(url or "").strip())
            host = str(parsed.hostname or "").strip().lower()
            if host in {"127.0.0.1", "localhost", "::1"}:
                return False
            return True
        except Exception:
            return True

    @staticmethod
    def _integration_webhook_requires_signing_secret(url: str) -> bool:
        return IntegrationPayloadMixin._integration_webhook_requires_tls(url)

    def _integration_event_payload(self, item: object) -> dict[str, Any]:
        event_id = str(getattr(item, "event_id", "") or "")
        delivery_status = str(getattr(item, "delivery_status", "") or "pending")
        receipt_status = "transport_ack" if delivery_status == "delivered" else "not_acknowledged"
        raw_consumer_receipts = getattr(item, "consumer_receipts", ()) or ()
        consumer_receipts = [
            self._integration_consumer_receipt_payload(receipt) for receipt in raw_consumer_receipts if receipt is not None
        ]
        return {
            "event_id": event_id,
            "event_type": str(getattr(item, "event_type", "") or ""),
            "target_type": str(getattr(item, "target_type", "") or ""),
            "target_id": str(getattr(item, "target_id", "") or ""),
            "created_at": self._isoformat_or_none(getattr(item, "created_at", None)),
            "created_by": str(getattr(item, "created_by", "") or ""),
            "session_source": str(getattr(item, "session_source", "") or ""),
            "audit_source": dict(getattr(item, "audit_source", {}) or {}),
            "payload": dict(getattr(item, "payload", {}) or {}),
            "delivery_status": delivery_status,
            "attempt_count": int(getattr(item, "attempt_count", 0) or 0),
            "last_attempt_at": self._isoformat_or_none(getattr(item, "last_attempt_at", None)),
            "delivered_at": self._isoformat_or_none(getattr(item, "delivered_at", None)),
            "last_error": str(getattr(item, "last_error", "") or ""),
            "next_retry_at": self._isoformat_or_none(getattr(item, "next_retry_at", None)),
            "signature": str(getattr(item, "signature", "") or ""),
            "retry_backoff_seconds": int(getattr(item, "retry_backoff_seconds", 0) or 0),
            "last_response_code": getattr(item, "last_response_code", None),
            "dead_lettered_at": self._isoformat_or_none(getattr(item, "dead_lettered_at", None)),
            "failure_category": str(getattr(item, "failure_category", "") or ""),
            "alert_status": str(getattr(item, "alert_status", "") or "none"),
            "alert_count": int(getattr(item, "alert_count", 0) or 0),
            "last_alert_at": self._isoformat_or_none(getattr(item, "last_alert_at", None)),
            "idempotency_key": str(
                getattr(item, "idempotency_key", "")
                or f"asl.outbox.idempotency.v1:{event_id}"
            ),
            "consumer_receipts": consumer_receipts,
            "consumer_receipt_count": len(consumer_receipts),
            "replay_receipts": [
                self._integration_replay_receipt_payload(receipt)
                for receipt in (getattr(item, "replay_receipts", ()) or ())
                if receipt is not None
            ],
            "replay_receipt_count": len(getattr(item, "replay_receipts", ()) or ()),
            "operator_receipts": [
                self._integration_operator_receipt_payload(receipt)
                for receipt in (getattr(item, "operator_receipts", ()) or ())
                if receipt is not None
            ],
            "operator_receipt_count": len(getattr(item, "operator_receipts", ()) or ()),
            "delivery_receipt": {
                "receipt_key": f"asl.outbox.receipt.v1:{event_id}",
                "receipt_status": receipt_status,
                "contract": "webhook_transport_ack_only_plus_operator_receipts",
                "delivered_at": self._isoformat_or_none(getattr(item, "delivered_at", None)),
            },
        }

    def _integration_webhook_payload(self, item: object) -> dict[str, Any]:
        url = str(getattr(item, "url", "") or "")
        return {
            "webhook_id": str(getattr(item, "webhook_id", "") or ""),
            "name": str(getattr(item, "name", "") or ""),
            "url": url,
            "subscribed_event_types": list(getattr(item, "subscribed_event_types", ()) or ()),
            "created_at": self._isoformat_or_none(getattr(item, "created_at", None)),
            "created_by": str(getattr(item, "created_by", "") or ""),
            "secret_hint": str(getattr(item, "secret_hint", "") or ""),
            "signature_key_id": str(getattr(item, "signature_key_id", "") or ""),
            "accepted_signature_key_ids": list(getattr(item, "accepted_signature_key_ids", ()) or ()),
            "failure_policy": str(getattr(item, "failure_policy", "") or ""),
            "delivery_channel": str(getattr(item, "delivery_channel", "") or ""),
            "security_boundary": self._integration_webhook_security_boundary(url),
            "requires_tls": self._integration_webhook_requires_tls(url),
            "requires_signing_secret": self._integration_webhook_requires_signing_secret(url),
        }

    def _integration_worker_status_payload(self, item: object) -> dict[str, Any]:
        return {
            "worker_name": str(getattr(item, "worker_name", "") or ""),
            "status": str(getattr(item, "status", "") or ""),
            "worker_mode": str(getattr(item, "worker_mode", "") or ""),
            "daemon_enabled": bool(getattr(item, "daemon_enabled", False)),
            "daemon_pid": getattr(item, "daemon_pid", None),
            "daemon_heartbeat_at": self._isoformat_or_none(getattr(item, "daemon_heartbeat_at", None)),
            "last_started_at": self._isoformat_or_none(getattr(item, "last_started_at", None)),
            "last_finished_at": self._isoformat_or_none(getattr(item, "last_finished_at", None)),
            "last_success_at": self._isoformat_or_none(getattr(item, "last_success_at", None)),
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

    def _integration_consumer_receipt_payload(self, item: object) -> dict[str, Any]:
        event_id = str(getattr(item, "event_id", "") or "")
        receipt_id = str(getattr(item, "receipt_id", "") or "")
        return {
            "receipt_id": receipt_id,
            "event_id": event_id,
            "webhook_name": str(getattr(item, "webhook_name", "") or ""),
            "idempotency_key": str(getattr(item, "idempotency_key", "") or ""),
            "received_at": self._isoformat_or_none(getattr(item, "received_at", None)),
            "status": str(getattr(item, "status", "") or "delivered"),
            "response_code": getattr(item, "response_code", None),
            "consumer_id": str(getattr(item, "consumer_id", "") or ""),
            "consumer_receipt_id": str(getattr(item, "consumer_receipt_id", "") or ""),
            "response_excerpt": str(getattr(item, "response_excerpt", "") or ""),
            "receipt_key": f"asl.outbox.consumer_receipt.v1:{event_id}:{receipt_id}",
        }

    def _integration_replay_receipt_payload(self, item: object) -> dict[str, Any]:
        event_id = str(getattr(item, "event_id", "") or "")
        receipt_id = str(getattr(item, "receipt_id", "") or "")
        return {
            "receipt_id": receipt_id,
            "event_id": event_id,
            "webhook_name": str(getattr(item, "webhook_name", "") or ""),
            "idempotency_key": str(getattr(item, "idempotency_key", "") or ""),
            "replayed_at": self._isoformat_or_none(getattr(item, "replayed_at", None)),
            "replayed_by": str(getattr(item, "replayed_by", "") or ""),
            "status": str(getattr(item, "status", "") or ""),
            "replay_token": str(getattr(item, "replay_token", "") or ""),
            "notes": str(getattr(item, "notes", "") or ""),
            "receipt_key": f"asl.outbox.replay_receipt.v1:{event_id}:{receipt_id}",
        }

    def _integration_operator_receipt_payload(self, item: object) -> dict[str, Any]:
        event_id = str(getattr(item, "event_id", "") or "")
        receipt_id = str(getattr(item, "receipt_id", "") or "")
        return {
            "receipt_id": receipt_id,
            "event_id": event_id,
            "webhook_name": str(getattr(item, "webhook_name", "") or ""),
            "action": str(getattr(item, "action", "") or ""),
            "operator_id": str(getattr(item, "operator_id", "") or ""),
            "recorded_at": self._isoformat_or_none(getattr(item, "recorded_at", None)),
            "status": str(getattr(item, "status", "") or ""),
            "session_source": str(getattr(item, "session_source", "") or ""),
            "audit_source": dict(getattr(item, "audit_source", {}) or {}),
            "notes": str(getattr(item, "notes", "") or ""),
            "receipt_key": f"asl.outbox.operator_receipt.v1:{event_id}:{receipt_id}",
        }


__all__ = ["IntegrationPayloadMixin"]
