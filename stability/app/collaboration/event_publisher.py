from __future__ import annotations

from typing import Any, Mapping


class EventPublisherMixin:
    def _publish_event(
        self,
        *,
        event_type: str,
        target_type: str,
        target_id: str,
        actor_id: str,
        session_source: str,
        audit_source: Mapping[str, Any] | None,
        payload: Mapping[str, Any],
    ) -> None:
        if self._outbox_service is None:
            return
        self._outbox_service.publish_event(
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            created_by=actor_id,
            session_source=session_source.strip(),
            audit_source=dict(audit_source or {}),
            payload=payload,
        )
