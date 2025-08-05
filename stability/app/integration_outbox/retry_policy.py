from __future__ import annotations


class RetryPolicyMixin:
    _retryable_http_statuses = frozenset({408, 409, 425, 429})

    def _compute_retry_backoff(self, attempt_count: int) -> int:
        if self._retry_delay <= 0:
            return max(self._delivery_interval, 0)
        multiplier = max(attempt_count - 1, 0)
        backoff_seconds = self._retry_delay * (2 ** multiplier)
        backoff_seconds = min(backoff_seconds, self._max_retry_delay)
        return max(backoff_seconds, self._delivery_interval)

    @classmethod
    def _is_retryable_failure(cls, status_code: int | None) -> bool:
        if status_code is None:
            return True
        if int(status_code) >= 500:
            return True
        return int(status_code) in cls._retryable_http_statuses

    @staticmethod
    def _is_system_alert_event(event_type: str) -> bool:
        return str(event_type or "").startswith("outbox.")
