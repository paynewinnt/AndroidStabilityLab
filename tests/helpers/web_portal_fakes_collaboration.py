from __future__ import annotations

from types import SimpleNamespace


class _FakeCollaborationService:
    def __init__(self) -> None:
        self._outbox = None
        self._actors = {
            "tester": SimpleNamespace(actor_id="tester", display_name="Tester", role_key="tester", permissions=("assign_issue", "comment_issue", "transition_issue", "assign_admission_case", "comment_admission_case", "transition_admission_case", "override_gate")),
            "developer": SimpleNamespace(actor_id="developer", display_name="Developer", role_key="developer", permissions=("comment_issue", "transition_issue", "comment_admission_case")),
            "admin": SimpleNamespace(actor_id="admin", display_name="Admin", role_key="admin", permissions=("assign_issue", "comment_issue", "transition_issue", "assign_admission_case", "comment_admission_case", "transition_admission_case", "override_gate")),
        }
        self._issues: dict[str, SimpleNamespace] = {}
        self._admissions: dict[str, SimpleNamespace] = {}

    def attach_outbox(self, outbox_service) -> None:
        self._outbox = outbox_service

    def list_actors(self):
        return tuple(self._actors.values())

    def get_actor(self, actor_id: str):
        key = str(actor_id or "").strip()
        if not key or key not in self._actors:
            raise ValueError(actor_id)
        return self._actors[key]

    def actor_session_id(self, actor_id: str, *, auth_mechanism: str = "", session_token: str = ""):
        token = session_token or f"{auth_mechanism}:{actor_id}"
        return f"asl.session_id.v1:{token.replace(':', '_')}"

    def resolve_sso_actor(
        self,
        claims,
        *,
        auth_mechanism: str = "sso_header",
        session_source: str = "header:trusted_sso",
        ttl_seconds=None,
    ):
        del ttl_seconds
        provider = str(dict(claims or {}).get("provider", "") or "").strip()
        subject = str(dict(claims or {}).get("external_subject_id", "") or "").strip()
        if not provider or not subject:
            raise ValueError("provider and external_subject_id are required")
        actor_id = subject if subject in self._actors else str(dict(claims or {}).get("role_key", "") or "tester")
        if actor_id not in self._actors:
            actor_id = "tester"
        actor = self._actors[actor_id]
        organization_id = str(dict(claims or {}).get("organization_id", "") or "").strip()
        team_ids = list(dict(claims or {}).get("team_ids", []) or [])
        role_claims = list(dict(claims or {}).get("role_claims", []) or [])
        external_identity_id = f"asl.external_identity.v1:{provider}:{subject}"
        session_id = f"asl.session_id.v1:sso_header_{provider}_{subject}"
        identity = SimpleNamespace(
            identity_id=external_identity_id,
            actor_id=actor.actor_id,
            provider=provider,
            external_subject_id=subject,
            external_email=str(dict(claims or {}).get("external_email", "") or ""),
            organization_id=organization_id,
            team_ids=tuple(team_ids),
            role_claims=tuple(role_claims),
            auth_mechanism=auth_mechanism,
            session_id=session_id,
            session_source=session_source,
        )
        session = SimpleNamespace(
            session_id=session_id,
            session_token="",
            auth_mechanism=auth_mechanism,
            session_source=session_source,
            expires_at=None,
        )
        return {
            "actor": actor,
            "identity": identity,
            "session": session,
            "session_source": session_source,
            "audit_source": {
                "auth_mechanism": auth_mechanism,
                "identity_provider": provider,
                "external_identity_id": external_identity_id,
                "external_subject_id": subject,
                "external_email": identity.external_email,
                "organization_id": organization_id,
                "team_ids": team_ids,
                "role_claims": role_claims,
                "resolved_session_id": session_id,
            },
        }

    def get_issue_record(self, fingerprint: str):
        return self._issues.get(
            fingerprint,
            SimpleNamespace(
                fingerprint=fingerprint,
                workflow_state="new",
                assignee_id="",
                assignee_display_name="",
                updated_at=None,
                updated_by="",
                comments=(),
                events=(),
                defect_links=(),
            ),
        )

    def get_admission_case_record(self, baseline_key: str):
        return self._admissions.get(
            baseline_key,
            SimpleNamespace(
                baseline_key=baseline_key,
                workflow_state="new",
                assignee_id="",
                assignee_display_name="",
                final_reviewer_id="",
                final_reviewer_display_name="",
                updated_at=None,
                updated_by="",
                comments=(),
                events=(),
            ),
        )

    def assign_issue(
        self,
        *,
        fingerprint: str,
        actor_id: str,
        actor_identity_id: str = "",
        assignee_id: str,
        session_source: str = "",
        audit_source=None,
    ):
        assignee = self._actors[assignee_id]
        record = self.get_issue_record(fingerprint)
        audit_payload = {
            **dict(audit_source or {}),
            "resolved_identity_id": actor_identity_id or dict(audit_source or {}).get("resolved_identity_id", ""),
            "identity_binding_status": "verified" if actor_identity_id else "service_backfilled",
        }
        event = SimpleNamespace(event_id="event_assign", action="assign", created_at=None, created_by=actor_id, session_source=session_source, audit_source=audit_payload, payload={"assignee_id": assignee_id})
        updated = SimpleNamespace(
            fingerprint=fingerprint,
            workflow_state="assigned",
            assignee_id=assignee_id,
            assignee_display_name=assignee.display_name,
            updated_at=None,
            updated_by=actor_id,
            comments=tuple(record.comments),
            events=tuple(list(record.events) + [event]),
        )
        self._issues[fingerprint] = updated
        if self._outbox is not None:
            self._outbox.publish_event(
                event_type="issue.assigned",
                target_type="issue",
                target_id=fingerprint,
                created_by=actor_id,
                session_source=session_source,
                audit_source=audit_payload,
                payload={"assignee_id": assignee_id},
            )
        return updated

    def create_issue_defect(
        self,
        *,
        fingerprint: str,
        actor_id: str,
        actor_identity_id: str = "",
        system_key: str,
        title: str,
        description: str = "",
        team_key: str = "",
        session_source: str = "",
        audit_source=None,
    ):
        record = self.get_issue_record(fingerprint)
        audit_payload = {
            **dict(audit_source or {}),
            "resolved_identity_id": actor_identity_id or dict(audit_source or {}).get("resolved_identity_id", ""),
            "identity_binding_status": "verified" if actor_identity_id else "service_backfilled",
        }
        defect = SimpleNamespace(
            link_id="defect_link_1",
            system_key=system_key,
            defect_id="",
            title=title,
            url="",
            status="requested",
            acceptable_for_close=False,
            sync_status="pending_create",
            metadata={"description": description, "team_key": team_key},
        )
        event = SimpleNamespace(
            event_id="event_defect_create",
            action="defect_create",
            created_at=None,
            created_by=actor_id,
            session_source=session_source,
            audit_source=audit_payload,
            payload={"system_key": system_key, "title": title},
        )
        updated = SimpleNamespace(
            fingerprint=fingerprint,
            workflow_state=record.workflow_state,
            assignee_id=record.assignee_id,
            assignee_display_name=record.assignee_display_name,
            updated_at=None,
            updated_by=actor_id,
            comments=tuple(record.comments),
            events=tuple(list(record.events) + [event]),
            defect_links=(defect,),
        )
        self._issues[fingerprint] = updated
        if self._outbox is not None:
            self._outbox.publish_event(
                event_type="issue.defect_create_requested",
                target_type="issue",
                target_id=fingerprint,
                created_by=actor_id,
                session_source=session_source,
                audit_source=audit_payload,
                payload={"system_key": system_key, "title": title},
            )
        return updated

    def sync_issue_defect_status(
        self,
        *,
        fingerprint: str,
        actor_id: str,
        actor_identity_id: str = "",
        link_id: str = "",
        system_key: str = "",
        defect_id: str = "",
        status: str,
        acceptable_for_close: bool = False,
        url: str = "",
        session_source: str = "",
        audit_source=None,
    ):
        record = self.get_issue_record(fingerprint)
        existing = list(getattr(record, "defect_links", ()) or ())
        defect = existing[0] if existing else SimpleNamespace(link_id=link_id or "defect_link_1", system_key=system_key, title="")
        updated_defect = SimpleNamespace(
            link_id=link_id or getattr(defect, "link_id", "defect_link_1"),
            system_key=system_key or getattr(defect, "system_key", ""),
            defect_id=defect_id,
            title=getattr(defect, "title", ""),
            url=url,
            status=status,
            acceptable_for_close=acceptable_for_close,
            sync_status="status_synced",
            metadata=dict(getattr(defect, "metadata", {}) or {}),
        )
        audit_payload = {
            **dict(audit_source or {}),
            "resolved_identity_id": actor_identity_id or dict(audit_source or {}).get("resolved_identity_id", ""),
            "identity_binding_status": "verified" if actor_identity_id else "service_backfilled",
        }
        event = SimpleNamespace(
            event_id="event_defect_sync",
            action="defect_sync",
            created_at=None,
            created_by=actor_id,
            session_source=session_source,
            audit_source=audit_payload,
            payload={"system_key": updated_defect.system_key, "status": status, "defect_id": defect_id},
        )
        updated = SimpleNamespace(
            fingerprint=fingerprint,
            workflow_state=record.workflow_state,
            assignee_id=record.assignee_id,
            assignee_display_name=record.assignee_display_name,
            updated_at=None,
            updated_by=actor_id,
            comments=tuple(record.comments),
            events=tuple(list(record.events) + [event]),
            defect_links=(updated_defect,),
        )
        self._issues[fingerprint] = updated
        if self._outbox is not None:
            self._outbox.publish_event(
                event_type="issue.defect_status_synced",
                target_type="issue",
                target_id=fingerprint,
                created_by=actor_id,
                session_source=session_source,
                audit_source=audit_payload,
                payload={"system_key": updated_defect.system_key, "status": status, "defect_id": defect_id},
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
        audit_source=None,
    ):
        record = self.get_issue_record(fingerprint)
        audit_payload = {
            **dict(audit_source or {}),
            "resolved_identity_id": actor_identity_id or dict(audit_source or {}).get("resolved_identity_id", ""),
            "identity_binding_status": "verified" if actor_identity_id else "service_backfilled",
        }
        comment = SimpleNamespace(comment_id="comment_1", body=body, created_by=actor_id, created_at=None, session_source=session_source, audit_source=audit_payload)
        event = SimpleNamespace(event_id="event_comment", action="comment", created_at=None, created_by=actor_id, session_source=session_source, audit_source=audit_payload, payload={"comment_id": "comment_1"})
        updated = SimpleNamespace(
            fingerprint=fingerprint,
            workflow_state=record.workflow_state,
            assignee_id=record.assignee_id,
            assignee_display_name=record.assignee_display_name,
            updated_at=None,
            updated_by=actor_id,
            comments=tuple(list(record.comments) + [comment]),
            events=tuple(list(record.events) + [event]),
        )
        self._issues[fingerprint] = updated
        if self._outbox is not None:
            self._outbox.publish_event(
                event_type="issue.commented",
                target_type="issue",
                target_id=fingerprint,
                created_by=actor_id,
                session_source=session_source,
                audit_source=audit_payload,
                payload={"comment_id": "comment_1"},
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
        audit_source=None,
    ):
        record = self.get_issue_record(fingerprint)
        audit_payload = {
            **dict(audit_source or {}),
            "resolved_identity_id": actor_identity_id or dict(audit_source or {}).get("resolved_identity_id", ""),
            "identity_binding_status": "verified" if actor_identity_id else "service_backfilled",
        }
        event = SimpleNamespace(event_id="event_transition", action="transition", created_at=None, created_by=actor_id, session_source=session_source, audit_source=audit_payload, payload={"workflow_state": workflow_state, "reason": reason})
        updated = SimpleNamespace(
            fingerprint=fingerprint,
            workflow_state=workflow_state,
            assignee_id=record.assignee_id,
            assignee_display_name=record.assignee_display_name,
            updated_at=None,
            updated_by=actor_id,
            comments=tuple(record.comments),
            events=tuple(list(record.events) + [event]),
        )
        self._issues[fingerprint] = updated
        if self._outbox is not None:
            self._outbox.publish_event(
                event_type="issue.transitioned",
                target_type="issue",
                target_id=fingerprint,
                created_by=actor_id,
                session_source=session_source,
                audit_source=audit_payload,
                payload={"workflow_state": workflow_state, "reason": reason},
            )
        return updated

    def assign_admission_case(
        self,
        *,
        baseline_key: str,
        actor_id: str,
        actor_identity_id: str = "",
        assignee_id: str,
        session_source: str = "",
        audit_source=None,
    ):
        assignee = self._actors[assignee_id]
        record = self.get_admission_case_record(baseline_key)
        audit_payload = {
            **dict(audit_source or {}),
            "resolved_identity_id": actor_identity_id or dict(audit_source or {}).get("resolved_identity_id", ""),
            "identity_binding_status": "verified" if actor_identity_id else "service_backfilled",
        }
        event = SimpleNamespace(event_id="admission_assign", action="assign", created_at=None, created_by=actor_id, session_source=session_source, audit_source=audit_payload, payload={"assignee_id": assignee_id})
        updated = SimpleNamespace(
            baseline_key=baseline_key,
            workflow_state="assigned",
            assignee_id=assignee_id,
            assignee_display_name=assignee.display_name,
            final_reviewer_id=record.final_reviewer_id,
            final_reviewer_display_name=record.final_reviewer_display_name,
            updated_at=None,
            updated_by=actor_id,
            comments=tuple(record.comments),
            events=tuple(list(record.events) + [event]),
        )
        self._admissions[baseline_key] = updated
        if self._outbox is not None:
            self._outbox.publish_event(
                event_type="admission_case.assigned",
                target_type="admission_case",
                target_id=baseline_key,
                created_by=actor_id,
                session_source=session_source,
                audit_source=audit_payload,
                payload={"assignee_id": assignee_id},
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
        audit_source=None,
    ):
        record = self.get_admission_case_record(baseline_key)
        audit_payload = {
            **dict(audit_source or {}),
            "resolved_identity_id": actor_identity_id or dict(audit_source or {}).get("resolved_identity_id", ""),
            "identity_binding_status": "verified" if actor_identity_id else "service_backfilled",
        }
        comment = SimpleNamespace(comment_id="admission_comment_1", body=body, created_by=actor_id, created_at=None, session_source=session_source, audit_source=audit_payload)
        event = SimpleNamespace(event_id="admission_comment", action="comment", created_at=None, created_by=actor_id, session_source=session_source, audit_source=audit_payload, payload={"comment_id": "admission_comment_1"})
        updated = SimpleNamespace(
            baseline_key=baseline_key,
            workflow_state=record.workflow_state,
            assignee_id=record.assignee_id,
            assignee_display_name=record.assignee_display_name,
            final_reviewer_id=record.final_reviewer_id,
            final_reviewer_display_name=record.final_reviewer_display_name,
            updated_at=None,
            updated_by=actor_id,
            comments=tuple(list(record.comments) + [comment]),
            events=tuple(list(record.events) + [event]),
        )
        self._admissions[baseline_key] = updated
        if self._outbox is not None:
            self._outbox.publish_event(
                event_type="admission_case.commented",
                target_type="admission_case",
                target_id=baseline_key,
                created_by=actor_id,
                session_source=session_source,
                audit_source=audit_payload,
                payload={"comment_id": "admission_comment_1"},
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
        audit_source=None,
    ):
        record = self.get_admission_case_record(baseline_key)
        audit_payload = {
            **dict(audit_source or {}),
            "resolved_identity_id": actor_identity_id or dict(audit_source or {}).get("resolved_identity_id", ""),
            "identity_binding_status": "verified" if actor_identity_id else "service_backfilled",
        }
        event = SimpleNamespace(event_id="admission_transition", action="transition", created_at=None, created_by=actor_id, session_source=session_source, audit_source=audit_payload, payload={"workflow_state": workflow_state, "reason": reason})
        updated = SimpleNamespace(
            baseline_key=baseline_key,
            workflow_state=workflow_state,
            assignee_id=record.assignee_id,
            assignee_display_name=record.assignee_display_name,
            final_reviewer_id=actor_id if workflow_state in {"pending_confirmation", "approved_with_risk", "approved", "rejected"} else record.final_reviewer_id,
            final_reviewer_display_name=self._actors[actor_id].display_name if workflow_state in {"pending_confirmation", "approved_with_risk", "approved", "rejected"} else record.final_reviewer_display_name,
            updated_at=None,
            updated_by=actor_id,
            comments=tuple(record.comments),
            events=tuple(list(record.events) + [event]),
        )
        self._admissions[baseline_key] = updated
        if self._outbox is not None:
            self._outbox.publish_event(
                event_type="admission_case.transitioned",
                target_type="admission_case",
                target_id=baseline_key,
                created_by=actor_id,
                session_source=session_source,
                audit_source=audit_payload,
                payload={"workflow_state": workflow_state, "reason": reason},
            )
        return updated


