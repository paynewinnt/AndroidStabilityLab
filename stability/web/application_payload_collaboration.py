from __future__ import annotations

from .application_common import *


class ApplicationPayloadCollaborationMixin:
    def _device_summaries(self) -> list[dict[str, Any]]:
        device_service = getattr(self._bundle, "device_service", None)
        if device_service is None:
            return []
        return list(device_service.list_device_summaries())

    def _task_summaries(self, *, limit: int, include_archived: bool = False) -> list[dict[str, Any]]:
        task_service = getattr(self._bundle, "task_service", None)
        if task_service is None:
            return []
        try:
            items = list(task_service.list_task_summaries(include_archived=include_archived))
        except TypeError:
            items = list(task_service.list_task_summaries())
            if not include_archived:
                items = [
                    item
                    for item in items
                    if not bool(
                        dict(item.get("metadata", {}) or {}).get("archived")
                        or str(dict(item.get("metadata", {}) or {}).get("status", "") or "").lower() == "archived"
                        or item.get("archived")
                    )
                ]
        if limit <= 0:
            return items
        return items[:limit]

    def _run_summaries(self, *, limit: int) -> list[dict[str, Any]]:
        service = getattr(self._bundle, "run_history_service", None)
        if service is None:
            return []
        return list(service.list_runs(limit=limit))

    def _issue_summaries(self, *, limit: int) -> list[dict[str, Any]]:
        service = getattr(self._bundle, "analysis_service", None)
        if service is None:
            return []
        collaboration_service = getattr(self._bundle, "collaboration_service", None)
        attribution_service = getattr(self._bundle, "attribution_service", None)
        items = service.list_top_issues(limit=limit)
        payloads: list[dict[str, Any]] = []
        for item in items:
            payload = {
                "fingerprint": item.fingerprint.value,
                "rule_version": item.fingerprint.rule_version,
                "title": item.title,
                "issue_type": item.issue_type.value,
                "severity": item.severity.value,
                "occurrence_count": item.occurrence_count,
                "affected_run_count": item.affected_run_count,
                "affected_device_count": item.affected_device_count,
                "affected_scenario_count": item.affected_scenario_count,
                "affected_versions": list(item.affected_versions),
                "affected_devices": list(item.affected_devices),
                "affected_scenarios": list(item.affected_scenarios),
                "affected_packages": list(item.affected_packages),
                "sample_event_ids": list(item.sample_event_ids),
                "first_seen_at": self._isoformat_or_none(item.first_seen_at),
                "last_seen_at": self._isoformat_or_none(item.last_seen_at),
                "score": item.score,
                "score_breakdown": dict(item.score_breakdown),
                "metadata": dict(getattr(item, "metadata", {}) or {}),
            }
            self._append_advanced_issue_evidence(payload, item=item)
            if attribution_service is not None and hasattr(attribution_service, "attribute_issue_group"):
                try:
                    payload["attribution"] = self._issue_attribution_payload(
                        attribution_service.attribute_issue_group(item)
                    )
                except Exception:
                    pass
            if collaboration_service is not None and hasattr(collaboration_service, "get_issue_record"):
                try:
                    record = collaboration_service.get_issue_record(item.fingerprint.value)
                except Exception:
                    record = None
                if record is not None:
                    payload.update(self._issue_collaboration_payload(record))
            payloads.append(payload)
        return payloads

    @staticmethod
    def _append_advanced_issue_evidence(payload: dict[str, Any], *, item: object) -> None:
        metadata = dict(getattr(item, "metadata", {}) or payload.get("metadata", {}) or {})
        evidence_signals = getattr(item, "evidence_signals", None)
        if evidence_signals is None:
            evidence_signals = metadata.get("evidence_signals")
        if evidence_signals:
            payload["evidence_signals"] = list(evidence_signals) if isinstance(evidence_signals, (list, tuple)) else evidence_signals
        confirmation_level = str(getattr(item, "confirmation_level", "") or metadata.get("confirmation_level", "") or "")
        if confirmation_level:
            payload["confirmation_level"] = confirmation_level

    @staticmethod
    def _issue_attribution_payload(item: object) -> dict[str, Any]:
        def read(name: str, default: Any = "") -> Any:
            if isinstance(item, Mapping):
                return item.get(name, default)
            return getattr(item, name, default)

        def enum_value(value: Any) -> Any:
            return getattr(value, "value", value)

        def list_value(value: Any) -> list[Any]:
            if value in (None, ""):
                return []
            if isinstance(value, (list, tuple)):
                return list(value)
            return [value]

        hits = []
        for hit in list_value(read("hits", [])):
            if isinstance(hit, Mapping):
                hits.append(dict(hit))
            else:
                hits.append(
                    {
                        "field": getattr(hit, "field", ""),
                        "keyword": getattr(hit, "keyword", ""),
                        "evidence": getattr(hit, "evidence", ""),
                        "score": getattr(hit, "score", 0),
                    }
                )

        payload: dict[str, Any] = {
            "fingerprint": read("fingerprint", ""),
            "issue_type": enum_value(read("issue_type", "")),
            "title": read("title", ""),
            "direction": read("direction", ""),
            "direction_label": read("direction_label", ""),
            "confidence": read("confidence", ""),
            "summary": read("summary", ""),
            "rule_version": read("rule_version", ""),
            "matched_rule_id": read("matched_rule_id", ""),
            "matched_rule_name": read("matched_rule_name", ""),
            "score": read("score", 0),
            "sample_event_ids": list_value(read("sample_event_ids", [])),
            "hits": hits,
            "notes": list_value(read("notes", [])),
        }
        for field in (
            "confidence_score",
            "matched_rule_ids",
            "evidence_summary",
            "recommended_next_steps",
            "review_notes",
        ):
            value = read(field, None)
            if value is None:
                continue
            payload[field] = list(value) if isinstance(value, (list, tuple)) else value
        return payload

    def _admission_view_groups(
        self,
        *,
        items: list[dict[str, Any]],
        current_actor: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        actor_id = str(dict(current_actor or {}).get("actor_id", "") or "")
        mine = [item for item in items if actor_id and str(item.get("assignee_id", "") or "") == actor_id]
        pending_confirmation = [
            item
            for item in items
            if str(item.get("status", "") or "") in {"pending_confirmation"}
        ]
        approved_with_risk = [
            item
            for item in items
            if str(item.get("status", "") or "") == "approved_with_risk"
            or (
                str(item.get("final_decision", "") or "") in {"pass", "conditional_pass"}
                and (
                    int(item.get("risk_count", 0) or 0) > 0
                    or int(item.get("performance_risk_count", 0) or 0) > 0
                )
            )
        ]
        return {
            "mine": mine,
            "pending_confirmation": pending_confirmation,
            "approved_with_risk": approved_with_risk,
            "summary": {
                "mine_count": len(mine),
                "pending_confirmation_count": len(pending_confirmation),
                "approved_with_risk_count": len(approved_with_risk),
            },
        }

    def _collaboration_actors(self) -> list[dict[str, Any]]:
        service = getattr(self._bundle, "collaboration_service", None)
        if service is None or not hasattr(service, "list_actors"):
            return []
        return [
            {
                "actor_id": str(getattr(item, "actor_id", "") or ""),
                "display_name": str(getattr(item, "display_name", "") or ""),
                "role_key": str(getattr(item, "role_key", "") or ""),
                "permissions": list(getattr(item, "permissions", ()) or ()),
            }
            for item in (service.list_actors() or ())
        ]

    def _user_profiles(self) -> tuple[list[dict[str, Any]], str]:
        service = getattr(self._bundle, "collaboration_service", None)
        if service is not None and hasattr(service, "list_user_profiles"):
            try:
                profiles = [self._user_profile_payload(item) for item in (service.list_user_profiles() or ())]
                return profiles, "user_profiles"
            except Exception:
                pass
        return [self._actor_as_user_profile(item) for item in self._collaboration_actors()], "actors_fallback"

    def _user_profile_payload(self, item: object) -> dict[str, Any]:
        raw = dict(item) if isinstance(item, Mapping) else {}
        external_values = raw.get("external_identities", getattr(item, "external_identities", ()))
        external_identities = [
            self._external_identity_payload(identity)
            for identity in list(external_values or [])
        ]
        actor_id = str(raw.get("actor_id", "") or getattr(item, "actor_id", "") or raw.get("profile_id", "") or getattr(item, "profile_id", "") or "")
        return {
            "profile_id": str(raw.get("profile_id", "") or getattr(item, "profile_id", "") or actor_id),
            "actor_id": actor_id,
            "display_name": str(raw.get("display_name", "") or getattr(item, "display_name", "") or raw.get("name", "") or getattr(item, "name", "") or actor_id),
            "email": str(raw.get("email", "") or getattr(item, "email", "") or raw.get("primary_email", "") or getattr(item, "primary_email", "") or ""),
            "role_key": str(raw.get("role_key", "") or getattr(item, "role_key", "") or ""),
            "team_ids": list(raw.get("team_ids", ()) or getattr(item, "team_ids", ()) or raw.get("teams", ()) or getattr(item, "teams", ()) or ()),
            "team_key": str(raw.get("team_key", "") or getattr(item, "team_key", "") or ""),
            "external_identities": external_identities,
            "permissions": list(raw.get("permissions", ()) or getattr(item, "permissions", ()) or ()),
            "source": "user_profiles",
        }

    def _actor_as_user_profile(self, actor: Mapping[str, Any]) -> dict[str, Any]:
        actor_id = str(actor.get("actor_id", "") or "")
        return {
            "profile_id": actor_id,
            "actor_id": actor_id,
            "display_name": str(actor.get("display_name", "") or actor_id),
            "email": "",
            "role_key": str(actor.get("role_key", "") or ""),
            "team_ids": [],
            "team_key": "",
            "external_identities": [],
            "permissions": list(actor.get("permissions", []) or []),
            "source": "actors_fallback",
        }

    @staticmethod
    def _external_identity_payload(item: object) -> dict[str, Any]:
        raw = dict(item) if isinstance(item, Mapping) else {}
        return {
            "identity_id": str(raw.get("identity_id", "") or getattr(item, "identity_id", "") or ""),
            "provider": str(raw.get("provider", "") or getattr(item, "provider", "") or ""),
            "external_subject_id": str(raw.get("external_subject_id", "") or getattr(item, "external_subject_id", "") or ""),
            "external_email": str(raw.get("external_email", "") or getattr(item, "external_email", "") or raw.get("email", "") or getattr(item, "email", "") or ""),
            "organization_id": str(raw.get("organization_id", "") or getattr(item, "organization_id", "") or ""),
            "team_ids": list(raw.get("team_ids", ()) or getattr(item, "team_ids", ()) or ()),
            "role_claims": list(raw.get("role_claims", ()) or getattr(item, "role_claims", ()) or ()),
        }

    def _release_submission_summaries_for_responsibility(self, *, limit: int) -> list[dict[str, Any]]:
        service = getattr(self._bundle, "release_submission_service", None)
        if service is None or not hasattr(service, "list_submissions"):
            return []
        try:
            return [self._release_submission_payload(item) for item in list(service.list_submissions(limit=limit))]
        except Exception:
            return []

    @staticmethod
    def _profile_ref(actor_id: str, profile_by_actor: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        profile = dict(profile_by_actor.get(actor_id, {}) or {})
        return {
            "actor_id": actor_id,
            "profile_id": str(profile.get("profile_id", "") or actor_id),
            "display_name": str(profile.get("display_name", "") or actor_id),
            "email": str(profile.get("email", "") or ""),
            "team_ids": list(profile.get("team_ids", []) or []),
            "external_identities": list(profile.get("external_identities", []) or []),
        }

    def _responsibility_issue_item(
        self,
        item: Mapping[str, Any],
        *,
        profile_by_actor: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        assignee_id = str(item.get("assignee_id", "") or "")
        return {
            "source": "issue",
            "target_type": "issue",
            "target_id": str(item.get("fingerprint", "") or ""),
            "title": str(item.get("title", "") or ""),
            "workflow_state": str(item.get("workflow_state", "") or "new"),
            "responsibility_type": "assignee",
            "responsibility_key": assignee_id,
            "assignee": self._profile_ref(assignee_id, profile_by_actor) if assignee_id else {},
            "severity": str(item.get("severity", "") or ""),
            "issue_type": str(item.get("issue_type", "") or ""),
        }

    def _responsibility_admission_item(
        self,
        item: Mapping[str, Any],
        *,
        profile_by_actor: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        assignee_id = str(item.get("assignee_id", "") or "")
        reviewer_id = str(item.get("final_reviewer_id", "") or "")
        return {
            "source": "admission",
            "target_type": "admission_case",
            "target_id": str(item.get("case_id", "") or item.get("baseline_key", "") or ""),
            "baseline_key": str(item.get("baseline_key", "") or ""),
            "workflow_state": str(item.get("workflow_state", "") or item.get("status", "") or "new"),
            "responsibility_type": "assignee_and_final_reviewer",
            "responsibility_key": assignee_id or reviewer_id,
            "assignee": self._profile_ref(assignee_id, profile_by_actor) if assignee_id else {},
            "final_reviewer": self._profile_ref(reviewer_id, profile_by_actor) if reviewer_id else {},
            "final_decision": str(item.get("final_decision", "") or ""),
        }

    @staticmethod
    def _responsibility_defect_item(*, issue: Mapping[str, Any], defect: Mapping[str, Any]) -> dict[str, Any]:
        metadata = dict(defect.get("metadata", {}) or {})
        team_key = str(metadata.get("team_key", "") or defect.get("team_key", "") or "")
        return {
            "source": "defect",
            "target_type": "defect",
            "target_id": str(defect.get("defect_id", "") or defect.get("link_id", "") or ""),
            "issue_fingerprint": str(issue.get("fingerprint", "") or ""),
            "system_key": str(defect.get("system_key", "") or ""),
            "status": str(defect.get("status", "") or ""),
            "responsibility_type": "team_key",
            "responsibility_key": team_key,
            "team_key": team_key,
        }

    @staticmethod
    def _responsibility_release_item(item: Mapping[str, Any]) -> dict[str, Any]:
        owner_team = str(item.get("owner_team", "") or "")
        return {
            "source": "release_submission",
            "target_type": "release_submission",
            "target_id": str(item.get("submission_id", "") or ""),
            "source_platform": str(item.get("source_platform", "") or ""),
            "source_request_id": str(item.get("source_request_id", "") or ""),
            "submission_status": str(item.get("submission_status", "") or ""),
            "responsibility_type": "owner_team",
            "responsibility_key": owner_team,
            "owner_team": owner_team,
            "baseline_key": str(item.get("baseline_key", "") or ""),
        }

    @staticmethod
    def _responsibility_external_mapping(profile: Mapping[str, Any], identity: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "source": "external_identity",
            "target_type": "user_profile",
            "target_id": str(profile.get("profile_id", "") or profile.get("actor_id", "") or ""),
            "actor_id": str(profile.get("actor_id", "") or ""),
            "display_name": str(profile.get("display_name", "") or ""),
            "responsibility_type": "external_identity",
            "responsibility_key": str(identity.get("identity_id", "") or identity.get("external_subject_id", "") or ""),
            "provider": str(identity.get("provider", "") or ""),
            "external_subject_id": str(identity.get("external_subject_id", "") or ""),
            "external_email": str(identity.get("external_email", "") or ""),
            "organization_id": str(identity.get("organization_id", "") or ""),
            "team_ids": list(identity.get("team_ids", []) or []),
        }

    def _issue_collaboration_payload(self, item: object) -> dict[str, Any]:
        comments = list(getattr(item, "comments", ()) or ())
        events = list(getattr(item, "events", ()) or ())
        defect_links = list(getattr(item, "defect_links", ()) or ())
        latest_comment = comments[-1] if comments else None
        latest_defect = defect_links[-1] if defect_links else None
        return {
            "workflow_state": str(getattr(item, "workflow_state", "") or "new"),
            "assignee_id": str(getattr(item, "assignee_id", "") or ""),
            "assignee_display_name": str(getattr(item, "assignee_display_name", "") or ""),
            "updated_at": self._isoformat_or_none(getattr(item, "updated_at", None)),
            "updated_by": str(getattr(item, "updated_by", "") or ""),
            "comment_count": len(comments),
            "defect_link_count": len(defect_links),
            "has_acceptable_defect": any(bool(getattr(entry, "acceptable_for_close", False)) for entry in defect_links),
            "latest_defect_system_key": str(getattr(latest_defect, "system_key", "") or "") if latest_defect else "",
            "latest_defect_status": str(getattr(latest_defect, "status", "") or "") if latest_defect else "",
            "latest_comment_body": str(getattr(latest_comment, "body", "") or "") if latest_comment else "",
            "latest_comment_by": str(getattr(latest_comment, "created_by", "") or "") if latest_comment else "",
            "latest_comment_at": self._isoformat_or_none(getattr(latest_comment, "created_at", None)) if latest_comment else None,
            "latest_comment_session_source": str(getattr(latest_comment, "session_source", "") or "") if latest_comment else "",
            "defect_links": [
                {
                    "link_id": str(getattr(entry, "link_id", "") or ""),
                    "system_key": str(getattr(entry, "system_key", "") or ""),
                    "defect_id": str(getattr(entry, "defect_id", "") or ""),
                    "title": str(getattr(entry, "title", "") or ""),
                    "url": str(getattr(entry, "url", "") or ""),
                    "status": str(getattr(entry, "status", "") or ""),
                    "acceptable_for_close": bool(getattr(entry, "acceptable_for_close", False)),
                    "sync_status": str(getattr(entry, "sync_status", "") or ""),
                    "created_at": self._isoformat_or_none(getattr(entry, "created_at", None)),
                    "created_by": str(getattr(entry, "created_by", "") or ""),
                    "synced_at": self._isoformat_or_none(getattr(entry, "synced_at", None)),
                    "synced_by": str(getattr(entry, "synced_by", "") or ""),
                    "metadata": dict(getattr(entry, "metadata", {}) or {}),
                }
                for entry in defect_links
            ],
            "events": [
                {
                    "event_id": str(getattr(entry, "event_id", "") or ""),
                    "action": str(getattr(entry, "action", "") or ""),
                    "created_at": self._isoformat_or_none(getattr(entry, "created_at", None)),
                    "created_by": str(getattr(entry, "created_by", "") or ""),
                    "session_source": str(getattr(entry, "session_source", "") or ""),
                    "audit_source": dict(getattr(entry, "audit_source", {}) or {}),
                    "payload": dict(getattr(entry, "payload", {}) or {}),
                }
                for entry in events[-5:]
            ],
        }

    def _admission_collaboration_payload(self, item: object) -> dict[str, Any]:
        comments = list(getattr(item, "comments", ()) or ())
        events = list(getattr(item, "events", ()) or ())
        latest_comment = comments[-1] if comments else None
        return {
            "status": str(getattr(item, "workflow_state", "") or "new"),
            "workflow_state": str(getattr(item, "workflow_state", "") or "new"),
            "assignee_id": str(getattr(item, "assignee_id", "") or ""),
            "assignee_display_name": str(getattr(item, "assignee_display_name", "") or ""),
            "final_reviewer_id": str(getattr(item, "final_reviewer_id", "") or ""),
            "final_reviewer_display_name": str(getattr(item, "final_reviewer_display_name", "") or ""),
            "updated_at": self._isoformat_or_none(getattr(item, "updated_at", None)),
            "updated_by": str(getattr(item, "updated_by", "") or ""),
            "comment_count": len(comments),
            "latest_comment_body": str(getattr(latest_comment, "body", "") or "") if latest_comment else "",
            "latest_comment_by": str(getattr(latest_comment, "created_by", "") or "") if latest_comment else "",
            "latest_comment_at": self._isoformat_or_none(getattr(latest_comment, "created_at", None)) if latest_comment else None,
            "events": [
                {
                    "event_id": str(getattr(entry, "event_id", "") or ""),
                    "action": str(getattr(entry, "action", "") or ""),
                    "created_at": self._isoformat_or_none(getattr(entry, "created_at", None)),
                    "created_by": str(getattr(entry, "created_by", "") or ""),
                    "session_source": str(getattr(entry, "session_source", "") or ""),
                    "audit_source": dict(getattr(entry, "audit_source", {}) or {}),
                    "payload": dict(getattr(entry, "payload", {}) or {}),
                }
                for entry in events[-5:]
            ],
        }
