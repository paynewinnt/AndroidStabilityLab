from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime, timedelta
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from stability.app import DeviceRecordNotFound
from stability.app.analysis_service import AggregatedIssueNotFound
from stability.app.task_service import TaskRecordNotFound
from stability.cli import task_create
from tests.helpers.cli import run_main_with_bundle


class CLIWebIntegrationCommandsTest(unittest.TestCase):
    def test_serve_web_outputs_startup_payload_and_invokes_server(self) -> None:
        bundle = SimpleNamespace(device_service=None)
        serve_calls: list[tuple[str, int, object, bool, str, str, str]] = []

        with patch("stability.cli.task_create.create_v1_persistent_bootstrap", return_value=bundle):
            with patch(
                "stability.cli.task_create.serve_web_portal",
                side_effect=lambda host, port, bundle, allow_remote_access=False, portal_mode="local_ops_console", public_base_url="", deployment_label="": serve_calls.append(
                    (host, port, bundle, allow_remote_access, portal_mode, public_base_url, deployment_label)
                ),
            ):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    exit_code = task_create.main(["serve-web", "--host", "127.0.0.1", "--port", "8041"])

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["web"]["url"], "http://127.0.0.1:8041/")
        self.assertEqual(payload["web"]["mode"], "local_ops_console")
        self.assertFalse(payload["web"]["allow_remote_access"])
        self.assertEqual(payload["web"]["public_base_url"], "http://127.0.0.1:8041/")
        self.assertEqual(
            payload["web"]["pages"],
            ["/", "/platform", "/tasks", "/long-run-templates", "/performance", "/issues", "/runner", "/integration", "/goldens", "/admission", "/json-api"],
        )
        self.assertIn("/api/platform", payload["web"]["api_endpoints"])
        self.assertIn("/api/manifest", payload["web"]["api_endpoints"])
        self.assertIn("/api/openapi.json", payload["web"]["api_endpoints"])
        self.assertIn("/api/long-run-templates", payload["web"]["api_endpoints"])
        self.assertIn("/api/runner", payload["web"]["api_endpoints"])
        self.assertIn("/api/integration", payload["web"]["api_endpoints"])
        self.assertIn("/api/integration/outbox", payload["web"]["api_endpoints"])
        self.assertIn("/ready", payload["web"]["api_endpoints"])
        self.assertEqual(serve_calls, [("127.0.0.1", 8041, bundle, False, "local_ops_console", "", "")])

    def test_serve_web_rejects_non_local_host_without_explicit_flag(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            task_create.main(["serve-web", "--host", "0.0.0.0", "--port", "8041"])

        self.assertIn("--allow-remote-access", str(ctx.exception))

    def test_serve_web_rejects_team_entry_without_public_base_url(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            task_create.main(["serve-web", "--portal-mode", "team_entry"])

        self.assertIn("--public-base-url", str(ctx.exception))

    def test_serve_web_allows_non_local_host_with_explicit_flag(self) -> None:
        bundle = SimpleNamespace(device_service=None)
        serve_calls: list[tuple[str, int, object, bool, str, str, str]] = []

        with patch("stability.cli.task_create.create_v1_persistent_bootstrap", return_value=bundle):
            with patch(
                "stability.cli.task_create.serve_web_portal",
                side_effect=lambda host, port, bundle, allow_remote_access=False, portal_mode="local_ops_console", public_base_url="", deployment_label="": serve_calls.append(
                    (host, port, bundle, allow_remote_access, portal_mode, public_base_url, deployment_label)
                ),
            ):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    exit_code = task_create.main(
                        ["serve-web", "--host", "0.0.0.0", "--port", "8041", "--allow-remote-access"]
                    )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["web"]["allow_remote_access"])
        self.assertEqual(serve_calls, [("0.0.0.0", 8041, bundle, True, "local_ops_console", "", "")])

    def test_serve_web_supports_team_entry_mode(self) -> None:
        bundle = SimpleNamespace(device_service=None)
        serve_calls: list[tuple[str, int, object, bool, str, str, str]] = []

        with patch("stability.cli.task_create.create_v1_persistent_bootstrap", return_value=bundle):
            with patch(
                "stability.cli.task_create.serve_web_portal",
                side_effect=lambda host, port, bundle, allow_remote_access=False, portal_mode="local_ops_console", public_base_url="", deployment_label="": serve_calls.append(
                    (host, port, bundle, allow_remote_access, portal_mode, public_base_url, deployment_label)
                ),
            ):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    exit_code = task_create.main(
                        [
                            "serve-web",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            "8041",
                            "--portal-mode",
                            "team_entry",
                            "--public-base-url",
                            "https://stability.example.internal",
                            "--deployment-label",
                            "team-shared",
                        ]
                    )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["web"]["mode"], "team_entry")
        self.assertEqual(payload["web"]["public_base_url"], "https://stability.example.internal")
        self.assertEqual(payload["web"]["deployment_label"], "team-shared")
        self.assertIn("Shared team entry mode enabled", payload["web"]["warning"])
        self.assertEqual(
            serve_calls,
            [("127.0.0.1", 8041, bundle, False, "team_entry", "https://stability.example.internal", "team-shared")],
        )

    def test_register_integration_webhook_outputs_registration_payload(self) -> None:
        register_calls: list[dict[str, object]] = []
        bundle = SimpleNamespace(
            integration_outbox_service=SimpleNamespace(
                register_webhook=lambda **kwargs: register_calls.append(dict(kwargs)) or SimpleNamespace(
                    webhook_id="webhook_1",
                    name=kwargs["name"],
                    url=kwargs["url"],
                    subscribed_event_types=tuple(kwargs["subscribed_event_types"]),
                    created_at=None,
                    created_by=kwargs["created_by"],
                    secret_hint=kwargs["secret_hint"],
                    signature_key_id=kwargs.get("signature_key_id", "v1"),
                    accepted_signature_key_ids=tuple(kwargs.get("accepted_signature_key_ids", ())),
                    failure_policy=kwargs.get("failure_policy", "retryable_http"),
                    delivery_channel=kwargs.get("delivery_channel", "generic"),
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "register-integration-webhook",
                "--name",
                "IM Notify",
                "--url",
                "https://example.invalid/im",
                "--event-type",
                "issue.assigned,admission.override_recorded",
                "--created-by",
                "admin",
                "--secret-hint",
                "configured in IM robot",
            ],
            bundle,
        )

        self.assertEqual(payload["webhook"]["name"], "IM Notify")
        self.assertEqual(
            payload["webhook"]["subscribed_event_types"],
            ["issue.assigned", "admission.override_recorded"],
        )
        self.assertEqual(payload["webhook"]["callback_contract_version"], "asl.webhook_callback.v1")
        self.assertEqual(payload["webhook"]["signature_key_id"], "v1")
        self.assertEqual(payload["webhook"]["failure_policy"], "retryable_http")
        self.assertEqual(
            payload["webhook"]["security_rules"],
            [
                "non-local webhook requires https",
                "non-local webhook requires signing_secret",
                "delivery uses signature headers plus idempotency key",
            ],
        )
        self.assertEqual(register_calls[0]["created_by"], "admin")

    def test_register_im_webhook_outputs_im_contract_payload(self) -> None:
        register_calls: list[dict[str, object]] = []
        bundle = SimpleNamespace(
            integration_outbox_service=SimpleNamespace(
                register_im_webhook=lambda **kwargs: register_calls.append(dict(kwargs)) or SimpleNamespace(
                    webhook_id="webhook_im_1",
                    name=kwargs["name"],
                    url=kwargs["url"],
                    subscribed_event_types=tuple(kwargs.get("subscribed_event_types", ())),
                    created_at=None,
                    created_by=kwargs["created_by"],
                    secret_hint=kwargs["secret_hint"],
                    signature_key_id=kwargs.get("signature_key_id", "v1"),
                    accepted_signature_key_ids=tuple(kwargs.get("accepted_signature_key_ids", ())),
                    failure_policy=kwargs.get("failure_policy", "retryable_http"),
                    delivery_channel="im_notify",
                ),
                im_notification_event_types=lambda: (
                    "issue.assigned",
                    "admission_case.updated",
                ),
            )
        )

        payload = self._run_main_with_bundle(
            [
                "register-im-webhook",
                "--name",
                "Team IM",
                "--url",
                "https://example.invalid/im",
                "--created-by",
                "admin",
                "--secret-hint",
                "configured in robot",
            ],
            bundle,
        )

        self.assertEqual(payload["webhook"]["name"], "Team IM")
        self.assertEqual(payload["webhook"]["delivery_channel"], "im_notify")
        self.assertEqual(payload["webhook"]["delivery_contract_version"], "asl.im_notify.v1")
        self.assertIn("im delivery body follows asl.im_notify.v1", payload["webhook"]["security_rules"])
        self.assertEqual(register_calls[0]["created_by"], "admin")

    def test_register_feishu_webhook_outputs_feishu_contract_payload(self) -> None:
        register_calls: list[dict[str, object]] = []
        bundle = SimpleNamespace(
            integration_outbox_service=SimpleNamespace(
                register_feishu_webhook=lambda **kwargs: register_calls.append(dict(kwargs)) or SimpleNamespace(
                    webhook_id="webhook_feishu_1",
                    name=kwargs["name"],
                    url=kwargs["url"],
                    subscribed_event_types=tuple(kwargs.get("subscribed_event_types", ())),
                    created_at=None,
                    created_by=kwargs["created_by"],
                    secret_hint=kwargs["secret_hint"],
                    signature_key_id=kwargs.get("signature_key_id", "feishu-bot"),
                    accepted_signature_key_ids=tuple(kwargs.get("accepted_signature_key_ids", ())),
                    failure_policy=kwargs.get("failure_policy", "retryable_http"),
                    delivery_channel="feishu_bot",
                ),
                feishu_bot_event_types=lambda: (
                    "issue.assigned",
                    "admission_case.updated",
                ),
            )
        )

        payload = self._run_main_with_bundle(
            [
                "register-feishu-webhook",
                "--name",
                "Team Feishu",
                "--url",
                "https://example.invalid/feishu",
                "--created-by",
                "admin",
                "--secret-hint",
                "configured in robot",
            ],
            bundle,
        )

        self.assertEqual(payload["webhook"]["name"], "Team Feishu")
        self.assertEqual(payload["webhook"]["delivery_channel"], "feishu_bot")
        self.assertEqual(payload["webhook"]["delivery_contract_version"], "feishu.custom_bot.v1")
        self.assertIn("feishu delivery body contains timestamp/sign/msg_type/content", payload["webhook"]["security_rules"])
        self.assertEqual(register_calls[0]["created_by"], "admin")

    def test_register_defect_webhook_outputs_defect_contract_payload(self) -> None:
        register_calls: list[dict[str, object]] = []
        bundle = SimpleNamespace(
            integration_outbox_service=SimpleNamespace(
                register_defect_webhook=lambda **kwargs: register_calls.append(dict(kwargs)) or SimpleNamespace(
                    webhook_id="webhook_defect_1",
                    name=kwargs["name"],
                    url=kwargs["url"],
                    subscribed_event_types=tuple(kwargs.get("subscribed_event_types", ())),
                    created_at=None,
                    created_by=kwargs["created_by"],
                    secret_hint=kwargs["secret_hint"],
                    signature_key_id=kwargs.get("signature_key_id", "v1"),
                    accepted_signature_key_ids=tuple(kwargs.get("accepted_signature_key_ids", ())),
                    failure_policy=kwargs.get("failure_policy", "retryable_http"),
                    delivery_channel="defect_sync",
                ),
                defect_sync_event_types=lambda: (
                    "issue.defect_create_requested",
                    "issue.defect_status_synced",
                ),
            )
        )

        payload = self._run_main_with_bundle(
            [
                "register-defect-webhook",
                "--name",
                "Defect Sync",
                "--url",
                "https://example.invalid/defect",
                "--created-by",
                "admin",
                "--secret-hint",
                "configured in defect bridge",
            ],
            bundle,
        )

        self.assertEqual(payload["webhook"]["name"], "Defect Sync")
        self.assertEqual(payload["webhook"]["delivery_channel"], "defect_sync")
        self.assertEqual(payload["webhook"]["delivery_contract_version"], "asl.defect_sync.v1")
        self.assertIn("defect delivery body follows asl.defect_sync.v1", payload["webhook"]["security_rules"])
        self.assertEqual(register_calls[0]["created_by"], "admin")

    def test_register_release_webhook_outputs_release_contract_payload(self) -> None:
        register_calls: list[dict[str, object]] = []
        bundle = SimpleNamespace(
            integration_outbox_service=SimpleNamespace(
                register_release_webhook=lambda **kwargs: register_calls.append(dict(kwargs)) or SimpleNamespace(
                    webhook_id="webhook_release_1",
                    name=kwargs["name"],
                    url=kwargs["url"],
                    subscribed_event_types=tuple(kwargs.get("subscribed_event_types", ())),
                    created_at=None,
                    created_by=kwargs["created_by"],
                    secret_hint=kwargs["secret_hint"],
                    signature_key_id=kwargs.get("signature_key_id", "v1"),
                    accepted_signature_key_ids=tuple(kwargs.get("accepted_signature_key_ids", ())),
                    failure_policy=kwargs.get("failure_policy", "retryable_http"),
                    delivery_channel="release_submission",
                ),
                release_submission_event_types=lambda: (
                    "release_submission.created",
                    "release_submission.admission_synced",
                ),
            )
        )

        payload = self._run_main_with_bundle(
            [
                "register-release-webhook",
                "--name",
                "Release Sync",
                "--url",
                "https://example.invalid/release",
                "--created-by",
                "admin",
                "--secret-hint",
                "configured in release platform",
            ],
            bundle,
        )

        self.assertEqual(payload["webhook"]["name"], "Release Sync")
        self.assertEqual(payload["webhook"]["delivery_channel"], "release_submission")
        self.assertEqual(payload["webhook"]["delivery_contract_version"], "asl.release_submission.v1")
        self.assertIn("release delivery body follows asl.release_submission.v1", payload["webhook"]["security_rules"])
        self.assertEqual(register_calls[0]["created_by"], "admin")

    def test_deliver_integration_outbox_outputs_delivery_summary(self) -> None:
        delivery_calls: list[dict[str, object]] = []
        bundle = SimpleNamespace(
            integration_outbox_service=SimpleNamespace(
                list_webhooks=lambda: (SimpleNamespace(name="IM Notify"),),
                _delivery_interval=300,
                _retry_delay=300,
                _max_retry_delay=3600,
                _dead_letter_threshold=5,
                _retry_alert_threshold=3,
                deliver_pending_events=lambda **kwargs: delivery_calls.append(dict(kwargs)) or {
                    "webhook_name": kwargs["webhook_name"],
                    "attempted_count": 2,
                    "delivered_count": 1,
                    "failed_count": 1,
                    "skipped_count": 0,
                    "delivered_event_ids": ["outbox_event_1"],
                    "remaining_pending_count": 3,
                }
            )
        )

        payload = self._run_main_with_bundle(
            [
                "deliver-integration-outbox",
                "--webhook-name",
                "IM Notify",
                "--event-type",
                "issue.assigned",
                "--limit",
                "5",
            ],
            bundle,
        )

        self.assertEqual(payload["delivery"]["webhook_name"], "IM Notify")
        self.assertEqual(payload["delivery"]["attempted_count"], 2)
        self.assertEqual(payload["worker"]["mode"], "single_delivery_round")
        self.assertEqual(payload["delivery"]["receipt_keys"], ["asl.outbox.receipt.v1:IM Notify:outbox_event_1"])
        self.assertEqual(delivery_calls[0]["event_types"], ("issue.assigned",))
        self.assertEqual(delivery_calls[0]["limit"], 5)

    def test_run_integration_outbox_worker_outputs_round_summary(self) -> None:
        delivery_calls: list[dict[str, object]] = []
        counters = {"IM Notify": 0, "CI Callback": 0}

        def _deliver(**kwargs):
            webhook_name = kwargs["webhook_name"]
            counters[webhook_name] += 1
            delivery_calls.append(dict(kwargs))
            attempted = 1 if counters[webhook_name] == 1 else 0
            remaining = 1 if webhook_name == "CI Callback" and counters[webhook_name] == 1 else 0
            return {
                "webhook_name": webhook_name,
                "attempted_count": attempted,
                "delivered_count": attempted,
                "failed_count": 0,
                "dead_lettered_count": 0,
                "skipped_count": 0,
                "alert_emitted_count": 0,
                "delivered_event_ids": [f"{webhook_name}-event"] if attempted else [],
                "remaining_pending_count": remaining,
            }

        service = SimpleNamespace(
            list_webhooks=lambda: (
                SimpleNamespace(name="IM Notify"),
                SimpleNamespace(name="CI Callback"),
            ),
            _delivery_interval=300,
            _retry_delay=300,
            _max_retry_delay=3600,
            _dead_letter_threshold=5,
            _retry_alert_threshold=3,
            deliver_pending_events=_deliver,
        )

        payload = self._run_main_with_bundle(
            [
                "run-integration-outbox-worker",
                "--event-type",
                "admission.override_recorded",
                "--rounds",
                "2",
                "--stop-when-idle",
            ],
            SimpleNamespace(integration_outbox_service=service),
        )

        self.assertEqual(payload["worker"]["mode"], "delivery_worker_loop")
        self.assertEqual(payload["delivery"]["requested_rounds"], 2)
        self.assertEqual(payload["delivery"]["rounds_executed"], 2)
        self.assertEqual(payload["delivery"]["aggregate"]["attempted_count"], 2)
        self.assertEqual(len(payload["delivery"]["rounds"]), 2)
        self.assertEqual(len(delivery_calls), 4)

    def test_run_integration_outbox_worker_prefers_service_run_api(self) -> None:
        call_args: list[dict[str, object]] = []

        def _run_worker(**kwargs):
            call_args.append(dict(kwargs))
            return {
                "worker": {
                    "worker_name": "integration_outbox_worker",
                    "status": "idle",
                },
                "delivery_rounds": [
                    {
                        "webhook_name": "IM Notify",
                        "attempted_count": 1,
                        "delivered_count": 1,
                        "failed_count": 0,
                        "dead_lettered_count": 0,
                        "skipped_count": 0,
                        "deduplicated_count": 0,
                        "alert_emitted_count": 0,
                        "delivered_event_ids": ["evt_notify"],
                        "remaining_pending_count": 1,
                    },
                    {
                        "webhook_name": "CI Callback",
                        "attempted_count": 0,
                        "delivered_count": 0,
                        "failed_count": 0,
                        "dead_lettered_count": 0,
                        "skipped_count": 1,
                        "deduplicated_count": 0,
                        "alert_emitted_count": 0,
                        "delivered_event_ids": [],
                        "remaining_pending_count": 0,
                    },
                ],
            }

        service = SimpleNamespace(
            list_webhooks=lambda: (
                SimpleNamespace(name="IM Notify"),
                SimpleNamespace(name="CI Callback"),
            ),
            run_delivery_worker=_run_worker,
            _delivery_interval=300,
            _retry_delay=300,
            _max_retry_delay=3600,
            _dead_letter_threshold=5,
            _retry_alert_threshold=3,
        )
        payload = self._run_main_with_bundle(
            [
                "run-integration-outbox-worker",
                "--event-type",
                "admission.override_recorded",
                "--rounds",
                "2",
                "--stop-when-idle",
            ],
            SimpleNamespace(integration_outbox_service=service),
        )

        self.assertEqual(payload["delivery"]["requested_rounds"], 2)
        self.assertEqual(payload["delivery"]["rounds_executed"], 2)
        self.assertEqual(payload["delivery"]["aggregate"]["attempted_count"], 2)
        self.assertEqual(payload["delivery"]["aggregate"]["delivered_count"], 2)
        self.assertEqual(payload["worker"]["supports_run_delivery_worker"], True)

    def test_run_defect_sync_worker_outputs_worker_summary(self) -> None:
        worker_calls: list[dict[str, object]] = []
        bundle = SimpleNamespace(
            integration_outbox_service=SimpleNamespace(
                run_defect_sync_worker=lambda **kwargs: worker_calls.append(dict(kwargs)) or {
                    "delivery_rounds": [],
                    "rounds_executed": kwargs["max_rounds"] or 1,
                    "selected_webhooks": list(kwargs["webhook_names"]),
                },
                defect_sync_event_types=lambda: (
                    "issue.defect_create_requested",
                    "issue.defect_status_synced",
                ),
                list_webhooks=lambda: (SimpleNamespace(name="defect-sync"),),
                get_worker_status=lambda: SimpleNamespace(
                    worker_name="integration_outbox_worker",
                    status="idle",
                    worker_mode="defect_sync",
                    daemon_enabled=True,
                    daemon_pid=None,
                    daemon_heartbeat_at=None,
                    last_started_at=None,
                    last_finished_at=None,
                    last_success_at=None,
                    last_error="",
                    run_count=0,
                    delivered_count=0,
                    failed_count=0,
                    replay_count=0,
                    configured_webhooks=("defect-sync",),
                    configured_event_types=("issue.defect_create_requested",),
                    schedule_interval_seconds=300,
                    chain_name="defect_sync",
                    last_delivery_receipt_id="",
                    last_operator_receipt_id="",
                    last_run_summary={},
                ),
                _delivery_interval=300,
                _retry_delay=300,
                _max_retry_delay=3600,
                _dead_letter_threshold=5,
                _retry_alert_threshold=3,
            )
        )

        payload = self._run_main_with_bundle(
            [
                "run-defect-sync-worker",
                "--webhook-name",
                "defect-sync",
                "--max-rounds",
                "1",
                "--daemon",
            ],
            bundle,
        )

        self.assertEqual(payload["mode"], "defect_sync_worker")
        self.assertEqual(payload["worker"]["mode"], "defect_sync_daemon")
        self.assertEqual(payload["delivery"]["rounds_executed"], 1)
        self.assertEqual(worker_calls[0]["webhook_names"], ("defect-sync",))

    def test_run_release_sync_worker_outputs_worker_summary(self) -> None:
        worker_calls: list[dict[str, object]] = []
        bundle = SimpleNamespace(
            integration_outbox_service=SimpleNamespace(
                run_release_sync_worker=lambda **kwargs: worker_calls.append(dict(kwargs)) or {
                    "delivery_rounds": [],
                    "rounds_executed": kwargs["max_rounds"] or 1,
                    "selected_webhooks": list(kwargs["webhook_names"]),
                },
                release_submission_event_types=lambda: (
                    "release_submission.created",
                    "release_submission.admission_synced",
                ),
                list_webhooks=lambda: (SimpleNamespace(name="release-sync"),),
                get_worker_status=lambda: SimpleNamespace(
                    worker_name="integration_outbox_worker",
                    status="idle",
                    worker_mode="release_submission",
                    daemon_enabled=True,
                    daemon_pid=None,
                    daemon_heartbeat_at=None,
                    last_started_at=None,
                    last_finished_at=None,
                    last_success_at=None,
                    last_error="",
                    run_count=0,
                    delivered_count=0,
                    failed_count=0,
                    replay_count=0,
                    configured_webhooks=("release-sync",),
                    configured_event_types=("release_submission.created",),
                    schedule_interval_seconds=300,
                    chain_name="release_submission",
                    last_delivery_receipt_id="",
                    last_operator_receipt_id="",
                    last_run_summary={},
                ),
                _delivery_interval=300,
                _retry_delay=300,
                _max_retry_delay=3600,
                _dead_letter_threshold=5,
                _retry_alert_threshold=3,
            )
        )

        payload = self._run_main_with_bundle(
            [
                "run-release-sync-worker",
                "--webhook-name",
                "release-sync",
                "--max-rounds",
                "1",
                "--daemon",
            ],
            bundle,
        )

        self.assertEqual(payload["mode"], "release_submission_worker")
        self.assertEqual(payload["worker"]["mode"], "release_submission_daemon")
        self.assertEqual(payload["delivery"]["rounds_executed"], 1)
        self.assertEqual(worker_calls[0]["webhook_names"], ("release-sync",))

    def test_run_im_notify_worker_uses_service_im_worker_api(self) -> None:
        call_args: list[dict[str, object]] = []

        def _run_im_worker(**kwargs):
            call_args.append(dict(kwargs))
            return {
                "mode": "daemon",
                "rounds_executed": 1,
                "selected_webhooks": ["Team IM"],
                "delivery_rounds": [
                    {
                        "webhook_name": "Team IM",
                        "attempted_count": 1,
                        "delivered_count": 1,
                        "failed_count": 0,
                        "dead_lettered_count": 0,
                        "skipped_count": 0,
                        "deduplicated_count": 0,
                        "alert_emitted_count": 0,
                        "delivered_event_ids": ["evt_im_1"],
                        "remaining_pending_count": 0,
                    }
                ],
            }

        service = SimpleNamespace(
            list_webhooks=lambda: (SimpleNamespace(name="Team IM"),),
            run_im_notification_worker=_run_im_worker,
            im_notification_event_types=lambda: ("issue.assigned", "admission_case.updated"),
            _delivery_interval=300,
            _retry_delay=300,
            _max_retry_delay=3600,
            _dead_letter_threshold=5,
            _retry_alert_threshold=3,
        )

        payload = self._run_main_with_bundle(
            [
                "run-im-notify-worker",
                "--webhook-name",
                "Team IM",
                "--daemon",
                "--max-rounds",
                "1",
            ],
            SimpleNamespace(integration_outbox_service=service),
        )

        self.assertEqual(payload["mode"], "im_notify_worker")
        self.assertEqual(payload["worker"]["mode"], "im_notification_daemon")
        self.assertIn("register_im_webhook", payload["worker"]["worker_commands"])
        self.assertEqual(call_args[0]["webhook_names"], ("Team IM",))
        self.assertTrue(call_args[0]["daemon"])
        self.assertEqual(len(call_args), 1)

    def test_run_feishu_notify_worker_uses_service_feishu_worker_api(self) -> None:
        call_args: list[dict[str, object]] = []

        def _run_feishu_worker(**kwargs):
            call_args.append(dict(kwargs))
            return {
                "mode": "daemon",
                "rounds_executed": 1,
                "selected_webhooks": ["Team Feishu"],
                "delivery_rounds": [
                    {
                        "webhook_name": "Team Feishu",
                        "attempted_count": 1,
                        "delivered_count": 1,
                        "failed_count": 0,
                        "dead_lettered_count": 0,
                        "skipped_count": 0,
                        "deduplicated_count": 0,
                        "alert_emitted_count": 0,
                        "delivered_event_ids": ["evt_feishu_1"],
                        "remaining_pending_count": 0,
                    }
                ],
            }

        service = SimpleNamespace(
            list_webhooks=lambda: (SimpleNamespace(name="Team Feishu"),),
            run_feishu_notify_worker=_run_feishu_worker,
            feishu_bot_event_types=lambda: ("issue.assigned", "admission_case.updated"),
            _delivery_interval=300,
            _retry_delay=300,
            _max_retry_delay=3600,
            _dead_letter_threshold=5,
            _retry_alert_threshold=3,
        )

        payload = self._run_main_with_bundle(
            [
                "run-feishu-notify-worker",
                "--webhook-name",
                "Team Feishu",
                "--daemon",
                "--max-rounds",
                "1",
            ],
            SimpleNamespace(integration_outbox_service=service),
        )

        self.assertEqual(payload["mode"], "feishu_notify_worker")
        self.assertEqual(payload["worker"]["mode"], "feishu_notify_daemon")
        self.assertIn("register_feishu_webhook", payload["worker"]["worker_commands"])
        self.assertEqual(payload["acceptance_summary"]["total_event_count"], 0)
        self.assertEqual(payload["acceptance_summary"]["deduplicated_count"], 0)
        self.assertEqual(call_args[0]["webhook_names"], ("Team Feishu",))
        self.assertTrue(call_args[0]["daemon"])
        self.assertEqual(len(call_args), 1)

    def test_show_im_acceptance_summary_outputs_feishu_counters_and_checklist(self) -> None:
        started_at = datetime(2025, 7, 25, 8, 0, 0)
        events = (
            SimpleNamespace(
                event_id="evt_feishu_1",
                event_type="issue.assigned",
                created_at=started_at,
                last_attempt_at=started_at + timedelta(hours=2, minutes=5),
                delivered_at=started_at + timedelta(hours=2, minutes=5),
                delivery_status="delivered",
                attempt_count=1,
                consumer_receipts=(
                    SimpleNamespace(
                        webhook_name="Team Feishu",
                        idempotency_key="asl.outbox.idempotency.v1:evt_feishu_1",
                        received_at=started_at + timedelta(hours=2, minutes=5),
                    ),
                ),
            ),
            SimpleNamespace(
                event_id="evt_feishu_2",
                event_type="admission_case.updated",
                created_at=started_at + timedelta(hours=1),
                last_attempt_at=started_at + timedelta(hours=2),
                delivered_at=None,
                delivery_status="retry_pending",
                attempt_count=3,
                consumer_receipts=(),
            ),
            SimpleNamespace(
                event_id="evt_other",
                event_type="release_submission.created",
                created_at=started_at,
                last_attempt_at=started_at,
                delivered_at=started_at,
                delivery_status="delivered",
                attempt_count=1,
                consumer_receipts=(),
            ),
        )
        service = SimpleNamespace(
            list_webhooks=lambda: (
                SimpleNamespace(name="Team Feishu", delivery_channel="feishu_bot"),
                SimpleNamespace(name="Team IM", delivery_channel="im_notify"),
            ),
            list_events=lambda limit=0: events[:limit] if limit > 0 else events,
            feishu_bot_event_types=lambda: ("issue.assigned", "admission_case.updated"),
            im_notification_event_types=lambda: ("issue.assigned",),
        )

        payload = self._run_main_with_bundle(
            [
                "show-im-acceptance-summary",
                "--channel",
                "feishu_bot",
                "--webhook-name",
                "Team Feishu",
            ],
            SimpleNamespace(integration_outbox_service=service),
        )

        summary = payload["acceptance_summary"]
        self.assertEqual(summary["channel"], "feishu_bot")
        self.assertEqual(summary["webhook_names"], ["Team Feishu"])
        self.assertEqual(summary["total_event_count"], 2)
        self.assertEqual(summary["delivered_count"], 1)
        self.assertEqual(summary["failed_count"], 1)
        self.assertEqual(summary["retry_count"], 2)
        self.assertEqual(summary["dead_letter_count"], 0)
        self.assertEqual(summary["consumer_receipt_count"], 1)
        self.assertEqual(summary["deduplicated_count"], 0)
        self.assertEqual(summary["noise_check"]["placeholder"], True)
        self.assertEqual(summary["acceptance_status"]["window"]["window_seconds"], 7500)
        self.assertEqual(summary["acceptance_status"]["two_hour"]["machine_status"], "not_ready")
        self.assertIn("存在 retry_pending", "".join(summary["acceptance_status"]["two_hour"]["blocking_reasons"]))
        self.assertEqual(summary["acceptance_status"]["twenty_four_hour"]["remaining_seconds"], 78900)
        self.assertIn("two_hour", summary["checklist"])

    _run_main_with_bundle = staticmethod(run_main_with_bundle)


if __name__ == "__main__":
    unittest.main()
