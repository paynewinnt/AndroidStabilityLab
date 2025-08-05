from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from stability.domain import AdmissionCaseLifecycleEvent, AdmissionCaseRoleAuditEntry
from stability.domain.value_objects import new_id

ALLOWED_STATUSES = frozenset(
    {"open", "assigned", "reviewing", "pending_confirmation", "approved_with_risk", "approved", "rejected"}
)
STATUS_ALIASES = {"new": "open", "confirmed": "pending_confirmation"}
ALLOWED_TRANSITIONS = {
    "open": frozenset({"open", "assigned", "reviewing", "pending_confirmation", "rejected"}),
    "assigned": frozenset({"assigned", "reviewing", "pending_confirmation", "approved_with_risk", "approved", "rejected"}),
    "reviewing": frozenset({"reviewing", "pending_confirmation", "approved_with_risk", "approved", "rejected", "assigned"}),
    "pending_confirmation": frozenset({"pending_confirmation", "approved_with_risk", "approved", "rejected", "reviewing"}),
    "approved_with_risk": frozenset({"approved_with_risk", "approved", "rejected", "reviewing"}),
    "approved": frozenset({"approved", "reviewing", "rejected"}),
    "rejected": frozenset({"rejected", "reviewing", "pending_confirmation"}),
}


def normalize_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    normalized = STATUS_ALIASES.get(normalized, normalized)
    if not normalized:
        return "open"
    if normalized not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported admission case status: {status}")
    return normalized


def validate_status_transition(*, from_status: str, to_status: str, action: str) -> None:
    normalized_from = normalize_status(from_status or "open")
    normalized_to = normalize_status(to_status or normalized_from)
    allowed = ALLOWED_TRANSITIONS.get(normalized_from, frozenset({normalized_from}))
    if normalized_to not in allowed:
        raise ValueError(f"Unsupported admission case transition via {action}: {normalized_from} -> {normalized_to}")


def lifecycle_event(
    *,
    action: str,
    from_status: str,
    to_status: str,
    changed_at: datetime,
    changed_by: str,
    reason: str,
    audit_source: Mapping[str, Any],
) -> AdmissionCaseLifecycleEvent:
    payload = dict(audit_source or {})
    return AdmissionCaseLifecycleEvent(
        entry_id=new_id("admission_case_transition"),
        action=str(action or "sync"),
        from_status=str(from_status or ""),
        to_status=str(to_status or ""),
        changed_at=changed_at,
        changed_by=str(changed_by or "system"),
        reason=str(reason or ""),
        audit_event_id=str(payload.get("audit_event_id", "") or ""),
        permission_check_id=str(payload.get("permission_check_id", "") or ""),
        session_id=str(payload.get("resolved_session_id", "") or ""),
    )


def role_audit_entry(
    *,
    role_name: str,
    changed_at: datetime,
    changed_by: str,
    from_actor_id: str,
    from_actor_display_name: str,
    to_actor_id: str,
    to_actor_display_name: str,
    reason: str,
    audit_source: Mapping[str, Any],
) -> AdmissionCaseRoleAuditEntry:
    payload = dict(audit_source or {})
    return AdmissionCaseRoleAuditEntry(
        entry_id=new_id("admission_case_role_audit"),
        role_name=str(role_name or ""),
        changed_at=changed_at,
        changed_by=str(changed_by or "system"),
        from_actor_id=str(from_actor_id or ""),
        from_actor_display_name=str(from_actor_display_name or ""),
        to_actor_id=str(to_actor_id or ""),
        to_actor_display_name=str(to_actor_display_name or ""),
        reason=str(reason or ""),
        audit_event_id=str(payload.get("audit_event_id", "") or ""),
        permission_check_id=str(payload.get("permission_check_id", "") or ""),
        session_id=str(payload.get("resolved_session_id", "") or ""),
    )
