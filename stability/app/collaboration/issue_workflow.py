from __future__ import annotations

from typing import Any, Mapping

from stability.domain import (
    CollaborationActor,
    CollaborationComment,
    CollaborationEvent,
    IssueCollaborationRecord,
    IssueDefectLink,
)
from stability.domain.value_objects import new_id, utcnow


class IssueWorkflowMixin:
    def get_issue_record(self, fingerprint: str) -> IssueCollaborationRecord:
        key = fingerprint.strip()
        if not key:
            raise ValueError("fingerprint is required.")
        registry = self._load_issue_registry()
        payload = registry.get(key)
        if not isinstance(payload, Mapping):
            return IssueCollaborationRecord(fingerprint=key, workflow_state="new")
        return self._issue_record_from_payload(key, payload)

    def assign_issue(
        self,
        *,
        fingerprint: str,
        actor_id: str,
        actor_identity_id: str = "",
        assignee_id: str,
        session_source: str = "",
        audit_source: Mapping[str, Any] | None = None,
    ) -> IssueCollaborationRecord:
        actor, audit_payload = self._authorize_actor(
            actor_id=actor_id,
            actor_identity_id=actor_identity_id,
            permission="assign_issue",
            audit_source=audit_source,
        )
        assignee = self.get_actor(assignee_id)
        record = self.get_issue_record(fingerprint)
        updated = self._issue_record_with_event(
            record=record,
            action="assign",
            actor=actor,
            payload={
                "actor_identity_id": str(audit_payload.get("resolved_identity_id", "") or ""),
                "assignee_id": assignee.actor_id,
                "assignee_identity_id": self._identity_id_for_actor(assignee),
                "assignee_display_name": assignee.display_name,
                "workflow_state": "assigned",
            },
            session_source=session_source,
            audit_source=audit_payload,
            workflow_state="assigned",
            assignee_id=assignee.actor_id,
            assignee_display_name=assignee.display_name,
        )
        self._save_issue_record(updated)
        self._publish_event(
            event_type="issue.assigned",
            target_type="issue",
            target_id=updated.fingerprint,
            actor_id=actor.actor_id,
            session_source=session_source,
            audit_source=audit_payload,
            payload={
                "actor_identity_id": str(audit_payload.get("resolved_identity_id", "") or ""),
                "assignee_id": updated.assignee_id,
                "assignee_identity_id": self._identity_id_for_actor(assignee),
                "workflow_state": updated.workflow_state,
            },
        )
        return updated

    def transition_issue(
        self,
        *,
        fingerprint: str,
        actor_id: str,
        actor_identity_id: str = "",
        workflow_state: str,
        reason: str = "",
        session_source: str = "",
        audit_source: Mapping[str, Any] | None = None,
    ) -> IssueCollaborationRecord:
        actor, audit_payload = self._authorize_actor(
            actor_id=actor_id,
            actor_identity_id=actor_identity_id,
            permission="transition_issue",
            audit_source=audit_source,
        )
        target_state = workflow_state.strip()
        if target_state not in self._allowed_states:
            raise ValueError(f"Unsupported workflow_state: {target_state}")
        record = self.get_issue_record(fingerprint)
        # 当前 issue 状态机里用 resolved 表示关闭态；若已关联缺陷，关闭前必须确认至少有一条缺陷达到可接受状态。
        if target_state in self._issue_terminal_states and record.defect_links and not any(
            bool(item.acceptable_for_close) for item in record.defect_links
        ):
            raise ValueError("Issue cannot be resolved before one linked defect reaches an acceptable status.")
        updated = self._issue_record_with_event(
            record=record,
            action="transition",
            actor=actor,
            payload={
                "actor_identity_id": str(audit_payload.get("resolved_identity_id", "") or ""),
                "from_state": record.workflow_state,
                "to_state": target_state,
                "reason": reason.strip(),
            },
            session_source=session_source,
            audit_source=audit_payload,
            workflow_state=target_state,
            assignee_id=record.assignee_id,
            assignee_display_name=record.assignee_display_name,
            defect_links=tuple(record.defect_links),
        )
        self._save_issue_record(updated)
        self._publish_event(
            event_type="issue.transitioned",
            target_type="issue",
            target_id=updated.fingerprint,
            actor_id=actor.actor_id,
            session_source=session_source,
            audit_source=audit_payload,
            payload={
                "actor_identity_id": str(audit_payload.get("resolved_identity_id", "") or ""),
                "from_state": record.workflow_state,
                "to_state": updated.workflow_state,
                "reason": reason.strip(),
            },
        )
        return updated

    def comment_issue(
        self,
        *,
        fingerprint: str,
        actor_id: str,
        actor_identity_id: str = "",
        body: str,
        session_source: str = "",
        audit_source: Mapping[str, Any] | None = None,
    ) -> IssueCollaborationRecord:
        actor, audit_payload = self._authorize_actor(
            actor_id=actor_id,
            actor_identity_id=actor_identity_id,
            permission="comment_issue",
            audit_source=audit_source,
        )
        message = body.strip()
        if not message:
            raise ValueError("Comment body is required.")
        record = self.get_issue_record(fingerprint)
        comment = CollaborationComment(
            comment_id=new_id("comment"),
            target_type="issue",
            target_id=record.fingerprint,
            body=message,
            created_at=utcnow(),
            created_by=actor.actor_id,
            session_source=session_source.strip(),
            audit_source=audit_payload,
        )
        updated = self._issue_record_with_event(
            record=record,
            action="comment",
            actor=actor,
            payload={
                "comment_id": comment.comment_id,
                "actor_identity_id": str(audit_payload.get("resolved_identity_id", "") or ""),
            },
            session_source=session_source,
            audit_source=audit_payload,
            workflow_state=record.workflow_state,
            assignee_id=record.assignee_id,
            assignee_display_name=record.assignee_display_name,
            comments=tuple(list(record.comments) + [comment]),
            defect_links=tuple(record.defect_links),
        )
        self._save_issue_record(updated)
        self._publish_event(
            event_type="issue.commented",
            target_type="issue",
            target_id=updated.fingerprint,
            actor_id=actor.actor_id,
            session_source=session_source,
            audit_source=audit_payload,
            payload={
                "comment_id": comment.comment_id,
                "actor_identity_id": str(audit_payload.get("resolved_identity_id", "") or ""),
            },
        )
        return updated

    def _issue_record_with_event(
        self,
        *,
        record: IssueCollaborationRecord,
        action: str,
        actor: CollaborationActor,
        payload: Mapping[str, Any],
        session_source: str,
        audit_source: Mapping[str, Any] | None,
        workflow_state: str,
        assignee_id: str,
        assignee_display_name: str,
        comments: tuple[CollaborationComment, ...] | None = None,
        defect_links: tuple[IssueDefectLink, ...] | None = None,
    ) -> IssueCollaborationRecord:
        event = CollaborationEvent(
            event_id=new_id("issue_event"),
            target_type="issue",
            target_id=record.fingerprint,
            action=action,
            created_at=utcnow(),
            created_by=actor.actor_id,
            session_source=session_source.strip(),
            audit_source=dict(audit_source or {}),
            payload=dict(payload),
        )
        return IssueCollaborationRecord(
            fingerprint=record.fingerprint,
            workflow_state=workflow_state,
            assignee_id=assignee_id,
            assignee_display_name=assignee_display_name,
            updated_at=event.created_at,
            updated_by=actor.actor_id,
            comments=tuple(comments if comments is not None else record.comments),
            events=tuple(list(record.events) + [event]),
            defect_links=tuple(defect_links if defect_links is not None else record.defect_links),
        )
