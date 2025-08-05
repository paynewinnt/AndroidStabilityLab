from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Sequence

from stability.domain import IssueCollaborationRecord, IssueDefectLink
from stability.domain.value_objects import new_id, utcnow


class DefectLinksMixin:
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
        audit_source: Mapping[str, Any] | None = None,
    ) -> IssueCollaborationRecord:
        actor, audit_payload = self._authorize_actor(
            actor_id=actor_id,
            actor_identity_id=actor_identity_id,
            permission="link_issue_defect",
            audit_source=audit_source,
        )
        normalized_system_key = system_key.strip()
        normalized_title = title.strip()
        if not normalized_system_key:
            raise ValueError("system_key is required.")
        if not normalized_title:
            raise ValueError("title is required.")
        record = self.get_issue_record(fingerprint)
        defect_link = IssueDefectLink(
            link_id=new_id("issue_defect"),
            fingerprint=record.fingerprint,
            system_key=normalized_system_key,
            title=normalized_title,
            status="requested",
            acceptable_for_close=False,
            sync_status="pending_create",
            created_at=utcnow(),
            created_by=actor.actor_id,
            session_source=session_source.strip(),
            audit_source=dict(audit_payload),
            metadata={
                "description": description.strip(),
                "team_key": team_key.strip(),
            },
        )
        updated = self._issue_record_with_event(
            record=record,
            action="defect_create",
            actor=actor,
            payload={
                "actor_identity_id": str(audit_payload.get("resolved_identity_id", "") or ""),
                "link_id": defect_link.link_id,
                "system_key": defect_link.system_key,
                "title": defect_link.title,
                "sync_status": defect_link.sync_status,
                "team_key": str(defect_link.metadata.get("team_key", "") or ""),
            },
            session_source=session_source,
            audit_source=audit_payload,
            workflow_state=record.workflow_state,
            assignee_id=record.assignee_id,
            assignee_display_name=record.assignee_display_name,
            defect_links=tuple(list(record.defect_links) + [defect_link]),
        )
        self._save_issue_record(updated)
        self._publish_event(
            event_type="issue.defect_create_requested",
            target_type="issue",
            target_id=updated.fingerprint,
            actor_id=actor.actor_id,
            session_source=session_source,
            audit_source=audit_payload,
            payload={
                "link_id": defect_link.link_id,
                "system_key": defect_link.system_key,
                "title": defect_link.title,
                "description": description.strip(),
                "team_key": team_key.strip(),
                "workflow_state": updated.workflow_state,
                "assignee_id": updated.assignee_id,
            },
        )
        return updated

    def link_issue_defect(
        self,
        *,
        fingerprint: str,
        actor_id: str,
        actor_identity_id: str = "",
        system_key: str,
        defect_id: str,
        title: str = "",
        url: str = "",
        status: str = "",
        acceptable_for_close: bool = False,
        session_source: str = "",
        audit_source: Mapping[str, Any] | None = None,
    ) -> IssueCollaborationRecord:
        actor, audit_payload = self._authorize_actor(
            actor_id=actor_id,
            actor_identity_id=actor_identity_id,
            permission="link_issue_defect",
            audit_source=audit_source,
        )
        normalized_system_key = system_key.strip()
        normalized_defect_id = defect_id.strip()
        if not normalized_system_key:
            raise ValueError("system_key is required.")
        if not normalized_defect_id:
            raise ValueError("defect_id is required.")
        record = self.get_issue_record(fingerprint)
        defect_links = list(record.defect_links)
        current_time = utcnow()
        replaced = False
        for index, item in enumerate(defect_links):
            if item.system_key == normalized_system_key and item.defect_id == normalized_defect_id:
                defect_links[index] = replace(
                    item,
                    title=title.strip() or item.title,
                    url=url.strip() or item.url,
                    status=status.strip() or item.status,
                    acceptable_for_close=bool(acceptable_for_close),
                    sync_status="linked",
                    synced_at=current_time,
                    synced_by=actor.actor_id,
                    session_source=session_source.strip() or item.session_source,
                    audit_source=dict(audit_payload),
                )
                replaced = True
                break
        if not replaced:
            defect_links.append(
                IssueDefectLink(
                    link_id=new_id("issue_defect"),
                    fingerprint=record.fingerprint,
                    system_key=normalized_system_key,
                    defect_id=normalized_defect_id,
                    title=title.strip(),
                    url=url.strip(),
                    status=status.strip(),
                    acceptable_for_close=bool(acceptable_for_close),
                    sync_status="linked",
                    created_at=current_time,
                    created_by=actor.actor_id,
                    synced_at=current_time,
                    synced_by=actor.actor_id,
                    session_source=session_source.strip(),
                    audit_source=dict(audit_payload),
                )
            )
        linked = next(item for item in defect_links if item.system_key == normalized_system_key and item.defect_id == normalized_defect_id)
        updated = self._issue_record_with_event(
            record=record,
            action="defect_link",
            actor=actor,
            payload={
                "actor_identity_id": str(audit_payload.get("resolved_identity_id", "") or ""),
                "link_id": linked.link_id,
                "system_key": linked.system_key,
                "defect_id": linked.defect_id,
                "status": linked.status,
                "acceptable_for_close": linked.acceptable_for_close,
            },
            session_source=session_source,
            audit_source=audit_payload,
            workflow_state=record.workflow_state,
            assignee_id=record.assignee_id,
            assignee_display_name=record.assignee_display_name,
            defect_links=tuple(defect_links),
        )
        self._save_issue_record(updated)
        self._publish_event(
            event_type="issue.defect_linked",
            target_type="issue",
            target_id=updated.fingerprint,
            actor_id=actor.actor_id,
            session_source=session_source,
            audit_source=audit_payload,
            payload={
                "link_id": linked.link_id,
                "system_key": linked.system_key,
                "defect_id": linked.defect_id,
                "title": linked.title,
                "url": linked.url,
                "status": linked.status,
                "acceptable_for_close": linked.acceptable_for_close,
                "sync_status": linked.sync_status,
            },
        )
        return updated

    def sync_issue_defect_status(
        self,
        *,
        fingerprint: str,
        actor_id: str,
        actor_identity_id: str = "",
        link_id: str = "",
        defect_id: str = "",
        system_key: str = "",
        status: str,
        acceptable_for_close: bool = False,
        url: str = "",
        session_source: str = "",
        audit_source: Mapping[str, Any] | None = None,
    ) -> IssueCollaborationRecord:
        actor, audit_payload = self._authorize_actor(
            actor_id=actor_id,
            actor_identity_id=actor_identity_id,
            permission="sync_issue_defect",
            audit_source=audit_source,
        )
        normalized_status = status.strip()
        if not normalized_status:
            raise ValueError("status is required.")
        record = self.get_issue_record(fingerprint)
        defect_links = list(record.defect_links)
        match_index = self._find_issue_defect_index(
            defect_links,
            link_id=link_id,
            system_key=system_key,
            defect_id=defect_id,
        )
        if match_index is None:
            raise ValueError("Matching issue defect link was not found.")
        current_time = utcnow()
        linked = defect_links[match_index]
        defect_links[match_index] = replace(
            linked,
            status=normalized_status,
            acceptable_for_close=bool(acceptable_for_close),
            url=url.strip() or linked.url,
            sync_status="status_synced",
            synced_at=current_time,
            synced_by=actor.actor_id,
            session_source=session_source.strip() or linked.session_source,
            audit_source=dict(audit_payload),
        )
        synced = defect_links[match_index]
        updated = self._issue_record_with_event(
            record=record,
            action="defect_sync",
            actor=actor,
            payload={
                "actor_identity_id": str(audit_payload.get("resolved_identity_id", "") or ""),
                "link_id": synced.link_id,
                "system_key": synced.system_key,
                "defect_id": synced.defect_id,
                "status": synced.status,
                "acceptable_for_close": synced.acceptable_for_close,
            },
            session_source=session_source,
            audit_source=audit_payload,
            workflow_state=record.workflow_state,
            assignee_id=record.assignee_id,
            assignee_display_name=record.assignee_display_name,
            defect_links=tuple(defect_links),
        )
        self._save_issue_record(updated)
        self._publish_event(
            event_type="issue.defect_status_synced",
            target_type="issue",
            target_id=updated.fingerprint,
            actor_id=actor.actor_id,
            session_source=session_source,
            audit_source=audit_payload,
            payload={
                "link_id": synced.link_id,
                "system_key": synced.system_key,
                "defect_id": synced.defect_id,
                "status": synced.status,
                "acceptable_for_close": synced.acceptable_for_close,
                "sync_status": synced.sync_status,
            },
        )
        return updated

    @staticmethod
    def _find_issue_defect_index(
        defect_links: Sequence[IssueDefectLink],
        *,
        link_id: str,
        system_key: str,
        defect_id: str,
    ) -> int | None:
        normalized_link_id = str(link_id or "").strip()
        normalized_system_key = str(system_key or "").strip()
        normalized_defect_id = str(defect_id or "").strip()
        for index, item in enumerate(defect_links):
            if normalized_link_id and item.link_id == normalized_link_id:
                return index
            if normalized_system_key and normalized_defect_id and item.system_key == normalized_system_key and item.defect_id == normalized_defect_id:
                return index
        return None
