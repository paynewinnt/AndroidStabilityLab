from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Mapping

from stability.domain import (
    AdmissionCaseCollaborationRecord,
    CollaborationComment,
    CollaborationEvent,
    CollaborationSession,
    IssueCollaborationRecord,
    IssueDefectLink,
)
from stability.domain.collaboration_models import CollaborationExternalIdentity
from stability.domain.value_objects import utcnow


class PersistenceMixin:
    def _load_session_registry(self) -> dict[str, Any]:
        if not self._sessions_path.exists():
            return {}
        try:
            payload = json.loads(self._sessions_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _load_identity_registry(self) -> dict[str, Any]:
        if not self._identities_path.exists():
            return {}
        try:
            payload = json.loads(self._identities_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _save_external_identity(self, item: CollaborationExternalIdentity) -> None:
        registry = self._load_identity_registry()
        registry[item.identity_id] = self._external_identity_payload(item)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._identities_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    def _external_identity_for_actor(self, actor_id: str) -> CollaborationExternalIdentity | None:
        key = str(actor_id or "").strip()
        if not key:
            return None
        for payload in self._load_identity_registry().values():
            if not isinstance(payload, Mapping):
                continue
            identity = self._external_identity_from_payload(payload)
            if identity.actor_id == key:
                return identity
        return None

    def _save_session(self, item: CollaborationSession) -> None:
        registry = self._load_session_registry()
        registry[item.session_token] = self._session_payload(item)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    def _active_session_for_actor(self, actor_id: str) -> CollaborationSession | None:
        current_time = utcnow()
        active: list[CollaborationSession] = []
        for payload in self._load_session_registry().values():
            if not isinstance(payload, Mapping):
                continue
            session = self._session_from_payload(payload)
            if session.actor_id != actor_id:
                continue
            if session.revoked_at is not None:
                continue
            if session.expires_at is not None and session.expires_at <= current_time:
                continue
            active.append(session)
        active.sort(key=lambda item: item.issued_at, reverse=True)
        return active[0] if active else None

    @staticmethod
    def _session_expiring(item: CollaborationSession, current_time: datetime) -> bool:
        if item.expires_at is None:
            return False
        return item.expires_at <= current_time + timedelta(minutes=5)

    @staticmethod
    def _session_payload(item: CollaborationSession) -> dict[str, Any]:
        return {
            "session_token": item.session_token,
            "session_id": item.session_id,
            "actor_id": item.actor_id,
            "identity_id": item.identity_id,
            "auth_mechanism": item.auth_mechanism,
            "issued_at": item.issued_at.isoformat(),
            "expires_at": item.expires_at.isoformat() if item.expires_at else None,
            "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
            "issued_by": item.issued_by,
            "revoked_by": item.revoked_by,
            "revoke_reason": item.revoke_reason,
            "permission_scope": list(item.permission_scope),
            "session_source": item.session_source,
            "identity_provider": item.identity_provider,
            "external_subject_id": item.external_subject_id,
            "organization_id": item.organization_id,
        }

    @staticmethod
    def _session_from_payload(payload: Mapping[str, Any]) -> CollaborationSession:
        issued_at_raw = str(payload.get("issued_at", "") or "")
        expires_at_raw = str(payload.get("expires_at", "") or "")
        revoked_at_raw = str(payload.get("revoked_at", "") or "")
        return CollaborationSession(
            session_token=str(payload.get("session_token", "") or ""),
            session_id=str(payload.get("session_id", "") or ""),
            actor_id=str(payload.get("actor_id", "") or ""),
            identity_id=str(payload.get("identity_id", "") or ""),
            auth_mechanism=str(payload.get("auth_mechanism", "") or "issued_session"),
            issued_at=datetime.fromisoformat(issued_at_raw) if issued_at_raw else utcnow(),
            expires_at=datetime.fromisoformat(expires_at_raw) if expires_at_raw else None,
            revoked_at=datetime.fromisoformat(revoked_at_raw) if revoked_at_raw else None,
            issued_by=str(payload.get("issued_by", "") or ""),
            revoked_by=str(payload.get("revoked_by", "") or ""),
            revoke_reason=str(payload.get("revoke_reason", "") or ""),
            permission_scope=tuple(str(item) for item in (payload.get("permission_scope", ()) or ()) if str(item).strip()),
            session_source=str(payload.get("session_source", "") or ""),
            identity_provider=str(payload.get("identity_provider", "") or ""),
            external_subject_id=str(payload.get("external_subject_id", "") or ""),
            organization_id=str(payload.get("organization_id", "") or ""),
        )

    @staticmethod
    def _external_identity_payload(item: CollaborationExternalIdentity) -> dict[str, Any]:
        return {
            "identity_id": item.identity_id,
            "actor_id": item.actor_id,
            "provider": item.provider,
            "external_subject_id": item.external_subject_id,
            "external_email": item.external_email,
            "external_display_name": item.external_display_name,
            "organization_id": item.organization_id,
            "team_ids": list(item.team_ids),
            "role_claims": list(item.role_claims),
            "auth_mechanism": item.auth_mechanism,
            "session_id": item.session_id,
            "session_source": item.session_source,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

    @staticmethod
    def _external_identity_from_payload(payload: Mapping[str, Any]) -> CollaborationExternalIdentity:
        created_at_raw = str(payload.get("created_at", "") or "")
        updated_at_raw = str(payload.get("updated_at", "") or "")
        return CollaborationExternalIdentity(
            identity_id=str(payload.get("identity_id", "") or ""),
            actor_id=str(payload.get("actor_id", "") or ""),
            provider=str(payload.get("provider", "") or ""),
            external_subject_id=str(payload.get("external_subject_id", "") or ""),
            external_email=str(payload.get("external_email", "") or ""),
            external_display_name=str(payload.get("external_display_name", "") or ""),
            organization_id=str(payload.get("organization_id", "") or ""),
            team_ids=tuple(str(item).strip() for item in (payload.get("team_ids", ()) or ()) if str(item).strip()),
            role_claims=tuple(str(item).strip() for item in (payload.get("role_claims", ()) or ()) if str(item).strip()),
            auth_mechanism=str(payload.get("auth_mechanism", "") or "sso_header"),
            session_id=str(payload.get("session_id", "") or ""),
            session_source=str(payload.get("session_source", "") or ""),
            created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else None,
            updated_at=datetime.fromisoformat(updated_at_raw) if updated_at_raw else None,
        )

    def _load_issue_registry(self) -> dict[str, Any]:
        if not self._issues_path.exists():
            return {}
        try:
            payload = json.loads(self._issues_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _load_admission_case_registry(self) -> dict[str, Any]:
        if not self._admission_cases_path.exists():
            return {}
        try:
            payload = json.loads(self._admission_cases_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def _save_issue_record(self, item: IssueCollaborationRecord) -> None:
        registry = self._load_issue_registry()
        registry[item.fingerprint] = self._issue_record_payload(item)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._issues_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_admission_case_record(self, item: AdmissionCaseCollaborationRecord) -> None:
        registry = self._load_admission_case_registry()
        registry[item.baseline_key] = self._admission_case_record_payload(item)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._admission_cases_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _issue_record_payload(item: IssueCollaborationRecord) -> dict[str, Any]:
        return {
            "workflow_state": item.workflow_state,
            "assignee_id": item.assignee_id,
            "assignee_display_name": item.assignee_display_name,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "updated_by": item.updated_by,
            "comments": [
                {
                    "comment_id": comment.comment_id,
                    "target_type": comment.target_type,
                    "target_id": comment.target_id,
                    "body": comment.body,
                    "created_at": comment.created_at.isoformat(),
                    "created_by": comment.created_by,
                    "session_source": comment.session_source,
                    "audit_source": dict(comment.audit_source),
                }
                for comment in item.comments
            ],
            "events": [
                {
                    "event_id": event.event_id,
                    "target_type": event.target_type,
                    "target_id": event.target_id,
                    "action": event.action,
                    "created_at": event.created_at.isoformat(),
                    "created_by": event.created_by,
                    "session_source": event.session_source,
                    "audit_source": dict(event.audit_source),
                    "payload": dict(event.payload),
                }
                for event in item.events
            ],
            "defect_links": [
                {
                    "link_id": entry.link_id,
                    "fingerprint": entry.fingerprint,
                    "system_key": entry.system_key,
                    "defect_id": entry.defect_id,
                    "title": entry.title,
                    "url": entry.url,
                    "status": entry.status,
                    "acceptable_for_close": bool(entry.acceptable_for_close),
                    "sync_status": entry.sync_status,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None,
                    "created_by": entry.created_by,
                    "synced_at": entry.synced_at.isoformat() if entry.synced_at else None,
                    "synced_by": entry.synced_by,
                    "session_source": entry.session_source,
                    "audit_source": dict(entry.audit_source),
                    "metadata": dict(entry.metadata),
                }
                for entry in item.defect_links
            ],
        }

    @staticmethod
    def _issue_record_from_payload(fingerprint: str, payload: Mapping[str, Any]) -> IssueCollaborationRecord:
        updated_at_raw = str(payload.get("updated_at", "") or "")
        comments = []
        for item in list(payload.get("comments", ()) or ()):
            if not isinstance(item, Mapping):
                continue
            created_at_raw = str(item.get("created_at", "") or "")
            comments.append(
                CollaborationComment(
                    comment_id=str(item.get("comment_id", "") or ""),
                    target_type=str(item.get("target_type", "") or "issue"),
                    target_id=str(item.get("target_id", "") or fingerprint),
                    body=str(item.get("body", "") or ""),
                    created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else utcnow(),
                    created_by=str(item.get("created_by", "") or ""),
                    session_source=str(item.get("session_source", "") or ""),
                    audit_source=dict(item.get("audit_source", {}) or {}),
                )
            )
        events = []
        for item in list(payload.get("events", ()) or ()):
            if not isinstance(item, Mapping):
                continue
            created_at_raw = str(item.get("created_at", "") or "")
            events.append(
                CollaborationEvent(
                    event_id=str(item.get("event_id", "") or ""),
                    target_type=str(item.get("target_type", "") or "issue"),
                    target_id=str(item.get("target_id", "") or fingerprint),
                    action=str(item.get("action", "") or ""),
                    created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else utcnow(),
                    created_by=str(item.get("created_by", "") or ""),
                    session_source=str(item.get("session_source", "") or ""),
                    audit_source=dict(item.get("audit_source", {}) or {}),
                    payload=dict(item.get("payload", {}) or {}),
                )
            )
        defect_links = []
        for item in list(payload.get("defect_links", ()) or ()):
            if not isinstance(item, Mapping):
                continue
            created_at_raw = str(item.get("created_at", "") or "")
            synced_at_raw = str(item.get("synced_at", "") or "")
            defect_links.append(
                IssueDefectLink(
                    link_id=str(item.get("link_id", "") or ""),
                    fingerprint=str(item.get("fingerprint", "") or fingerprint),
                    system_key=str(item.get("system_key", "") or ""),
                    defect_id=str(item.get("defect_id", "") or ""),
                    title=str(item.get("title", "") or ""),
                    url=str(item.get("url", "") or ""),
                    status=str(item.get("status", "") or ""),
                    acceptable_for_close=bool(item.get("acceptable_for_close", False)),
                    sync_status=str(item.get("sync_status", "") or "pending_create"),
                    created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else None,
                    created_by=str(item.get("created_by", "") or ""),
                    synced_at=datetime.fromisoformat(synced_at_raw) if synced_at_raw else None,
                    synced_by=str(item.get("synced_by", "") or ""),
                    session_source=str(item.get("session_source", "") or ""),
                    audit_source=dict(item.get("audit_source", {}) or {}),
                    metadata=dict(item.get("metadata", {}) or {}),
                )
            )
        return IssueCollaborationRecord(
            fingerprint=fingerprint,
            workflow_state=str(payload.get("workflow_state", "") or "new"),
            assignee_id=str(payload.get("assignee_id", "") or ""),
            assignee_display_name=str(payload.get("assignee_display_name", "") or ""),
            updated_at=datetime.fromisoformat(updated_at_raw) if updated_at_raw else None,
            updated_by=str(payload.get("updated_by", "") or ""),
            comments=tuple(comments),
            events=tuple(events),
            defect_links=tuple(defect_links),
        )

    @staticmethod
    def _admission_case_record_payload(item: AdmissionCaseCollaborationRecord) -> dict[str, Any]:
        return {
            "workflow_state": item.workflow_state,
            "assignee_id": item.assignee_id,
            "assignee_display_name": item.assignee_display_name,
            "final_reviewer_id": item.final_reviewer_id,
            "final_reviewer_display_name": item.final_reviewer_display_name,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "updated_by": item.updated_by,
            "comments": [
                {
                    "comment_id": comment.comment_id,
                    "target_type": comment.target_type,
                    "target_id": comment.target_id,
                    "body": comment.body,
                    "created_at": comment.created_at.isoformat(),
                    "created_by": comment.created_by,
                    "session_source": comment.session_source,
                    "audit_source": dict(comment.audit_source),
                }
                for comment in item.comments
            ],
            "events": [
                {
                    "event_id": event.event_id,
                    "target_type": event.target_type,
                    "target_id": event.target_id,
                    "action": event.action,
                    "created_at": event.created_at.isoformat(),
                    "created_by": event.created_by,
                    "session_source": event.session_source,
                    "audit_source": dict(event.audit_source),
                    "payload": dict(event.payload),
                }
                for event in item.events
            ],
        }

    @staticmethod
    def _admission_case_record_from_payload(
        baseline_key: str,
        payload: Mapping[str, Any],
    ) -> AdmissionCaseCollaborationRecord:
        updated_at_raw = str(payload.get("updated_at", "") or "")
        comments = []
        for item in list(payload.get("comments", ()) or ()):
            if not isinstance(item, Mapping):
                continue
            created_at_raw = str(item.get("created_at", "") or "")
            comments.append(
                CollaborationComment(
                    comment_id=str(item.get("comment_id", "") or ""),
                    target_type=str(item.get("target_type", "") or "admission_case"),
                    target_id=str(item.get("target_id", "") or baseline_key),
                    body=str(item.get("body", "") or ""),
                    created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else utcnow(),
                    created_by=str(item.get("created_by", "") or ""),
                    session_source=str(item.get("session_source", "") or ""),
                    audit_source=dict(item.get("audit_source", {}) or {}),
                )
            )
        events = []
        for item in list(payload.get("events", ()) or ()):
            if not isinstance(item, Mapping):
                continue
            created_at_raw = str(item.get("created_at", "") or "")
            events.append(
                CollaborationEvent(
                    event_id=str(item.get("event_id", "") or ""),
                    target_type=str(item.get("target_type", "") or "admission_case"),
                    target_id=str(item.get("target_id", "") or baseline_key),
                    action=str(item.get("action", "") or ""),
                    created_at=datetime.fromisoformat(created_at_raw) if created_at_raw else utcnow(),
                    created_by=str(item.get("created_by", "") or ""),
                    session_source=str(item.get("session_source", "") or ""),
                    audit_source=dict(item.get("audit_source", {}) or {}),
                    payload=dict(item.get("payload", {}) or {}),
                )
            )
        return AdmissionCaseCollaborationRecord(
            baseline_key=baseline_key,
            workflow_state=str(payload.get("workflow_state", "") or "new"),
            assignee_id=str(payload.get("assignee_id", "") or ""),
            assignee_display_name=str(payload.get("assignee_display_name", "") or ""),
            final_reviewer_id=str(payload.get("final_reviewer_id", "") or ""),
            final_reviewer_display_name=str(payload.get("final_reviewer_display_name", "") or ""),
            updated_at=datetime.fromisoformat(updated_at_raw) if updated_at_raw else None,
            updated_by=str(payload.get("updated_by", "") or ""),
            comments=tuple(comments),
            events=tuple(events),
        )
