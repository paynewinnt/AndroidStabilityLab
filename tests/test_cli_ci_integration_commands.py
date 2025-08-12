from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime
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


class CLICIIntegrationCommandsTest(unittest.TestCase):
    def test_run_ci_admission_sync_worker_uses_daemon_api(self) -> None:
        call_args: list[dict[str, object]] = []

        def _run_daemon(**kwargs):
            call_args.append(dict(kwargs))
            return {
                "mode": "daemon",
                "selected_webhooks": ["CI Callback"],
                "event_types": ["admission_case.updated"],
                "rounds_executed": 1,
                "stopped_when_idle": True,
                "aggregate": {"attempted_count": 1, "delivered_count": 1, "remaining_pending_count": 0},
                "rounds": [],
                "worker": {"worker_name": "integration_outbox_worker", "worker_mode": "daemon", "chain_name": "ci_admission_callback"},
            }

        service = SimpleNamespace(
            list_webhooks=lambda: (SimpleNamespace(name="CI Callback"),),
            run_delivery_daemon=_run_daemon,
            _delivery_interval=300,
            _retry_delay=300,
            _max_retry_delay=3600,
            _dead_letter_threshold=5,
            _retry_alert_threshold=3,
        )
        payload = self._run_main_with_bundle(
            [
                "run-ci-admission-sync-worker",
                "--webhook-name",
                "CI Callback",
                "--interval-seconds",
                "60",
                "--max-rounds",
                "2",
                "--stop-when-idle",
            ],
            SimpleNamespace(integration_outbox_service=service),
        )

        self.assertEqual(payload["mode"], "ci_admission_sync_worker")
        self.assertEqual(payload["worker"]["mode"], "ci_admission_callback_daemon")
        self.assertEqual(call_args[0]["event_types"], ("admission_case.updated",))
        self.assertEqual(call_args[0]["chain_name"], "ci_admission_callback")

    def test_replay_integration_dead_letters_execute_uses_replay_api(self) -> None:
        events = [
            SimpleNamespace(
                event_id="outbox_event_dead_1",
                event_type="admission.override_recorded",
                target_type="admission",
                target_id="baseline_1",
                idempotency_key="idem_outbox_event_dead_1",
                delivery_status="dead_letter",
                attempt_count=3,
                last_response_code=503,
                last_error="gateway timeout",
                next_retry_at=None,
                dead_lettered_at=datetime(2025, 7, 23, 11, 0, 0),
                signature="sha256=deadbeef",
            )
        ]
        replay_calls: list[dict[str, object]] = []
        service = SimpleNamespace(
            list_events=lambda limit=0: events,
            list_webhooks=lambda: (SimpleNamespace(name="CI Callback"),),
            replay_dead_lettered_events=lambda **kwargs: (
                replay_calls.append(dict(kwargs))
                or {
                    "webhook_name": kwargs["webhook_name"],
                    "replayed_count": 1,
                    "replayed_event_ids": ["outbox_event_dead_1"],
                    "remaining_dead_letter_count": 0,
                }
            ),
        )
        payload = self._run_main_with_bundle(
            [
                "replay-integration-dead-letters",
                "--event-id",
                "outbox_event_dead_1",
                "--execute",
                "--replayed-by",
                "operator",
            ],
            SimpleNamespace(integration_outbox_service=service),
        )

        self.assertEqual(payload["dead_letter_replay"]["mode"], "execute")
        self.assertEqual(payload["dead_letter_replay"]["replayed_count"], 1)
        self.assertEqual(payload["dead_letter_replay"]["replayed_event_ids"], ["outbox_event_dead_1"])
        self.assertEqual(payload["dead_letter_replay"]["receipts"][0]["replayed_by"], "operator")
        self.assertEqual(payload["dead_letter_replay"]["receipts"][0]["idempotency_key"], "idem_outbox_event_dead_1")
        self.assertEqual(len(replay_calls), 1)
        self.assertEqual(replay_calls[0]["webhook_name"], "CI Callback")

    def test_replay_integration_dead_letters_previews_matching_events(self) -> None:
        dead_letter = SimpleNamespace(
            event_id="outbox_event_dead_1",
            event_type="admission.override_recorded",
            target_type="admission",
            target_id="baseline_1",
            delivery_status="dead_letter",
            attempt_count=5,
            last_response_code=503,
            last_error="gateway timeout",
            next_retry_at=None,
            dead_lettered_at=datetime(2025, 7, 23, 11, 0, 0),
            signature="sha256=deadbeef",
        )
        service = SimpleNamespace(
            list_events=lambda limit=0: [dead_letter],
            list_webhooks=lambda: (),
            _delivery_interval=300,
            _retry_delay=300,
            _max_retry_delay=3600,
            _dead_letter_threshold=5,
            _retry_alert_threshold=3,
        )

        payload = self._run_main_with_bundle(
            [
                "replay-integration-dead-letters",
                "--event-type",
                "admission.override_recorded",
            ],
            SimpleNamespace(integration_outbox_service=service),
        )

        self.assertEqual(payload["dead_letter_replay"]["mode"], "preview")
        self.assertEqual(payload["dead_letter_replay"]["matched_count"], 1)
        self.assertEqual(
            payload["dead_letter_replay"]["events"][0]["idempotency_key"],
            "asl.outbox.idempotency.v1:outbox_event_dead_1",
        )

    def test_replay_integration_dead_letters_execute_requeues_selected_events(self) -> None:
        events_registry = [
            {
                "event_id": "outbox_event_dead_1",
                "event_type": "admission.override_recorded",
                "target_type": "admission",
                "target_id": "baseline_1",
                "delivery_status": "dead_letter",
                "attempt_count": 5,
                "last_error": "gateway timeout",
                "signature": "sha256=deadbeef",
                "alert_status": "emitted",
            }
        ]
        saved_payloads: list[list[dict[str, object]]] = []
        service = SimpleNamespace(
            list_events=lambda limit=0: [
                SimpleNamespace(
                    event_id="outbox_event_dead_1",
                    event_type="admission.override_recorded",
                    target_type="admission",
                    target_id="baseline_1",
                    delivery_status="dead_letter",
                    attempt_count=5,
                    last_response_code=503,
                    last_error="gateway timeout",
                    next_retry_at=None,
                    dead_lettered_at=datetime(2025, 7, 23, 11, 0, 0),
                    signature="sha256=deadbeef",
                )
            ],
            list_webhooks=lambda: (),
            _delivery_interval=300,
            _retry_delay=300,
            _max_retry_delay=3600,
            _dead_letter_threshold=5,
            _retry_alert_threshold=3,
            _events_path="runtime/integration_outbox/events.json",
            _load_event_registry=lambda: list(events_registry),
            _save_registry=lambda path, payload: saved_payloads.append(list(payload)),
        )

        payload = self._run_main_with_bundle(
            [
                "replay-integration-dead-letters",
                "--event-id",
                "outbox_event_dead_1",
                "--execute",
                "--replayed-by",
                "operator",
            ],
            SimpleNamespace(integration_outbox_service=service),
        )

        self.assertEqual(payload["dead_letter_replay"]["mode"], "execute")
        self.assertEqual(payload["dead_letter_replay"]["replayed_count"], 1)
        self.assertEqual(payload["dead_letter_replay"]["receipts"][0]["replayed_by"], "operator")
        self.assertEqual(saved_payloads[-1][0]["delivery_status"], "pending")
        self.assertEqual(saved_payloads[-1][0]["attempt_count"], 0)

    def test_sync_ci_admission_decisions_dry_run_outputs_query_payload(self) -> None:
        service_event = SimpleNamespace(
            event_id="outbox_event_1",
            event_type="admission_case.updated",
            target_type="admission_case",
            target_id="baseline_1",
            created_at=datetime(2025, 7, 23, 10, 30, 0),
            created_by="admin",
            session_source="query:cli",
            audit_source={"request_path": "/api/admission/override"},
            payload={
                "case_id": "admission_case:baseline_1:review_1",
                "case_revision": 3,
                "status": "approved",
                "assignee": {"actor_id": "developer", "display_name": "Developer"},
                "final_reviewer": {"actor_id": "tester", "display_name": "Tester"},
                "final_decision": "pass",
                "final_review_opinion": "Risk cleared",
                "case_trace_summary": {"top_issue_count": 1},
                "source_refs": {"report": {"report_id": "review_1"}},
            },
            delivery_status="pending",
            attempt_count=0,
        )
        bundle = SimpleNamespace(
            integration_outbox_service=SimpleNamespace(
                list_events=lambda limit=0: [service_event],
            )
        )

        payload = self._run_main_with_bundle(
            [
                "sync-ci-admission-decisions",
                "--webhook-name",
                "CI Callback",
                "--event-type",
                "admission_case.updated",
                "--query-limit",
                "50",
                "--limit",
                "1",
                "--dry-run",
            ],
            bundle,
        )

        self.assertEqual(payload["mode"], "ci_admission_decisions_query")
        self.assertEqual(payload["query"]["pending_count"], 1)
        self.assertEqual(payload["query"]["ci_payloads"][0]["event_id"], "outbox_event_1")
        self.assertEqual(payload["query"]["ci_payloads"][0]["baseline_key"], "baseline_1")
        self.assertEqual(payload["query"]["ci_payloads"][0]["case_id"], "admission_case:baseline_1:review_1")
        self.assertEqual(payload["query"]["ci_payloads"][0]["final_decision"], "pass")

    def test_sync_ci_admission_decisions_auto_registers_webhook_and_delivers(self) -> None:
        events = [
            SimpleNamespace(
                event_id="outbox_event_1",
                event_type="admission_case.updated",
                target_type="admission_case",
                target_id="baseline_1",
                created_at=datetime(2025, 7, 23, 10, 30, 0),
                created_by="admin",
                session_source="query:cli",
                audit_source={},
                payload={
                    "case_id": "admission_case:baseline_1:review_1",
                    "case_revision": 4,
                    "status": "rejected",
                    "assignee": {"actor_id": "developer", "display_name": "Developer"},
                    "final_reviewer": {"actor_id": "tester", "display_name": "Tester"},
                    "final_decision": "fail",
                    "final_review_opinion": "关键回归",
                    "case_trace_summary": {"top_issue_count": 2},
                    "source_refs": {"report": {"report_id": "review_1"}},
                },
                delivery_status="pending",
                attempt_count=0,
            )
        ]
        register_calls: list[dict[str, object]] = []
        delivery_calls: list[dict[str, object]] = []

        service = SimpleNamespace(
            list_events=lambda limit=0: events,
            list_webhooks=lambda: [],
            _delivery_interval=300,
            _retry_delay=300,
            _max_retry_delay=3600,
            _dead_letter_threshold=5,
            _retry_alert_threshold=3,
            register_webhook=lambda **kwargs: (
                register_calls.append(dict(kwargs))
                or SimpleNamespace(
                    webhook_id="webhook_1",
                    name=kwargs["name"],
                    url=kwargs["url"],
                    subscribed_event_types=tuple(kwargs["subscribed_event_types"]),
                    created_by=kwargs["created_by"],
                    created_at=None,
                    secret_hint="",
                )
            ),
            deliver_pending_events=lambda **kwargs: delivery_calls.append(dict(kwargs)) or {
                "webhook_name": kwargs["webhook_name"],
                "attempted_count": 1,
                "delivered_count": 1,
                "failed_count": 0,
                "skipped_count": 0,
                "delivered_event_ids": ["outbox_event_1"],
                "remaining_pending_count": 0,
            },
        )
        payload = self._run_main_with_bundle(
            [
                "sync-ci-admission-decisions",
                "--webhook-name",
                "CI Callback",
                "--ci-endpoint",
                "https://ci.example.invalid/admission/callback",
                "--limit",
                "2",
            ],
            SimpleNamespace(integration_outbox_service=service),
        )

        self.assertEqual(payload["mode"], "ci_admission_decisions_sync")
        self.assertEqual(payload["worker"]["mode"], "ci_callback_sync")
        self.assertEqual(payload["query"]["pending_count"], 1)
        self.assertEqual(len(register_calls), 1)
        self.assertEqual(register_calls[0]["name"], "CI Callback")
        self.assertEqual(register_calls[0]["url"], "https://ci.example.invalid/admission/callback")
        self.assertEqual(payload["delivery"]["webhook_name"], "CI Callback")
        self.assertEqual(payload["delivery"]["receipt_keys"], ["asl.outbox.receipt.v1:CI Callback:outbox_event_1"])
        self.assertEqual(delivery_calls[0]["event_types"], ("admission_case.updated",))
        self.assertEqual(delivery_calls[0]["limit"], 2)

    _run_main_with_bundle = staticmethod(run_main_with_bundle)


if __name__ == "__main__":
    unittest.main()
