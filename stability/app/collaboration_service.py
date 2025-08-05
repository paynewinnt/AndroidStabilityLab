from __future__ import annotations

from pathlib import Path
from typing import Sequence

from stability.domain import CollaborationActor, CollaborationRole

from .collaboration import (
    AdmissionWorkflowMixin,
    DefectLinksMixin,
    EventPublisherMixin,
    IdentitySessionsMixin,
    IssueWorkflowMixin,
    PersistenceMixin,
)
from .integration_outbox_service import IntegrationOutboxService


class CollaborationService(
    AdmissionWorkflowMixin,
    DefectLinksMixin,
    IssueWorkflowMixin,
    IdentitySessionsMixin,
    PersistenceMixin,
    EventPublisherMixin,
):
    """Provide a minimal writable stage-3 collaboration loop for issues."""

    _default_roles = (
        CollaborationRole(
            role_key="admin",
            name="管理员",
            permissions=(
                "assign_issue",
                "comment_issue",
                "transition_issue",
                "link_issue_defect",
                "sync_issue_defect",
                "assign_admission_case",
                "comment_admission_case",
                "transition_admission_case",
                "override_gate",
            ),
        ),
        CollaborationRole(
            role_key="tester",
            name="测试",
            permissions=(
                "assign_issue",
                "comment_issue",
                "transition_issue",
                "link_issue_defect",
                "sync_issue_defect",
                "assign_admission_case",
                "comment_admission_case",
                "transition_admission_case",
                "override_gate",
            ),
        ),
        CollaborationRole(
            role_key="developer",
            name="研发",
            permissions=("comment_issue", "transition_issue", "link_issue_defect", "sync_issue_defect", "comment_admission_case"),
        ),
        CollaborationRole(
            role_key="observer",
            name="观察者",
            permissions=("comment_issue", "comment_admission_case"),
        ),
    )
    _default_actors = (
        CollaborationActor(
            actor_id="admin",
            display_name="Admin",
            role_key="admin",
            permissions=(
                "assign_issue",
                "comment_issue",
                "transition_issue",
                "link_issue_defect",
                "sync_issue_defect",
                "assign_admission_case",
                "comment_admission_case",
                "transition_admission_case",
                "override_gate",
            ),
        ),
        CollaborationActor(
            actor_id="tester",
            display_name="Tester",
            role_key="tester",
            permissions=(
                "assign_issue",
                "comment_issue",
                "transition_issue",
                "link_issue_defect",
                "sync_issue_defect",
                "assign_admission_case",
                "comment_admission_case",
                "transition_admission_case",
                "override_gate",
            ),
        ),
        CollaborationActor(
            actor_id="developer",
            display_name="Developer",
            role_key="developer",
            permissions=("comment_issue", "transition_issue", "link_issue_defect", "sync_issue_defect", "comment_admission_case"),
        ),
        CollaborationActor(
            actor_id="observer",
            display_name="Observer",
            role_key="observer",
            permissions=("comment_issue", "comment_admission_case"),
        ),
    )
    _allowed_states = frozenset({"new", "assigned", "processing", "confirmed", "resolved", "ignored"})
    _issue_terminal_states = frozenset({"resolved"})
    _allowed_admission_states = frozenset(
        {"new", "assigned", "reviewing", "pending_confirmation", "approved_with_risk", "approved", "rejected"}
    )
    _identity_namespace = "asl.identity.v1"
    _external_identity_namespace = "asl.external_identity.v1"
    _session_token_namespace = "asl.session.v1"
    _session_id_namespace = "asl.session_id.v1"
    _issued_session_namespace = "asl.issued_session.v1"
    _permission_check_namespace = "asl.permission_check.v1"
    _audit_event_namespace = "asl.audit_event.v1"
    _default_session_ttl_seconds = 12 * 60 * 60
    _permission_policies = {
        "assign_issue": {"target_type": "issue", "actions": ("assign",), "allowed_roles": ("admin", "tester")},
        "comment_issue": {"target_type": "issue", "actions": ("comment",), "allowed_roles": ("admin", "tester", "developer", "observer")},
        "transition_issue": {"target_type": "issue", "actions": ("transition",), "allowed_roles": ("admin", "tester", "developer")},
        "link_issue_defect": {"target_type": "issue", "actions": ("defect_link",), "allowed_roles": ("admin", "tester", "developer")},
        "sync_issue_defect": {"target_type": "issue", "actions": ("defect_sync",), "allowed_roles": ("admin", "tester", "developer")},
        "assign_admission_case": {"target_type": "admission_case", "actions": ("assign",), "allowed_roles": ("admin", "tester")},
        "comment_admission_case": {"target_type": "admission_case", "actions": ("comment",), "allowed_roles": ("admin", "tester", "developer", "observer")},
        "transition_admission_case": {"target_type": "admission_case", "actions": ("transition",), "allowed_roles": ("admin", "tester")},
        "override_gate": {"target_type": "quality_gate", "actions": ("override",), "allowed_roles": ("admin", "tester")},
    }

    def __init__(
        self,
        *,
        root_dir: str | Path = "runtime/collaboration",
        outbox_service: IntegrationOutboxService | None = None,
        trusted_organization_ids: Sequence[str] = (),
    ) -> None:
        self._root_dir = Path(root_dir)
        self._issues_path = self._root_dir / "issues.json"
        self._admission_cases_path = self._root_dir / "admission_cases.json"
        self._sessions_path = self._root_dir / "sessions.json"
        self._identities_path = self._root_dir / "identities.json"
        self._outbox_service = outbox_service
        self._admission_case_service = None
        self._roles = {item.role_key: item for item in self._default_roles}
        self._actors = {item.actor_id: item for item in self._default_actors}
        self._trusted_organization_ids = {
            str(item).strip() for item in trusted_organization_ids if str(item).strip()
        }

    def attach_admission_case_service(self, admission_case_service: object) -> None:
        self._admission_case_service = admission_case_service

    def list_roles(self) -> tuple[CollaborationRole, ...]:
        return tuple(self._roles.values())

    def list_actors(self) -> tuple[CollaborationActor, ...]:
        return tuple(self._actors.values())
