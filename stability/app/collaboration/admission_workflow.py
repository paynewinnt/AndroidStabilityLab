from __future__ import annotations

from typing import Any, Mapping

from stability.domain import (
    AdmissionCaseCollaborationRecord,
    CollaborationActor,
    CollaborationComment,
    CollaborationEvent,
)
from stability.domain.value_objects import new_id, utcnow


class AdmissionWorkflowMixin:
    def get_admission_case_record(self, baseline_key: str) -> AdmissionCaseCollaborationRecord:
        key = baseline_key.strip()
        if not key:
            raise ValueError("baseline_key is required.")
        registry = self._load_admission_case_registry()
        payload = registry.get(key)
        if not isinstance(payload, Mapping):
            return AdmissionCaseCollaborationRecord(baseline_key=key, workflow_state="new")
        return self._admission_case_record_from_payload(key, payload)

    def assign_admission_case(
        self,
        *,
        baseline_key: str,
        actor_id: str,
        actor_identity_id: str = "",
        assignee_id: str,
        session_source: str = "",
        audit_source: Mapping[str, Any] | None = None,
    ) -> AdmissionCaseCollaborationRecord:
        actor, audit_payload = self._authorize_actor(
            actor_id=actor_id,
            actor_identity_id=actor_identity_id,
            permission="assign_admission_case",
            audit_source=audit_source,
        )
        assignee = self.get_actor(assignee_id)
        record = self.get_admission_case_record(baseline_key)
        updated = self._admission_record_with_event(
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
            final_reviewer_id=record.final_reviewer_id,
            final_reviewer_display_name=record.final_reviewer_display_name,
        )
        self._save_admission_case_record(updated)
        self._sync_admission_case_workflow(
            baseline_key=baseline_key,
            workflow_state=updated.workflow_state,
            assignee_id=updated.assignee_id,
            assignee_display_name=updated.assignee_display_name,
            final_reviewer_id=updated.final_reviewer_id,
            final_reviewer_display_name=updated.final_reviewer_display_name,
            action="assign",
            changed_by=actor.actor_id,
            changed_by_display_name=actor.display_name,
            reason="Admission case assigned.",
            audit_source=audit_payload,
        )
        self._publish_event(
            event_type="admission_case.assigned",
            target_type="admission_case",
            target_id=updated.baseline_key,
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

    def comment_admission_case(
        self,
        *,
        baseline_key: str,
        actor_id: str,
        actor_identity_id: str = "",
        body: str,
        session_source: str = "",
        audit_source: Mapping[str, Any] | None = None,
    ) -> AdmissionCaseCollaborationRecord:
        actor, audit_payload = self._authorize_actor(
            actor_id=actor_id,
            actor_identity_id=actor_identity_id,
            permission="comment_admission_case",
            audit_source=audit_source,
        )
        message = body.strip()
        if not message:
            raise ValueError("Comment body is required.")
        record = self.get_admission_case_record(baseline_key)
        comment = CollaborationComment(
            comment_id=new_id("comment"),
            target_type="admission_case",
            target_id=record.baseline_key,
            body=message,
            created_at=utcnow(),
            created_by=actor.actor_id,
            session_source=session_source.strip(),
            audit_source=audit_payload,
        )
        updated = self._admission_record_with_event(
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
            final_reviewer_id=record.final_reviewer_id,
            final_reviewer_display_name=record.final_reviewer_display_name,
            comments=tuple(list(record.comments) + [comment]),
        )
        self._save_admission_case_record(updated)
        self._publish_event(
            event_type="admission_case.commented",
            target_type="admission_case",
            target_id=updated.baseline_key,
            actor_id=actor.actor_id,
            session_source=session_source,
            audit_source=audit_payload,
            payload={
                "comment_id": comment.comment_id,
                "actor_identity_id": str(audit_payload.get("resolved_identity_id", "") or ""),
            },
        )
        return updated

    def transition_admission_case(
        self,
        *,
        baseline_key: str,
        actor_id: str,
        actor_identity_id: str = "",
        workflow_state: str,
        reason: str = "",
        session_source: str = "",
        audit_source: Mapping[str, Any] | None = None,
    ) -> AdmissionCaseCollaborationRecord:
        actor, audit_payload = self._authorize_actor(
            actor_id=actor_id,
            actor_identity_id=actor_identity_id,
            permission="transition_admission_case",
            audit_source=audit_source,
        )
        target_state = workflow_state.strip()
        if target_state not in self._allowed_admission_states:
            raise ValueError(f"Unsupported workflow_state: {target_state}")
        record = self.get_admission_case_record(baseline_key)
        final_reviewer_id = record.final_reviewer_id
        final_reviewer_display_name = record.final_reviewer_display_name
        if target_state in {"pending_confirmation", "approved_with_risk", "approved", "rejected"}:
            final_reviewer_id = actor.actor_id
            final_reviewer_display_name = actor.display_name
        updated = self._admission_record_with_event(
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
            final_reviewer_id=final_reviewer_id,
            final_reviewer_display_name=final_reviewer_display_name,
        )
        self._save_admission_case_record(updated)
        self._sync_admission_case_workflow(
            baseline_key=baseline_key,
            workflow_state=updated.workflow_state,
            assignee_id=updated.assignee_id,
            assignee_display_name=updated.assignee_display_name,
            final_reviewer_id=updated.final_reviewer_id,
            final_reviewer_display_name=updated.final_reviewer_display_name,
            action="transition",
            changed_by=actor.actor_id,
            changed_by_display_name=actor.display_name,
            reason=reason.strip(),
            audit_source=audit_payload,
        )
        self._publish_event(
            event_type="admission_case.transitioned",
            target_type="admission_case",
            target_id=updated.baseline_key,
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

    def _admission_record_with_event(
        self,
        *,
        record: AdmissionCaseCollaborationRecord,
        action: str,
        actor: CollaborationActor,
        payload: Mapping[str, Any],
        session_source: str,
        audit_source: Mapping[str, Any] | None,
        workflow_state: str,
        assignee_id: str,
        assignee_display_name: str,
        final_reviewer_id: str,
        final_reviewer_display_name: str,
        comments: tuple[CollaborationComment, ...] | None = None,
    ) -> AdmissionCaseCollaborationRecord:
        event = CollaborationEvent(
            event_id=new_id("admission_event"),
            target_type="admission_case",
            target_id=record.baseline_key,
            action=action,
            created_at=utcnow(),
            created_by=actor.actor_id,
            session_source=session_source.strip(),
            audit_source=dict(audit_source or {}),
            payload=dict(payload),
        )
        return AdmissionCaseCollaborationRecord(
            baseline_key=record.baseline_key,
            workflow_state=workflow_state,
            assignee_id=assignee_id,
            assignee_display_name=assignee_display_name,
            final_reviewer_id=final_reviewer_id,
            final_reviewer_display_name=final_reviewer_display_name,
            updated_at=event.created_at,
            updated_by=actor.actor_id,
            comments=tuple(comments if comments is not None else record.comments),
            events=tuple(list(record.events) + [event]),
        )

    def _sync_admission_case_workflow(
        self,
        *,
        baseline_key: str,
        workflow_state: str,
        assignee_id: str,
        assignee_display_name: str,
        final_reviewer_id: str,
        final_reviewer_display_name: str,
        action: str,
        changed_by: str,
        changed_by_display_name: str,
        reason: str,
        audit_source: Mapping[str, Any] | None,
    ) -> None:
        service = self._admission_case_service
        if service is None or not hasattr(service, "update_case_collaboration"):
            return
        service.update_case_collaboration(
            baseline_key,
            status=workflow_state,
            assignee_id=assignee_id,
            assignee_display_name=assignee_display_name,
            final_reviewer_id=final_reviewer_id,
            final_reviewer_display_name=final_reviewer_display_name,
            action=action,
            changed_by=changed_by,
            changed_by_display_name=changed_by_display_name,
            reason=reason,
            audit_source=dict(audit_source or {}),
        )
