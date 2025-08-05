from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class CollaborationRole:
    """Minimal local role model for stage-3 collaboration actions."""

    role_key: str
    name: str
    permissions: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class CollaborationActor:
    """Resolved local actor identity used by the collaboration workflow."""

    actor_id: str
    display_name: str
    role_key: str
    permissions: Sequence[str] = field(default_factory=tuple)
    is_active: bool = True


@dataclass(frozen=True)
class CollaborationExternalIdentity:
    """Trusted external SSO identity bound to a local collaboration actor."""

    identity_id: str
    actor_id: str
    provider: str
    external_subject_id: str
    external_email: str
    external_display_name: str
    organization_id: str
    team_ids: Sequence[str] = field(default_factory=tuple)
    role_claims: Sequence[str] = field(default_factory=tuple)
    auth_mechanism: str = "sso_header"
    session_id: str = ""
    session_source: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class CollaborationUserProfile:
    """Unified directory view for local actors and trusted SSO identities."""

    profile_id: str
    actor_id: str
    identity_id: str
    display_name: str
    role_key: str
    permissions: Sequence[str] = field(default_factory=tuple)
    email: str = ""
    organization_id: str = ""
    team_ids: Sequence[str] = field(default_factory=tuple)
    external_identities: Sequence[CollaborationExternalIdentity] = field(default_factory=tuple)
    last_seen_at: datetime | None = None
    source: str = "collaboration_actor_registry"
    is_active: bool = True


@dataclass(frozen=True)
class CollaborationSession:
    """One locally issued session with expiry and revocation metadata."""

    session_token: str
    session_id: str
    actor_id: str
    identity_id: str
    auth_mechanism: str
    issued_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    issued_by: str = ""
    revoked_by: str = ""
    revoke_reason: str = ""
    permission_scope: Sequence[str] = field(default_factory=tuple)
    session_source: str = ""
    identity_provider: str = ""
    external_subject_id: str = ""
    organization_id: str = ""


@dataclass(frozen=True)
class CollaborationComment:
    """One human discussion entry attached to an issue or admission case."""

    comment_id: str
    target_type: str
    target_id: str
    body: str
    created_at: datetime
    created_by: str
    session_source: str = ""
    audit_source: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CollaborationEvent:
    """Immutable collaboration action record."""

    event_id: str
    target_type: str
    target_id: str
    action: str
    created_at: datetime
    created_by: str
    session_source: str = ""
    audit_source: Mapping[str, Any] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IssueDefectLink:
    """One external defect link or creation request attached to an issue."""

    link_id: str
    fingerprint: str
    system_key: str
    defect_id: str = ""
    title: str = ""
    url: str = ""
    status: str = ""
    acceptable_for_close: bool = False
    sync_status: str = "pending_create"
    created_at: datetime | None = None
    created_by: str = ""
    synced_at: datetime | None = None
    synced_by: str = ""
    session_source: str = ""
    audit_source: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IssueCollaborationRecord:
    """Collaboration state for one aggregated issue fingerprint."""

    fingerprint: str
    workflow_state: str
    assignee_id: str = ""
    assignee_display_name: str = ""
    updated_at: datetime | None = None
    updated_by: str = ""
    comments: Sequence[CollaborationComment] = field(default_factory=tuple)
    events: Sequence[CollaborationEvent] = field(default_factory=tuple)
    defect_links: Sequence[IssueDefectLink] = field(default_factory=tuple)


@dataclass(frozen=True)
class AdmissionCaseCollaborationRecord:
    """Collaboration state for one admission case baseline."""

    baseline_key: str
    workflow_state: str
    assignee_id: str = ""
    assignee_display_name: str = ""
    final_reviewer_id: str = ""
    final_reviewer_display_name: str = ""
    updated_at: datetime | None = None
    updated_by: str = ""
    comments: Sequence[CollaborationComment] = field(default_factory=tuple)
    events: Sequence[CollaborationEvent] = field(default_factory=tuple)
