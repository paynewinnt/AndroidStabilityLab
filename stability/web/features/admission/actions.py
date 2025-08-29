from __future__ import annotations

from typing import Any, Mapping


class AdmissionActionsMixin:
    def _handle_issue_assign(
        self,
        payload: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "collaboration_service", None)
        if service is None or not hasattr(service, "assign_issue"):
            raise ValueError("Collaboration service is unavailable.")
        current_actor = dict(request_context.get("current_actor", {}) or {})
        record = service.assign_issue(
            fingerprint=self._required_form_value(payload, "fingerprint"),
            actor_id=str(current_actor.get("actor_id", "") or ""),
            actor_identity_id=str(current_actor.get("identity_id", "") or ""),
            assignee_id=self._required_form_value(payload, "assignee_id"),
            session_source=str(current_actor.get("session_source", "") or ""),
            audit_source=dict(request_context.get("audit_source", {}) or {}),
        )
        return {
            "ok": True,
            "action": "assign_issue",
            "actor_id": str(current_actor.get("actor_id", "") or ""),
            "identity_id": str(current_actor.get("identity_id", "") or ""),
            "fingerprint": str(getattr(record, "fingerprint", "") or ""),
            **self._issue_collaboration_payload(record),
        }

    def _handle_issue_comment(
        self,
        payload: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "collaboration_service", None)
        if service is None or not hasattr(service, "comment_issue"):
            raise ValueError("Collaboration service is unavailable.")
        current_actor = dict(request_context.get("current_actor", {}) or {})
        record = service.comment_issue(
            fingerprint=self._required_form_value(payload, "fingerprint"),
            actor_id=str(current_actor.get("actor_id", "") or ""),
            actor_identity_id=str(current_actor.get("identity_id", "") or ""),
            body=self._required_form_value(payload, "body"),
            session_source=str(current_actor.get("session_source", "") or ""),
            audit_source=dict(request_context.get("audit_source", {}) or {}),
        )
        return {
            "ok": True,
            "action": "comment_issue",
            "actor_id": str(current_actor.get("actor_id", "") or ""),
            "identity_id": str(current_actor.get("identity_id", "") or ""),
            "fingerprint": str(getattr(record, "fingerprint", "") or ""),
            **self._issue_collaboration_payload(record),
        }

    def _handle_issue_transition(
        self,
        payload: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "collaboration_service", None)
        if service is None or not hasattr(service, "transition_issue"):
            raise ValueError("Collaboration service is unavailable.")
        current_actor = dict(request_context.get("current_actor", {}) or {})
        record = service.transition_issue(
            fingerprint=self._required_form_value(payload, "fingerprint"),
            actor_id=str(current_actor.get("actor_id", "") or ""),
            actor_identity_id=str(current_actor.get("identity_id", "") or ""),
            workflow_state=self._required_form_value(payload, "workflow_state"),
            reason=self._form_value(payload, "reason"),
            session_source=str(current_actor.get("session_source", "") or ""),
            audit_source=dict(request_context.get("audit_source", {}) or {}),
        )
        return {
            "ok": True,
            "action": "transition_issue",
            "actor_id": str(current_actor.get("actor_id", "") or ""),
            "identity_id": str(current_actor.get("identity_id", "") or ""),
            "fingerprint": str(getattr(record, "fingerprint", "") or ""),
            **self._issue_collaboration_payload(record),
        }

    def _handle_issue_create_defect(
        self,
        payload: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "collaboration_service", None)
        if service is None or not hasattr(service, "create_issue_defect"):
            raise ValueError("Collaboration service is unavailable.")
        current_actor = dict(request_context.get("current_actor", {}) or {})
        record = service.create_issue_defect(
            fingerprint=self._required_form_value(payload, "fingerprint"),
            actor_id=str(current_actor.get("actor_id", "") or ""),
            actor_identity_id=str(current_actor.get("identity_id", "") or ""),
            system_key=self._required_form_value(payload, "system_key"),
            title=self._required_form_value(payload, "title"),
            description=self._form_value(payload, "description"),
            team_key=self._form_value(payload, "team_key"),
            session_source=str(current_actor.get("session_source", "") or ""),
            audit_source=dict(request_context.get("audit_source", {}) or {}),
        )
        return {
            "ok": True,
            "action": "create_issue_defect",
            "actor_id": str(current_actor.get("actor_id", "") or ""),
            "identity_id": str(current_actor.get("identity_id", "") or ""),
            "fingerprint": str(getattr(record, "fingerprint", "") or ""),
            **self._issue_collaboration_payload(record),
        }

    def _handle_issue_sync_defect(
        self,
        payload: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "collaboration_service", None)
        if service is None or not hasattr(service, "sync_issue_defect_status"):
            raise ValueError("Collaboration service is unavailable.")
        current_actor = dict(request_context.get("current_actor", {}) or {})
        record = service.sync_issue_defect_status(
            fingerprint=self._required_form_value(payload, "fingerprint"),
            actor_id=str(current_actor.get("actor_id", "") or ""),
            actor_identity_id=str(current_actor.get("identity_id", "") or ""),
            link_id=self._form_value(payload, "link_id"),
            system_key=self._form_value(payload, "system_key"),
            defect_id=self._form_value(payload, "defect_id"),
            status=self._required_form_value(payload, "status"),
            acceptable_for_close=self._form_bool(payload, "acceptable_for_close", default=False),
            url=self._form_value(payload, "url"),
            session_source=str(current_actor.get("session_source", "") or ""),
            audit_source=dict(request_context.get("audit_source", {}) or {}),
        )
        return {
            "ok": True,
            "action": "sync_issue_defect",
            "actor_id": str(current_actor.get("actor_id", "") or ""),
            "identity_id": str(current_actor.get("identity_id", "") or ""),
            "fingerprint": str(getattr(record, "fingerprint", "") or ""),
            **self._issue_collaboration_payload(record),
        }

    def _handle_admission_override(
        self,
        payload: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "quality_gate_service", None)
        if service is None or not hasattr(service, "record_override"):
            raise ValueError("Quality gate service is unavailable.")
        baseline_key = self._required_form_value(payload, "baseline_key")
        current_actor = dict(request_context.get("current_actor", {}) or {})
        collaboration_service = getattr(self._bundle, "collaboration_service", None)
        audit_source = dict(request_context.get("audit_source", {}) or {})
        if collaboration_service is not None and hasattr(collaboration_service, "authorize_action"):
            authorization = collaboration_service.authorize_action(
                actor_id=str(current_actor.get("actor_id", "") or ""),
                actor_identity_id=str(current_actor.get("identity_id", "") or ""),
                permission="override_gate",
                audit_source=audit_source,
            )
            audit_source = dict(authorization.get("audit_source", {}) or audit_source)
        override = service.record_override(
            baseline_key=baseline_key,
            final_decision=self._required_form_value(payload, "final_decision"),
            reason=self._required_form_value(payload, "reason"),
            created_by=str(current_actor.get("actor_id", "") or ""),
            session_source=str(current_actor.get("session_source", "") or ""),
            audit_source=audit_source,
            comment=self._form_value(payload, "comment"),
            evidence_paths=tuple(
                item.strip()
                for item in self._form_value(payload, "evidence_paths").split(",")
                if item.strip()
            ),
        )
        gate = self._quality_gate_detail_payload(baseline_key)
        return {
            "ok": True,
            "action": "override_admission",
            "baseline_key": baseline_key,
            "identity_id": str(current_actor.get("identity_id", "") or ""),
            "override": {
                "override_id": str(getattr(override, "override_id", "") or ""),
                "created_by": str(getattr(override, "created_by", "") or ""),
                "reason": str(getattr(override, "reason", "") or ""),
                "comment": str(getattr(override, "comment", "") or ""),
            },
            "automatic_decision": str(gate.get("automatic_decision", "") or getattr(override, "automatic_decision", "")),
            "final_decision": str(gate.get("final_decision", "") or getattr(override, "final_decision", "")),
        }

    def _handle_admission_assign(
        self,
        payload: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "collaboration_service", None)
        if service is None or not hasattr(service, "assign_admission_case"):
            raise ValueError("Collaboration service is unavailable.")
        current_actor = dict(request_context.get("current_actor", {}) or {})
        record = service.assign_admission_case(
            baseline_key=self._required_form_value(payload, "baseline_key"),
            actor_id=str(current_actor.get("actor_id", "") or ""),
            actor_identity_id=str(current_actor.get("identity_id", "") or ""),
            assignee_id=self._required_form_value(payload, "assignee_id"),
            session_source=str(current_actor.get("session_source", "") or ""),
            audit_source=dict(request_context.get("audit_source", {}) or {}),
        )
        return {
            "ok": True,
            "action": "assign_admission_case",
            "actor_id": str(current_actor.get("actor_id", "") or ""),
            "identity_id": str(current_actor.get("identity_id", "") or ""),
            "baseline_key": str(getattr(record, "baseline_key", "") or ""),
            **self._admission_collaboration_payload(record),
        }

    def _handle_admission_comment(
        self,
        payload: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "collaboration_service", None)
        if service is None or not hasattr(service, "comment_admission_case"):
            raise ValueError("Collaboration service is unavailable.")
        current_actor = dict(request_context.get("current_actor", {}) or {})
        record = service.comment_admission_case(
            baseline_key=self._required_form_value(payload, "baseline_key"),
            actor_id=str(current_actor.get("actor_id", "") or ""),
            actor_identity_id=str(current_actor.get("identity_id", "") or ""),
            body=self._required_form_value(payload, "body"),
            session_source=str(current_actor.get("session_source", "") or ""),
            audit_source=dict(request_context.get("audit_source", {}) or {}),
        )
        return {
            "ok": True,
            "action": "comment_admission_case",
            "actor_id": str(current_actor.get("actor_id", "") or ""),
            "identity_id": str(current_actor.get("identity_id", "") or ""),
            "baseline_key": str(getattr(record, "baseline_key", "") or ""),
            **self._admission_collaboration_payload(record),
        }

    def _handle_admission_transition(
        self,
        payload: dict[str, list[str]],
        *,
        request_context: Mapping[str, Any],
    ) -> dict[str, Any]:
        service = getattr(self._bundle, "collaboration_service", None)
        if service is None or not hasattr(service, "transition_admission_case"):
            raise ValueError("Collaboration service is unavailable.")
        current_actor = dict(request_context.get("current_actor", {}) or {})
        record = service.transition_admission_case(
            baseline_key=self._required_form_value(payload, "baseline_key"),
            actor_id=str(current_actor.get("actor_id", "") or ""),
            actor_identity_id=str(current_actor.get("identity_id", "") or ""),
            workflow_state=self._required_form_value(payload, "workflow_state"),
            reason=self._form_value(payload, "reason"),
            session_source=str(current_actor.get("session_source", "") or ""),
            audit_source=dict(request_context.get("audit_source", {}) or {}),
        )
        return {
            "ok": True,
            "action": "transition_admission_case",
            "actor_id": str(current_actor.get("actor_id", "") or ""),
            "identity_id": str(current_actor.get("identity_id", "") or ""),
            "baseline_key": str(getattr(record, "baseline_key", "") or ""),
            **self._admission_collaboration_payload(record),
        }


__all__ = ["AdmissionActionsMixin"]
