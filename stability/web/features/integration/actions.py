from __future__ import annotations

from stability.application import (
    ChannelWorkerCommand,
    CiAdmissionSyncCommand,
    DeliverOutboxCommand,
    ReplayDeadLettersCommand,
    RunOutboxWorkerCommand,
    deliver_integration_outbox,
    replay_integration_dead_letters,
    run_defect_sync_worker,
    run_feishu_notify_worker,
    run_im_notification_worker,
    run_integration_outbox_worker,
    run_release_sync_worker,
    sync_ci_admission_decisions,
)

from typing import Any, Mapping


class IntegrationActionsMixin:
    def _handle_register_integration_webhook(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "integration_outbox_service", None)
        if service is None or not hasattr(service, "register_webhook"):
            raise ValueError("Integration outbox service is unavailable.")
        actor = dict(request_context.get("current_actor", {}) or {})
        webhook = service.register_webhook(
            name=self._required_form_value(dict(payload), "name"),
            url=self._required_form_value(dict(payload), "url"),
            subscribed_event_types=tuple(self._expand_form_values(payload, "event_types")),
            created_by=str(actor.get("actor_id", "") or "web"),
            secret_hint=self._form_value(dict(payload), "secret_hint"),
            signing_secret=self._form_value(dict(payload), "signing_secret"),
            signature_key_id=self._form_value(dict(payload), "signature_key_id") or "v1",
            accepted_signature_key_ids=tuple(self._expand_form_values(payload, "accepted_signature_key_ids")),
            failure_policy=self._form_value(dict(payload), "failure_policy") or "retryable_http",
            delivery_channel=self._form_value(dict(payload), "delivery_channel") or "generic",
        )
        return {
            "storage_mode": "persistent",
            "webhook": self._integration_webhook_result_payload(webhook),
        }

    def _handle_register_im_webhook(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "integration_outbox_service", None)
        if service is None:
            raise ValueError("Integration outbox service is unavailable.")
        actor = dict(request_context.get("current_actor", {}) or {})
        event_types = tuple(self._expand_form_values(payload, "event_types"))
        if hasattr(service, "register_im_webhook"):
            webhook = service.register_im_webhook(
                name=self._required_form_value(dict(payload), "name"),
                url=self._required_form_value(dict(payload), "url"),
                created_by=str(actor.get("actor_id", "") or "web"),
                secret_hint=self._form_value(dict(payload), "secret_hint"),
                signing_secret=self._form_value(dict(payload), "signing_secret"),
                signature_key_id=self._form_value(dict(payload), "signature_key_id") or "v1",
                accepted_signature_key_ids=tuple(self._expand_form_values(payload, "accepted_signature_key_ids")),
                failure_policy=self._form_value(dict(payload), "failure_policy") or "retryable_http",
                subscribed_event_types=event_types,
            )
        elif hasattr(service, "register_webhook"):
            fallback_event_types = event_types
            if not fallback_event_types and hasattr(service, "im_notification_event_types"):
                fallback_event_types = tuple(service.im_notification_event_types())
            webhook = service.register_webhook(
                name=self._required_form_value(dict(payload), "name"),
                url=self._required_form_value(dict(payload), "url"),
                subscribed_event_types=fallback_event_types,
                created_by=str(actor.get("actor_id", "") or "web"),
                secret_hint=self._form_value(dict(payload), "secret_hint"),
                signing_secret=self._form_value(dict(payload), "signing_secret"),
                signature_key_id=self._form_value(dict(payload), "signature_key_id") or "v1",
                accepted_signature_key_ids=tuple(self._expand_form_values(payload, "accepted_signature_key_ids")),
                failure_policy=self._form_value(dict(payload), "failure_policy") or "retryable_http",
                delivery_channel="im_notify",
            )
        else:
            raise ValueError("Integration outbox service webhook APIs are unavailable.")
        return {
            "storage_mode": "persistent",
            "webhook": {
                **self._integration_webhook_result_payload(webhook, default_channel="im_notify"),
                "delivery_contract_version": "asl.im_notify.v1",
            },
        }

    def _handle_register_defect_webhook(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "integration_outbox_service", None)
        if service is None:
            raise ValueError("Integration outbox service is unavailable.")
        actor = dict(request_context.get("current_actor", {}) or {})
        event_types = tuple(self._expand_form_values(payload, "event_types"))
        if hasattr(service, "register_defect_webhook"):
            webhook = service.register_defect_webhook(
                name=self._required_form_value(dict(payload), "name"),
                url=self._required_form_value(dict(payload), "url"),
                created_by=str(actor.get("actor_id", "") or "web"),
                secret_hint=self._form_value(dict(payload), "secret_hint"),
                signing_secret=self._form_value(dict(payload), "signing_secret"),
                signature_key_id=self._form_value(dict(payload), "signature_key_id") or "v1",
                accepted_signature_key_ids=tuple(self._expand_form_values(payload, "accepted_signature_key_ids")),
                failure_policy=self._form_value(dict(payload), "failure_policy") or "retryable_http",
                subscribed_event_types=event_types,
            )
        elif hasattr(service, "register_webhook"):
            fallback_event_types = event_types
            if not fallback_event_types and hasattr(service, "defect_sync_event_types"):
                fallback_event_types = tuple(service.defect_sync_event_types())
            webhook = service.register_webhook(
                name=self._required_form_value(dict(payload), "name"),
                url=self._required_form_value(dict(payload), "url"),
                subscribed_event_types=fallback_event_types,
                created_by=str(actor.get("actor_id", "") or "web"),
                secret_hint=self._form_value(dict(payload), "secret_hint"),
                signing_secret=self._form_value(dict(payload), "signing_secret"),
                signature_key_id=self._form_value(dict(payload), "signature_key_id") or "v1",
                accepted_signature_key_ids=tuple(self._expand_form_values(payload, "accepted_signature_key_ids")),
                failure_policy=self._form_value(dict(payload), "failure_policy") or "retryable_http",
                delivery_channel="defect_sync",
            )
        else:
            raise ValueError("Integration outbox service webhook APIs are unavailable.")
        return {
            "storage_mode": "persistent",
            "webhook": {
                **self._integration_webhook_result_payload(webhook, default_channel="defect_sync"),
                "delivery_contract_version": "asl.defect_sync.v1",
            },
        }

    def _handle_create_release_submission(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "release_submission_service", None)
        if service is None or not hasattr(service, "create_submission"):
            raise ValueError("Release submission service is unavailable.")
        actor = dict(request_context.get("current_actor", {}) or {})
        device_sync = self._maybe_sync_release_submission_devices(payload)
        record = service.create_submission(
            source_platform=self._required_form_value(dict(payload), "source_platform"),
            source_request_id=self._required_form_value(dict(payload), "source_request_id"),
            package_name=self._required_form_value(dict(payload), "package_name"),
            version_name=self._form_value(dict(payload), "version_name"),
            version_code=self._form_value(dict(payload), "version_code"),
            build_id=self._form_value(dict(payload), "build_id"),
            release_channel=self._form_value(dict(payload), "release_channel"),
            owner_team=self._form_value(dict(payload), "owner_team"),
            submission_title=self._form_value(dict(payload), "submission_title"),
            template_type=self._form_value(dict(payload), "template_type"),
            selected_device_ids=tuple(self._expand_form_values(payload, "devices") or self._expand_form_values(payload, "device")),
            enabled_metrics=tuple(self._expand_form_values(payload, "metrics")),
            sampling_interval_seconds=max(self._form_int(payload, "sampling_interval", default=5), 0),
            monitoring_backend=self._form_value(dict(payload), "monitoring_backend"),
            execute_immediately=self._form_bool(payload, "execute_immediately", default=True),
            max_concurrency=max(self._form_int(payload, "max_concurrency", default=1), 1),
            retry_count=max(self._form_int(payload, "retry_count", default=0), 0),
            created_by=str(actor.get("actor_id", "") or "web"),
            metadata=self._json_form_object(payload, "metadata"),
            task_params=self._json_form_object(payload, "task_params"),
        )
        result = {
            "storage_mode": "persistent",
            "release_submission": self._release_submission_payload(record),
        }
        if device_sync is not None:
            result["device_sync"] = device_sync
        return result

    def _handle_sync_release_submission_admission(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "release_submission_service", None)
        if service is None or not hasattr(service, "sync_admission_result"):
            raise ValueError("Release submission service is unavailable.")
        actor = dict(request_context.get("current_actor", {}) or {})
        record = service.sync_admission_result(
            submission_id=self._required_form_value(dict(payload), "submission_id"),
            baseline_key=self._required_form_value(dict(payload), "baseline_key"),
            synced_by=str(actor.get("actor_id", "") or "web"),
        )
        return {
            "storage_mode": "persistent",
            "release_submission": self._release_submission_payload(record),
        }

    def _handle_register_release_webhook(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "integration_outbox_service", None)
        if service is None:
            raise ValueError("Integration outbox service is unavailable.")
        actor = dict(request_context.get("current_actor", {}) or {})
        event_types = tuple(self._expand_form_values(payload, "event_types"))
        if hasattr(service, "register_release_webhook"):
            webhook = service.register_release_webhook(
                name=self._required_form_value(dict(payload), "name"),
                url=self._required_form_value(dict(payload), "url"),
                created_by=str(actor.get("actor_id", "") or "web"),
                secret_hint=self._form_value(dict(payload), "secret_hint"),
                signing_secret=self._form_value(dict(payload), "signing_secret"),
                signature_key_id=self._form_value(dict(payload), "signature_key_id") or "v1",
                accepted_signature_key_ids=tuple(self._expand_form_values(payload, "accepted_signature_key_ids")),
                failure_policy=self._form_value(dict(payload), "failure_policy") or "retryable_http",
                subscribed_event_types=event_types,
            )
        elif hasattr(service, "register_webhook"):
            fallback_event_types = event_types
            if not fallback_event_types and hasattr(service, "release_submission_event_types"):
                fallback_event_types = tuple(service.release_submission_event_types())
            webhook = service.register_webhook(
                name=self._required_form_value(dict(payload), "name"),
                url=self._required_form_value(dict(payload), "url"),
                subscribed_event_types=fallback_event_types,
                created_by=str(actor.get("actor_id", "") or "web"),
                secret_hint=self._form_value(dict(payload), "secret_hint"),
                signing_secret=self._form_value(dict(payload), "signing_secret"),
                signature_key_id=self._form_value(dict(payload), "signature_key_id") or "v1",
                accepted_signature_key_ids=tuple(self._expand_form_values(payload, "accepted_signature_key_ids")),
                failure_policy=self._form_value(dict(payload), "failure_policy") or "retryable_http",
                delivery_channel="release_submission",
            )
        else:
            raise ValueError("Integration outbox service webhook APIs are unavailable.")
        return {
            "storage_mode": "persistent",
            "webhook": {
                **self._integration_webhook_result_payload(webhook, default_channel="release_submission"),
                "delivery_contract_version": "asl.release_submission.v1",
            },
        }

    def _handle_deliver_integration_outbox(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        return deliver_integration_outbox(
            getattr(self._bundle, "integration_outbox_service", None),
            DeliverOutboxCommand(
                webhook_name=self._required_form_value(dict(payload), "webhook_name"),
                event_types=tuple(self._expand_form_values(payload, "event_types")),
                limit=max(self._form_int(payload, "limit", default=20), 1),
            ),
        )

    def _handle_run_integration_worker(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        webhook_names = tuple(self._expand_form_values(payload, "webhook_names") or self._expand_form_values(payload, "webhook_name"))
        event_types = tuple(self._expand_form_values(payload, "event_types"))
        return run_integration_outbox_worker(
            getattr(self._bundle, "integration_outbox_service", None),
            RunOutboxWorkerCommand(
                webhook_names=webhook_names,
                event_types=event_types,
                limit_per_webhook=max(self._form_int(payload, "limit_per_webhook", default=20), 1),
                rounds=max(self._form_int(payload, "rounds", default=1), 1),
                interval_seconds=max(self._form_int(payload, "interval_seconds", default=0), 0),
                stop_when_idle=self._form_bool(payload, "stop_when_idle", default=False),
                daemon=self._form_bool(payload, "daemon", default=False),
                max_runtime_seconds=max(self._form_int(payload, "max_runtime_seconds", default=0), 0),
                chain_name="integration_outbox",
                worker_mode="delivery_worker_loop",
            ),
        )

    def _handle_run_ci_sync_worker(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        webhook_names = tuple(self._expand_form_values(payload, "webhook_names") or self._expand_form_values(payload, "webhook_name"))
        result = run_integration_outbox_worker(
            getattr(self._bundle, "integration_outbox_service", None),
            RunOutboxWorkerCommand(
                webhook_names=webhook_names,
                event_types=("admission_case.updated",),
                limit_per_webhook=max(self._form_int(payload, "limit_per_webhook", default=20), 1),
                rounds=max(self._form_int(payload, "max_rounds", default=1), 1),
                interval_seconds=max(self._form_int(payload, "interval_seconds", default=300), 0),
                stop_when_idle=self._form_bool(payload, "stop_when_idle", default=False),
                daemon=True,
                max_runtime_seconds=max(self._form_int(payload, "max_runtime_seconds", default=0), 0),
                chain_name="ci_admission_callback",
                worker_mode="ci_admission_callback_daemon",
            ),
        )
        result["mode"] = "ci_admission_sync_worker"
        return result

    def _handle_run_im_notify_worker(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        webhook_names = tuple(self._expand_form_values(payload, "webhook_names") or self._expand_form_values(payload, "webhook_name"))
        daemon = self._form_bool(payload, "daemon", default=True)
        channel = self._form_value(dict(payload), "channel") or "im_notify"
        command = ChannelWorkerCommand(
            webhook_names=webhook_names,
            limit_per_webhook=max(self._form_int(payload, "limit_per_webhook", default=20), 1),
            interval_seconds=max(self._form_int(payload, "interval_seconds", default=300), 0),
            max_rounds=max(self._form_int(payload, "max_rounds", default=1), 0),
            max_runtime_seconds=max(self._form_int(payload, "max_runtime_seconds", default=0), 0),
            stop_when_idle=self._form_bool(payload, "stop_when_idle", default=False),
            daemon=daemon,
        )
        if channel == "feishu_bot":
            return run_feishu_notify_worker(getattr(self._bundle, "integration_outbox_service", None), command)
        return run_im_notification_worker(getattr(self._bundle, "integration_outbox_service", None), command)

    def _handle_run_defect_sync_worker(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        webhook_names = tuple(self._expand_form_values(payload, "webhook_names") or self._expand_form_values(payload, "webhook_name"))
        daemon = self._form_bool(payload, "daemon", default=True)
        return run_defect_sync_worker(
            getattr(self._bundle, "integration_outbox_service", None),
            ChannelWorkerCommand(
                webhook_names=webhook_names,
                limit_per_webhook=max(self._form_int(payload, "limit_per_webhook", default=20), 1),
                interval_seconds=max(self._form_int(payload, "interval_seconds", default=300), 0),
                max_rounds=max(self._form_int(payload, "max_rounds", default=1), 0),
                max_runtime_seconds=max(self._form_int(payload, "max_runtime_seconds", default=0), 0),
                stop_when_idle=self._form_bool(payload, "stop_when_idle", default=False),
                daemon=daemon,
            ),
        )

    def _handle_run_release_sync_worker(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        del request_context
        webhook_names = tuple(self._expand_form_values(payload, "webhook_names") or self._expand_form_values(payload, "webhook_name"))
        daemon = self._form_bool(payload, "daemon", default=True)
        return run_release_sync_worker(
            getattr(self._bundle, "integration_outbox_service", None),
            ChannelWorkerCommand(
                webhook_names=webhook_names,
                limit_per_webhook=max(self._form_int(payload, "limit_per_webhook", default=20), 1),
                interval_seconds=max(self._form_int(payload, "interval_seconds", default=300), 0),
                max_rounds=max(self._form_int(payload, "max_rounds", default=1), 0),
                max_runtime_seconds=max(self._form_int(payload, "max_runtime_seconds", default=0), 0),
                stop_when_idle=self._form_bool(payload, "stop_when_idle", default=False),
                daemon=daemon,
            ),
        )

    def _handle_replay_dead_letters(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        actor = dict(request_context.get("current_actor", {}) or {})
        return replay_integration_dead_letters(
            getattr(self._bundle, "integration_outbox_service", None),
            ReplayDeadLettersCommand(
                event_ids=tuple(self._expand_form_values(payload, "event_ids") or self._expand_form_values(payload, "event_id")),
                event_types=tuple(self._expand_form_values(payload, "event_types")),
                limit=max(self._form_int(payload, "limit", default=20), 1),
                execute=self._form_bool(payload, "execute", default=False),
                replayed_by=str(actor.get("actor_id", "") or "web"),
                webhook_name=self._form_value(dict(payload), "webhook_name"),
            ),
        )

    def _handle_sync_ci_decisions(
        self,
        payload: Mapping[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        actor = dict(request_context.get("current_actor", {}) or {})
        return sync_ci_admission_decisions(
            getattr(self._bundle, "integration_outbox_service", None),
            CiAdmissionSyncCommand(
                webhook_name=self._required_form_value(dict(payload), "webhook_name")
                if not self._form_bool(payload, "dry_run", default=False)
                else self._form_value(dict(payload), "webhook_name"),
                event_types=tuple(self._expand_form_values(payload, "event_types")),
                query_limit=max(self._form_int(payload, "query_limit", default=0), 0),
                limit=max(self._form_int(payload, "limit", default=20), 1),
                dry_run=self._form_bool(payload, "dry_run", default=False),
                ci_endpoint=self._form_value(dict(payload), "ci_endpoint"),
                created_by=str(actor.get("actor_id", "") or "web"),
            ),
        )

    def _integration_webhook_result_payload(
        self,
        webhook: object,
        *,
        default_channel: str = "",
    ) -> dict[str, Any]:
        return {
            "webhook_id": str(getattr(webhook, "webhook_id", "") or ""),
            "name": str(getattr(webhook, "name", "") or ""),
            "url": str(getattr(webhook, "url", "") or ""),
            "subscribed_event_types": list(getattr(webhook, "subscribed_event_types", ()) or ()),
            "created_at": self._isoformat_or_none(getattr(webhook, "created_at", None)),
            "created_by": str(getattr(webhook, "created_by", "") or ""),
            "secret_hint": str(getattr(webhook, "secret_hint", "") or ""),
            "signature_key_id": str(getattr(webhook, "signature_key_id", "") or ""),
            "accepted_signature_key_ids": list(getattr(webhook, "accepted_signature_key_ids", ()) or ()),
            "failure_policy": str(getattr(webhook, "failure_policy", "") or ""),
            "delivery_channel": str(getattr(webhook, "delivery_channel", "") or default_channel),
        }

    def _maybe_sync_release_submission_devices(
        self,
        payload: Mapping[str, list[str]],
    ) -> dict[str, int] | None:
        device_service = getattr(self._bundle, "device_service", None)
        if (
            self._form_bool(payload, "skip_device_sync", default=False)
            or device_service is None
            or not hasattr(device_service, "sync_devices")
        ):
            return None
        sync_result = device_service.sync_devices(include_unavailable=True, mark_missing_offline=True)
        return {
            "scanned_count": int(getattr(sync_result, "scanned_count", 0) or 0),
            "created_count": len(getattr(sync_result, "created", ()) or ()),
            "updated_count": len(getattr(sync_result, "updated", ()) or ()),
            "refreshed_count": len(getattr(sync_result, "refreshed", ()) or ()),
            "marked_offline_count": len(getattr(sync_result, "marked_offline", ()) or ()),
        }


__all__ = ["IntegrationActionsMixin"]
