from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from stability.domain import WebhookSubscription


class SecurityMixin:
    _allowed_failure_policies = frozenset({"retryable_http", "best_effort", "fail_closed"})
    _retryable_http_statuses = frozenset({408, 409, 425, 429})

    @staticmethod
    def _signature(body: bytes, *, webhook: WebhookSubscription) -> str:
        if SecurityMixin._uses_feishu_bot_signature(webhook):
            return f"sha256={hashlib.sha256(body).hexdigest()}"
        signing_secret = str(getattr(webhook, "signing_secret", "") or "")
        if signing_secret:
            digest = hmac.new(signing_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            return f"sha256={digest}"
        return f"sha256={hashlib.sha256(body).hexdigest()}"

    @staticmethod
    def _uses_feishu_bot_signature(webhook: WebhookSubscription) -> bool:
        return str(getattr(webhook, "delivery_channel", "") or "").strip() == "feishu_bot"

    @classmethod
    def _signature_algorithm(cls, webhook: WebhookSubscription) -> str:
        if cls._uses_feishu_bot_signature(webhook):
            return "sha256"
        return "hmac-sha256" if str(getattr(webhook, "signing_secret", "") or "").strip() else "sha256"

    @staticmethod
    def _failure_category(*, status_code: int | None, should_retry: bool) -> str:
        if status_code is None:
            return "transport_error"
        if int(status_code) >= 500:
            return "server_error"
        if int(status_code) in SecurityMixin._retryable_http_statuses:
            return "retryable_client_error"
        if should_retry:
            return "retryable_error"
        return "client_error"

    @staticmethod
    def _idempotency_key(
        *,
        event_type: str,
        target_type: str,
        target_id: str,
        payload: Mapping[str, Any],
    ) -> str:
        raw = json.dumps(
            {
                "event_type": event_type,
                "target_type": target_type,
                "target_id": target_id,
                "payload": dict(payload or {}),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return f"idem:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"

    @classmethod
    def _validated_webhook_security(
        cls,
        *,
        url: str,
        signing_secret: str,
        signature_key_id: str,
        accepted_signature_key_ids: Sequence[str],
        failure_policy: str,
    ) -> dict[str, Any]:
        endpoint = str(url or "").strip()
        parsed = urlparse(endpoint)
        scheme = str(parsed.scheme or "").strip().lower()
        host = str(parsed.hostname or "").strip().lower()
        if scheme not in {"http", "https"}:
            raise ValueError("Webhook url must use http or https.")
        if not host:
            raise ValueError("Webhook url must include a host.")
        is_local = cls._is_local_webhook_host(host)
        if scheme != "https" and not is_local:
            raise ValueError("Non-local webhooks must use https.")
        normalized_secret = str(signing_secret or "").strip()
        if not is_local and not normalized_secret:
            raise ValueError("Non-local webhooks require signing_secret so receivers can verify callback signatures.")
        normalized_key_id = str(signature_key_id or "").strip() or "v1"
        normalized_accepted = [str(item).strip() for item in accepted_signature_key_ids if str(item).strip()]
        if normalized_key_id not in normalized_accepted:
            normalized_accepted.insert(0, normalized_key_id)
        deduped_key_ids: list[str] = []
        seen: set[str] = set()
        for item in normalized_accepted:
            if item in seen:
                continue
            seen.add(item)
            deduped_key_ids.append(item)
        normalized_policy = str(failure_policy or "").strip() or "retryable_http"
        if normalized_policy not in cls._allowed_failure_policies:
            raise ValueError(
                "failure_policy must be one of: " + ", ".join(sorted(cls._allowed_failure_policies))
            )
        return {
            "url": endpoint,
            "is_local": is_local,
            "signing_secret": normalized_secret,
            "signature_key_id": normalized_key_id,
            "accepted_signature_key_ids": tuple(deduped_key_ids),
            "failure_policy": normalized_policy,
        }

    @staticmethod
    def _is_local_webhook_host(host: str) -> bool:
        value = str(host or "").strip().lower()
        if value in {"127.0.0.1", "localhost", "::1"}:
            return True
        try:
            return ipaddress.ip_address(value).is_private
        except ValueError:
            pass
        return False
