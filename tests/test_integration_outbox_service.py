from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app import IntegrationOutboxService


class IntegrationOutboxServiceTest(unittest.TestCase):
    def test_publish_event_and_register_webhook_are_persisted(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IntegrationOutboxService(root_dir=Path(temp_dir))

            event = service.publish_event(
                event_type="issue.assigned",
                target_type="issue",
                target_id="ifp_1",
                created_by="tester",
                session_source="query:as_actor",
                audit_source={"request_path": "/issues/actions/assign"},
                payload={"assignee_id": "developer"},
            )
            webhook = service.register_webhook(
                name="CI Callback",
                url="https://example.invalid/callback",
                subscribed_event_types=("issue.assigned", "admission.override_recorded"),
                created_by="admin",
                secret_hint="configured",
                signing_secret="secret",
            )

            self.assertEqual(event.event_type, "issue.assigned")
            self.assertEqual(event.session_source, "query:as_actor")
            self.assertEqual(webhook.name, "CI Callback")
            self.assertEqual(webhook.signature_key_id, "v1")
            self.assertEqual(webhook.failure_policy, "retryable_http")
            self.assertEqual(len(service.list_events(limit=10)), 1)
            self.assertEqual(len(service.list_webhooks()), 1)
            self.assertTrue((Path(temp_dir) / "events.json").exists())
            self.assertTrue((Path(temp_dir) / "webhooks.json").exists())

    def test_register_webhook_rejects_non_https_remote_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IntegrationOutboxService(root_dir=Path(temp_dir))

            with self.assertRaises(ValueError) as ctx:
                service.register_webhook(
                    name="Remote HTTP",
                    url="http://example.invalid/callback",
                    subscribed_event_types=("issue.assigned",),
                    created_by="admin",
                    signing_secret="secret",
                )

            self.assertIn("https", str(ctx.exception))

    def test_register_webhook_requires_signing_secret_for_non_local_endpoint(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IntegrationOutboxService(root_dir=Path(temp_dir))

            with self.assertRaises(ValueError) as ctx:
                service.register_webhook(
                    name="Remote HTTPS",
                    url="https://example.invalid/callback",
                    subscribed_event_types=("issue.assigned",),
                    created_by="admin",
                )

            self.assertIn("signing_secret", str(ctx.exception))

    def test_register_webhook_allows_local_http_without_signing_secret(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IntegrationOutboxService(root_dir=Path(temp_dir))

            webhook = service.register_webhook(
                name="Local Callback",
                url="http://127.0.0.1:9010/callback",
                subscribed_event_types=("issue.assigned",),
                created_by="admin",
            )

            self.assertEqual(webhook.url, "http://127.0.0.1:9010/callback")
            self.assertEqual(webhook.signature_key_id, "v1")
            self.assertEqual(tuple(webhook.accepted_signature_key_ids), ("v1",))

    def test_register_im_webhook_uses_stable_channel_and_default_event_types(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IntegrationOutboxService(root_dir=Path(temp_dir))

            webhook = service.register_im_webhook(
                name="IM Notify",
                url="https://example.invalid/im",
                created_by="admin",
                signing_secret="secret",
            )

            self.assertEqual(webhook.delivery_channel, "im_notify")
            self.assertEqual(
                webhook.subscribed_event_types,
                IntegrationOutboxService.im_notification_event_types(),
            )

    def test_register_feishu_webhook_uses_feishu_channel_and_default_event_types(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IntegrationOutboxService(root_dir=Path(temp_dir))

            webhook = service.register_feishu_webhook(
                name="Feishu Bot",
                url="https://example.invalid/feishu",
                created_by="admin",
                signing_secret="feishu-test-secret",
            )

            self.assertEqual(webhook.delivery_channel, "feishu_bot")
            self.assertEqual(
                webhook.subscribed_event_types,
                IntegrationOutboxService.feishu_bot_event_types(),
            )

    def test_deliver_pending_events_marks_delivery_metadata(self) -> None:
        with TemporaryDirectory() as temp_dir:
            deliveries: list[tuple[str, dict[str, str], bytes]] = []

            def transport(url: str, headers, body: bytes):
                deliveries.append((url, dict(headers), body))
                return 202, "accepted"

            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                delivery_transport=transport,
            )
            service.publish_event(
                event_type="issue.assigned",
                target_type="issue",
                target_id="ifp_1",
                created_by="tester",
                payload={"assignee_id": "developer"},
            )
            service.register_webhook(
                name="CI Callback",
                url="https://example.invalid/callback",
                subscribed_event_types=("issue.assigned",),
                created_by="admin",
                signing_secret="secret",
            )

            result = service.deliver_pending_events(webhook_name="CI Callback", limit=10)
            event = service.list_events(limit=10)[0]

            self.assertEqual(result["attempted_count"], 1)
            self.assertEqual(result["delivered_count"], 1)
            self.assertEqual(event.delivery_status, "delivered")
            self.assertEqual(event.attempt_count, 1)
            self.assertIsNotNone(event.delivered_at)
            self.assertTrue(event.signature.startswith("sha256="))
            self.assertTrue(event.idempotency_key.startswith("idem:"))
            self.assertEqual(len(event.consumer_receipts), 1)
            self.assertEqual(event.consumer_receipts[0].webhook_name, "CI Callback")
            self.assertEqual(deliveries[0][0], "https://example.invalid/callback")
            self.assertEqual(deliveries[0][1]["X-ASL-Event-Type"], "issue.assigned")
            self.assertEqual(deliveries[0][1]["X-ASL-Signature"], event.signature)
            self.assertEqual(deliveries[0][1]["X-ASL-Event-Id"], event.event_id)
            self.assertEqual(deliveries[0][1]["X-ASL-Idempotency-Key"], event.idempotency_key)
            self.assertEqual(deliveries[0][1]["X-ASL-Delivery-Contract"], "asl.webhook_delivery.v1")
            self.assertEqual(deliveries[0][1]["X-ASL-Callback-Contract-Version"], "asl.webhook_callback.v1")
            self.assertEqual(deliveries[0][1]["X-ASL-Failure-Policy"], "retryable_http")

    def test_im_delivery_uses_im_contract_body(self) -> None:
        with TemporaryDirectory() as temp_dir:
            deliveries: list[tuple[str, dict[str, str], bytes]] = []

            def transport(url: str, headers, body: bytes):
                deliveries.append((url, dict(headers), body))
                return 202, '{"receipt_id":"im-ack-1","consumer_id":"im-bot"}'

            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                delivery_transport=transport,
            )
            service.publish_event(
                event_type="admission_case.updated",
                target_type="admission_case",
                target_id="baseline_1",
                created_by="tester",
                payload={
                    "final_decision": "conditional_pass",
                    "status": "approved_with_risk",
                    "final_reviewer": "qa_lead",
                },
            )
            service.register_im_webhook(
                name="IM Notify",
                url="https://example.invalid/im",
                created_by="admin",
                signing_secret="secret",
            )

            result = service.deliver_pending_events(webhook_name="IM Notify", limit=10)
            body = json.loads(deliveries[0][2].decode("utf-8"))

            self.assertEqual(result["delivered_count"], 1)
            self.assertEqual(body["contract_version"], "asl.im_notify.v1")
            self.assertEqual(body["delivery_channel"], "im_notify")
            self.assertEqual(body["message_type"], "markdown")
            self.assertEqual(body["event"]["event_type"], "admission_case.updated")
            self.assertEqual(body["original_payload"]["final_decision"], "conditional_pass")
            self.assertIn("准入单更新", body["title"])
            self.assertIn("approved_with_risk", body["message"])

    def test_feishu_delivery_uses_custom_bot_body_signature_and_consumer_receipt(self) -> None:
        with TemporaryDirectory() as temp_dir:
            deliveries: list[tuple[str, dict[str, str], bytes]] = []

            def transport(url: str, headers, body: bytes):
                deliveries.append((url, dict(headers), body))
                return 202, '{"receipt_id":"feishu-ack-1","consumer_id":"feishu-bot"}'

            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                delivery_transport=transport,
            )
            service.publish_event(
                event_type="admission_case.updated",
                target_type="admission_case",
                target_id="baseline_1",
                created_by="tester",
                payload={
                    "final_decision": "conditional_pass",
                    "status": "approved_with_risk",
                    "final_reviewer": "qa_lead",
                },
            )
            service.register_feishu_webhook(
                name="Feishu Bot",
                url="https://example.invalid/feishu",
                created_by="admin",
                signing_secret="feishu-test-secret",
                signature_key_id="feishu-test-v1",
            )

            now = datetime(2025, 7, 24, 10, 0, 0, tzinfo=timezone.utc)
            result = service.deliver_pending_events(webhook_name="Feishu Bot", limit=10, now=now)
            event = service.list_events(limit=10)[0]
            body = json.loads(deliveries[0][2].decode("utf-8"))
            expected_sign = base64.b64encode(
                hmac.new(
                    b"1753351200\nfeishu-test-secret",
                    b"",
                    digestmod=hashlib.sha256,
                ).digest()
            ).decode("utf-8")

            self.assertEqual(result["delivered_count"], 1)
            self.assertEqual(body["timestamp"], "1753351200")
            self.assertEqual(body["sign"], expected_sign)
            self.assertEqual(body["msg_type"], "text")
            self.assertIn("content", body)
            self.assertIn("准入单更新", body["content"]["text"])
            self.assertIn("admission_case.updated", body["content"]["text"])
            self.assertIn(event.idempotency_key, body["content"]["text"])
            self.assertEqual(deliveries[0][1]["X-ASL-Signature-Alg"], "sha256")
            self.assertEqual(deliveries[0][1]["X-ASL-Signature"], event.signature)
            self.assertEqual(len(event.consumer_receipts), 1)
            self.assertEqual(event.consumer_receipts[0].consumer_id, "feishu-bot")
            self.assertEqual(event.consumer_receipts[0].consumer_receipt_id, "feishu-ack-1")

    def test_feishu_delivery_treats_naive_datetime_as_utc_for_signature_timestamp(self) -> None:
        with TemporaryDirectory() as temp_dir:
            deliveries: list[tuple[str, dict[str, str], bytes]] = []

            def transport(url: str, headers, body: bytes):
                deliveries.append((url, dict(headers), body))
                return 200, '{"code":0,"msg":"success"}'

            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                delivery_transport=transport,
            )
            service.publish_event(
                event_type="admission_case.updated",
                target_type="admission_case",
                target_id="baseline_1",
                created_by="tester",
                payload={"final_decision": "pass"},
            )
            service.register_feishu_webhook(
                name="Feishu Bot",
                url="https://example.invalid/feishu",
                created_by="admin",
                signing_secret="feishu-test-secret",
            )

            now = datetime(2025, 7, 24, 10, 0, 0)
            result = service.deliver_pending_events(webhook_name="Feishu Bot", limit=10, now=now)
            body = json.loads(deliveries[0][2].decode("utf-8"))

            self.assertEqual(result["delivered_count"], 1)
            self.assertEqual(body["timestamp"], "1753351200")

    def test_feishu_delivery_treats_business_error_body_as_failure(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                delivery_transport=lambda url, headers, body: (
                    200,
                    '{"code":19021,"data":{},"msg":"sign match fail or timestamp is not within one hour from current time"}',
                ),
            )
            service.publish_event(
                event_type="admission_case.updated",
                target_type="admission_case",
                target_id="baseline_1",
                created_by="tester",
                payload={"final_decision": "pass"},
            )
            service.register_feishu_webhook(
                name="Feishu Bot",
                url="https://example.invalid/feishu",
                created_by="admin",
                signing_secret="feishu-test-secret",
            )

            result = service.deliver_pending_events(webhook_name="Feishu Bot", limit=10)
            event = self._event_by_type(service, "admission_case.updated")

            self.assertEqual(result["delivered_count"], 0)
            self.assertEqual(result["dead_letter_count"], 1)
            self.assertEqual(event.delivery_status, "dead_letter")
            self.assertIn("code=19021", event.last_error)
            self.assertEqual(len(event.consumer_receipts), 0)

    def test_register_defect_webhook_and_delivery_use_defect_contract(self) -> None:
        with TemporaryDirectory() as temp_dir:
            deliveries: list[tuple[str, dict[str, str], bytes]] = []

            def transport(url: str, headers, body: bytes):
                deliveries.append((url, dict(headers), body))
                return 202, '{"receipt_id":"defect-ack-1","consumer_id":"jira-bridge"}'

            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                delivery_transport=transport,
            )
            service.publish_event(
                event_type="issue.defect_create_requested",
                target_type="issue",
                target_id="ifp_2",
                created_by="tester",
                payload={
                    "fingerprint": "ifp_2",
                    "issue_title": "首页冷启动偶发崩溃",
                    "system_key": "jira",
                    "team_key": "android-client",
                    "defect": {
                        "link_id": "link_1",
                        "title": "首页冷启动偶发崩溃",
                        "sync_status": "pending_create",
                    },
                },
            )
            webhook = service.register_defect_webhook(
                name="Defect Sync",
                url="https://example.invalid/defect",
                created_by="admin",
                signing_secret="secret",
            )

            result = service.deliver_pending_events(webhook_name="Defect Sync", limit=10)
            body = json.loads(deliveries[0][2].decode("utf-8"))

            self.assertEqual(webhook.delivery_channel, "defect_sync")
            self.assertEqual(
                webhook.subscribed_event_types,
                IntegrationOutboxService.defect_sync_event_types(),
            )
            self.assertEqual(result["delivered_count"], 1)
            self.assertEqual(body["contract_version"], "asl.defect_sync.v1")
            self.assertEqual(body["delivery_channel"], "defect_sync")
            self.assertEqual(body["action"], "create_defect")
            self.assertEqual(body["issue"]["fingerprint"], "ifp_2")
            self.assertEqual(body["defect"]["system_key"], "jira")
            self.assertEqual(body["routing"]["webhook_name"], "Defect Sync")

    def test_register_release_webhook_and_delivery_use_release_submission_contract(self) -> None:
        with TemporaryDirectory() as temp_dir:
            deliveries: list[tuple[str, dict[str, str], bytes]] = []

            def transport(url: str, headers, body: bytes):
                deliveries.append((url, dict(headers), body))
                return 202, '{"receipt_id":"release-ack-1","consumer_id":"release-center"}'

            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                delivery_transport=transport,
            )
            service.publish_event(
                event_type="release_submission.admission_synced",
                target_type="release_submission",
                target_id="release_submission_1",
                created_by="release-bot",
                payload={
                    "submission_id": "release_submission_1",
                    "source_platform": "release-center",
                    "source_request_id": "REL-2026-001",
                    "package_name": "com.example.app",
                    "version_name": "1.2.3",
                    "release_channel": "gray",
                    "submission_status": "admission_synced",
                    "task_id": "task_1",
                    "run_id": "run_1",
                    "run_status": "success",
                    "baseline_key": "baseline-release-gray",
                    "admission_case_id": "admission_case:baseline-release-gray",
                    "admission_status": "approved_with_risk",
                    "admission_final_decision": "conditional_pass",
                    "admission_error_code": "CONDITIONAL_PASS",
                },
            )
            webhook = service.register_release_webhook(
                name="Release Sync",
                url="https://example.invalid/release",
                created_by="admin",
                signing_secret="secret",
            )

            result = service.deliver_pending_events(webhook_name="Release Sync", limit=10)
            body = json.loads(deliveries[0][2].decode("utf-8"))

            self.assertEqual(webhook.delivery_channel, "release_submission")
            self.assertEqual(
                webhook.subscribed_event_types,
                IntegrationOutboxService.release_submission_event_types(),
            )
            self.assertEqual(result["delivered_count"], 1)
            self.assertEqual(body["contract_version"], "asl.release_submission.v1")
            self.assertEqual(body["delivery_channel"], "release_submission")
            self.assertEqual(body["action"], "sync_admission_result")
            self.assertEqual(body["submission"]["submission_id"], "release_submission_1")
            self.assertEqual(body["submission"]["source_request_id"], "REL-2026-001")
            self.assertEqual(body["task"]["task_id"], "task_1")
            self.assertEqual(body["run"]["run_status"], "success")
            self.assertEqual(body["admission"]["final_decision"], "conditional_pass")
            self.assertEqual(body["routing"]["webhook_name"], "Release Sync")

    def test_failed_delivery_moves_event_to_retry_pending(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                retry_delay_seconds=120,
                delivery_transport=lambda url, headers, body: (500, "server unavailable"),
            )
            service.publish_event(
                event_type="admission.override_recorded",
                target_type="admission",
                target_id="device_offline_default",
                created_by="tester",
                payload={"final_decision": "pass"},
            )
            service.register_webhook(
                name="IM Notify",
                url="https://example.invalid/im",
                subscribed_event_types=("admission.override_recorded",),
                created_by="admin",
                signing_secret="secret",
            )

            result = service.deliver_pending_events(webhook_name="IM Notify", limit=10)
            event = service.list_events(limit=10)[0]

            self.assertEqual(result["attempted_count"], 1)
            self.assertEqual(result["failed_count"], 1)
            self.assertEqual(event.delivery_status, "retry_pending")
            self.assertEqual(event.attempt_count, 1)
            self.assertEqual(event.last_error, "server unavailable")
            self.assertIsNotNone(event.last_attempt_at)
            self.assertIsNotNone(event.next_retry_at)
            self.assertEqual(event.retry_backoff_seconds, 120)

    def test_delivery_respects_fixed_frequency_backoff_and_emits_retry_alert(self) -> None:
        with TemporaryDirectory() as temp_dir:
            responses = iter(((500, "server unavailable"), (500, "still unavailable"), (202, "accepted")))
            deliveries: list[datetime] = []
            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                retry_delay_seconds=10,
                delivery_interval_seconds=5,
                retry_alert_threshold=2,
                delivery_transport=lambda url, headers, body: (deliveries.append(datetime.now()), next(responses))[1],
            )
            created = datetime(2025, 7, 23, 9, 0, 0)
            service.publish_event(
                event_type="issue.assigned",
                target_type="issue",
                target_id="ifp_2",
                created_by="tester",
                payload={"assignee_id": "developer"},
            )
            service.register_webhook(
                name="CI Callback",
                url="https://example.invalid/callback",
                subscribed_event_types=("issue.assigned",),
                created_by="admin",
                signing_secret="secret",
            )

            first = service.deliver_pending_events(webhook_name="CI Callback", limit=10, now=created)
            first_event = self._event_by_type(service, "issue.assigned")
            self.assertEqual(first["attempted_count"], 1)
            self.assertEqual(first["failed_count"], 1)
            self.assertEqual(first_event.delivery_status, "retry_pending")
            self.assertEqual(first_event.retry_backoff_seconds, 10)
            self.assertEqual(first_event.next_retry_at, created + timedelta(seconds=10))

            gated = service.deliver_pending_events(webhook_name="CI Callback", limit=10, now=created + timedelta(seconds=4))
            gated_event = self._event_by_type(service, "issue.assigned")
            self.assertEqual(gated["attempted_count"], 0)
            self.assertEqual(gated_event.attempt_count, 1)

            second = service.deliver_pending_events(webhook_name="CI Callback", limit=10, now=created + timedelta(seconds=10))
            second_event = self._event_by_type(service, "issue.assigned")
            alert_event = self._event_by_type(service, "outbox.retry_alert")
            self.assertEqual(second["attempted_count"], 1)
            self.assertEqual(second["alert_emitted_count"], 1)
            self.assertEqual(second_event.delivery_status, "retry_pending")
            self.assertEqual(second_event.attempt_count, 2)
            self.assertEqual(second_event.retry_backoff_seconds, 20)
            self.assertEqual(second_event.next_retry_at, created + timedelta(seconds=30))
            self.assertEqual(second_event.alert_status, "emitted")
            self.assertEqual(second_event.alert_count, 1)
            self.assertEqual(alert_event.target_id, second_event.event_id)
            self.assertEqual(alert_event.delivery_status, "pending")

            third = service.deliver_pending_events(webhook_name="CI Callback", limit=10, now=created + timedelta(seconds=30))
            delivered_event = self._event_by_type(service, "issue.assigned")
            self.assertEqual(third["attempted_count"], 1)
            self.assertEqual(third["delivered_count"], 1)
            self.assertEqual(delivered_event.delivery_status, "delivered")
            self.assertEqual(delivered_event.attempt_count, 3)

    def test_non_retryable_failure_dead_letters_event_without_re_amplifying(self) -> None:
        with TemporaryDirectory() as temp_dir:
            attempts: list[int] = []

            def transport(url: str, headers, body: bytes):
                attempts.append(1)
                return 400, "bad request"

            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                retry_delay_seconds=10,
                dead_letter_threshold=4,
                delivery_transport=transport,
            )
            service.publish_event(
                event_type="admission.override_recorded",
                target_type="admission",
                target_id="baseline_1",
                created_by="tester",
                payload={"final_decision": "fail"},
            )
            service.register_webhook(
                name="CI Callback",
                url="https://example.invalid/callback",
                subscribed_event_types=("admission.override_recorded",),
                created_by="admin",
                signing_secret="secret",
            )

            first = service.deliver_pending_events(
                webhook_name="CI Callback",
                limit=10,
                now=datetime(2025, 7, 23, 10, 0, 0),
            )
            event = self._event_by_type(service, "admission.override_recorded")
            self.assertEqual(first["attempted_count"], 1)
            self.assertEqual(first["dead_lettered_count"], 1)
            self.assertEqual(event.delivery_status, "dead_letter")
            self.assertIsNotNone(event.dead_lettered_at)
            self.assertIn("non-retryable", event.last_error)
            self.assertIsNone(event.next_retry_at)

            second = service.deliver_pending_events(
                webhook_name="CI Callback",
                limit=10,
                now=datetime(2025, 7, 23, 10, 5, 0),
            )
            self.assertEqual(second["attempted_count"], 0)
            self.assertEqual(len(attempts), 1)

    def test_delivery_worker_status_and_dead_letter_replay_are_persisted(self) -> None:
        with TemporaryDirectory() as temp_dir:
            attempts: list[int] = []

            def transport(url: str, headers, body: bytes):
                attempts.append(1)
                if len(attempts) == 1:
                    return 400, "bad request"
                return 202, '{"receipt_id":"ack-1","consumer_id":"ci"}'

            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                delivery_transport=transport,
            )
            service.publish_event(
                event_type="admission.override_recorded",
                target_type="admission",
                target_id="baseline_1",
                created_by="tester",
                payload={"final_decision": "fail"},
            )
            service.register_webhook(
                name="CI Callback",
                url="https://example.invalid/callback",
                subscribed_event_types=("admission.override_recorded",),
                created_by="admin",
                signing_secret="secret",
            )

            first = service.run_delivery_worker(webhook_names=("CI Callback",), limit_per_webhook=5, now=datetime(2025, 7, 23, 10, 0, 0))
            self.assertEqual(first["worker"]["status"], "idle")
            self.assertEqual(first["worker"]["run_count"], 1)
            self.assertEqual(first["delivery_rounds"][0]["dead_lettered_count"], 1)

            replay = service.replay_dead_lettered_events(
                webhook_name="CI Callback",
                limit=5,
                now=datetime(2025, 7, 23, 10, 1, 0),
                replayed_by="operator",
            )
            self.assertEqual(replay["replayed_count"], 1)
            self.assertEqual(len(replay["replay_receipt_ids"]), 1)
            self.assertEqual(len(replay["operator_receipt_ids"]), 1)

            second = service.run_delivery_worker(webhook_names=("CI Callback",), limit_per_webhook=5, now=datetime(2025, 7, 23, 10, 2, 0))
            event = self._event_by_type(service, "admission.override_recorded")
            worker = service.get_worker_status()
            worker_aggregate = dict(worker.last_run_summary.get("aggregate", {}) or {})
            self.assertEqual(second["delivery_rounds"][0]["delivered_count"], 1)
            self.assertEqual(event.delivery_status, "delivered")
            self.assertEqual(event.consumer_receipts[0].consumer_receipt_id, "ack-1")
            self.assertEqual(event.replay_receipts[0].replayed_by, "operator")
            self.assertEqual(event.operator_receipts[0].operator_id, "operator")
            self.assertEqual(worker.replay_count, 1)
            self.assertTrue(worker.last_operator_receipt_id)

    def test_run_delivery_daemon_persists_daemon_worker_state(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                delivery_transport=lambda url, headers, body: (202, '{"receipt_id":"ack-2","consumer_id":"ci"}'),
            )
            service.publish_event(
                event_type="admission_case.updated",
                target_type="admission_case",
                target_id="baseline_1",
                created_by="tester",
                payload={"final_decision": "pass"},
            )
            service.register_webhook(
                name="CI Callback",
                url="https://example.invalid/callback",
                subscribed_event_types=("admission_case.updated",),
                created_by="admin",
                signing_secret="secret",
                delivery_channel="ci_callback",
            )

            result = service.run_delivery_daemon(
                webhook_names=("CI Callback",),
                event_types=("admission_case.updated",),
                limit_per_webhook=5,
                interval_seconds=0,
                max_rounds=1,
                chain_name="ci_admission_callback",
            )
            worker = service.get_worker_status()

            self.assertEqual(result["mode"], "daemon")
            self.assertEqual(result["rounds_executed"], 1)
            self.assertEqual(worker.worker_mode, "daemon")
            self.assertEqual(worker.chain_name, "ci_admission_callback")
            self.assertEqual(tuple(worker.configured_event_types), ("admission_case.updated",))
            self.assertEqual(result["aggregate"]["attempted_count"], 1)
            self.assertEqual(result["aggregate"]["delivered_count"], 1)
            self.assertEqual(result["aggregate"]["receipt_count"], 1)
            self.assertEqual(result["rounds"][0]["receipt_count"], 1)

    def test_second_delivery_round_is_deduplicated_by_consumer_receipt(self) -> None:
        with TemporaryDirectory() as temp_dir:
            attempts: list[int] = []

            def transport(url: str, headers, body: bytes):
                attempts.append(1)
                return 202, '{"receipt_id":"ack-1"}'

            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                delivery_transport=transport,
            )
            service.publish_event(
                event_type="issue.assigned",
                target_type="issue",
                target_id="ifp_1",
                created_by="tester",
                payload={"assignee_id": "developer"},
            )
            service.register_webhook(
                name="CI Callback",
                url="https://example.invalid/callback",
                subscribed_event_types=("issue.assigned",),
                created_by="admin",
                signing_secret="secret",
            )

            first = service.deliver_pending_events(webhook_name="CI Callback", limit=10)
            second = service.deliver_pending_events(webhook_name="CI Callback", limit=10)

            self.assertEqual(first["delivered_count"], 1)
            self.assertEqual(second["attempted_count"], 0)
            self.assertEqual(second["deduplicated_count"], 1)
            self.assertEqual(second["receipt_count"], 1)
            self.assertEqual(len(attempts), 1)

    def test_worker_aggregates_retry_dead_letter_dedup_and_receipts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            attempts: list[str] = []

            def transport(url: str, headers, body: bytes):
                event_id = str(headers["X-ASL-Event-Id"])
                attempts.append(event_id)
                if len(attempts) == 1:
                    return 202, '{"receipt_id":"ack-1","consumer_id":"im-bot"}'
                if len(attempts) == 2:
                    return 500, "retry me"
                return 400, "bad request"

            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                retry_delay_seconds=60,
                delivery_transport=transport,
            )
            service.publish_event(
                event_type="issue.assigned",
                target_type="issue",
                target_id="ifp_delivered",
                created_by="tester",
                payload={"assignee_id": "developer"},
            )
            service.publish_event(
                event_type="issue.commented",
                target_type="issue",
                target_id="ifp_retry",
                created_by="tester",
                payload={"comment": "please retry"},
            )
            service.publish_event(
                event_type="admission.override_recorded",
                target_type="admission",
                target_id="ifp_dead",
                created_by="tester",
                payload={"final_decision": "fail"},
            )
            service.register_webhook(
                name="IM Notify",
                url="https://example.invalid/im",
                subscribed_event_types=("issue.assigned", "issue.commented", "admission.override_recorded"),
                created_by="admin",
                signing_secret="secret",
                delivery_channel="im_notify",
            )

            first = service.run_delivery_worker(
                webhook_names=("IM Notify",),
                limit_per_webhook=5,
                now=datetime(2025, 7, 24, 10, 0, 0),
            )
            second = service.run_delivery_worker(
                webhook_names=("IM Notify",),
                limit_per_webhook=5,
                now=datetime(2025, 7, 24, 10, 0, 30),
            )
            worker = service.get_worker_status()
            worker_aggregate = dict(worker.last_run_summary.get("aggregate", {}) or {})

            self.assertEqual(first["worker"]["last_run_summary"]["aggregate"]["attempted_count"], 3)
            self.assertEqual(first["worker"]["last_run_summary"]["aggregate"]["delivered_count"], 1)
            self.assertEqual(first["worker"]["last_run_summary"]["aggregate"]["retry_count"], 1)
            self.assertEqual(first["worker"]["last_run_summary"]["aggregate"]["dead_letter_count"], 1)
            self.assertEqual(first["worker"]["last_run_summary"]["aggregate"]["receipt_count"], 1)
            self.assertEqual(second["worker"]["last_run_summary"]["aggregate"]["deduplicated_count"], 1)
            self.assertEqual(second["worker"]["last_run_summary"]["aggregate"]["receipt_count"], 1)
            self.assertEqual(worker_aggregate["attempted_count"], 0)
            self.assertEqual(worker_aggregate["deduplicated_count"], 1)
            self.assertEqual(worker_aggregate["receipt_count"], 1)
            self.assertEqual(worker.delivered_count, 1)
            self.assertEqual(worker.failed_count, 2)

    def test_feishu_acceptance_summary_reports_delivery_audit_coverage(self) -> None:
        with TemporaryDirectory() as temp_dir:
            responses = iter(
                (
                    (202, '{"receipt_id":"feishu-ack-1","consumer_id":"feishu-bot"}'),
                    (500, "server unavailable"),
                    (400, "bad request"),
                )
            )
            service = IntegrationOutboxService(
                root_dir=Path(temp_dir),
                retry_delay_seconds=60,
                delivery_transport=lambda url, headers, body: next(responses),
            )
            service.publish_event(
                event_type="admission_case.updated",
                target_type="admission_case",
                target_id="baseline_ok",
                created_by="tester",
                payload={"final_decision": "pass"},
            )
            service.publish_event(
                event_type="issue.assigned",
                target_type="issue",
                target_id="ifp_retry",
                created_by="tester",
                payload={"assignee_id": "developer"},
            )
            service.publish_event(
                event_type="admission.override_recorded",
                target_type="admission",
                target_id="baseline_dead",
                created_by="tester",
                payload={"final_decision": "fail"},
            )
            service.register_feishu_webhook(
                name="Feishu Bot",
                url="https://example.invalid/feishu",
                created_by="admin",
                signing_secret="secret",
            )

            service.run_feishu_notify_worker(
                webhook_names=("Feishu Bot",),
                limit_per_webhook=5,
                daemon=False,
            )
            summary = service.build_feishu_delivery_acceptance_summary()

            self.assertEqual(summary["name"], "feishu_bot")
            self.assertEqual(summary["total_event_count"], 4)
            self.assertEqual(summary["success_count"], 1)
            self.assertEqual(summary["failed_count"], 2)
            self.assertEqual(summary["retry_count"], 1)
            self.assertEqual(summary["dead_letter_count"], 1)
            self.assertEqual(summary["consumer_receipt_count"], 1)
            self.assertTrue(summary["coverage"]["last_error"]["is_complete"])
            self.assertTrue(summary["coverage"]["failure_category"]["is_complete"])
            self.assertTrue(summary["coverage"]["next_retry_at"]["is_complete"])
            self.assertEqual(summary["worker_counters"]["attempted_count"], 3)
            self.assertEqual(summary["worker_counters"]["receipt_count"], 1)

    @staticmethod
    def _event_by_type(service: IntegrationOutboxService, event_type: str):
        for item in service.list_events(limit=20):
            if item.event_type == event_type:
                return item
        raise AssertionError(f"missing event_type={event_type}")


if __name__ == "__main__":
    unittest.main()
