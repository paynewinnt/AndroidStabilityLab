from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app import CollaborationService, IntegrationOutboxService
from stability.domain.value_objects import utcnow


class CollaborationServiceTest(unittest.TestCase):
    def test_issue_actions_persist_state_comments_and_outbox_events(self) -> None:
        with TemporaryDirectory() as temp_dir:
            outbox = IntegrationOutboxService(root_dir=Path(temp_dir) / "outbox")
            service = CollaborationService(
                root_dir=Path(temp_dir) / "collaboration",
                outbox_service=outbox,
            )

            assigned = service.assign_issue(
                fingerprint="ifp_1",
                actor_id="tester",
                assignee_id="developer",
                session_source="query:as_actor",
                audit_source={"request_path": "/issues/actions/assign"},
            )
            self.assertEqual(assigned.workflow_state, "assigned")
            self.assertEqual(assigned.assignee_id, "developer")

            commented = service.comment_issue(
                fingerprint="ifp_1",
                actor_id="developer",
                body="可以稳定复现，继续分析。",
                session_source="header:x-asl-actor",
                audit_source={"request_path": "/issues/actions/comment"},
            )
            self.assertEqual(len(commented.comments), 1)
            self.assertEqual(commented.comments[0].body, "可以稳定复现，继续分析。")
            self.assertEqual(commented.comments[0].session_source, "header:x-asl-actor")

            transitioned = service.transition_issue(
                fingerprint="ifp_1",
                actor_id="developer",
                workflow_state="processing",
                reason="已开始定位。",
                session_source="query:as_actor",
                audit_source={"request_path": "/issues/actions/transition"},
            )
            self.assertEqual(transitioned.workflow_state, "processing")
            self.assertEqual(len(transitioned.events), 3)

            reloaded = service.get_issue_record("ifp_1")
            self.assertEqual(reloaded.workflow_state, "processing")
            self.assertEqual(reloaded.assignee_id, "developer")
            self.assertEqual(len(reloaded.comments), 1)

            events = outbox.list_events(limit=10)
            self.assertEqual(len(events), 3)
            self.assertEqual(events[0].event_type, "issue.transitioned")
            self.assertEqual(events[0].session_source, "query:as_actor")
            self.assertEqual(events[-1].event_type, "issue.assigned")

    def test_admission_case_actions_persist_state_comments_and_outbox_events(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CollaborationService(
                root_dir=Path(temp_dir) / "collaboration",
                outbox_service=IntegrationOutboxService(root_dir=Path(temp_dir) / "outbox"),
            )

            assigned = service.assign_admission_case(
                baseline_key="baseline_1",
                actor_id="tester",
                assignee_id="developer",
                session_source="header:x-asl-actor",
                audit_source={"request_path": "/admission/actions/assign", "auth_mechanism": "header_actor"},
            )
            self.assertEqual(assigned.workflow_state, "assigned")
            self.assertEqual(assigned.assignee_id, "developer")

            commented = service.comment_admission_case(
                baseline_key="baseline_1",
                actor_id="developer",
                body="存在性能风险，建议转待确认。",
                session_source="header:x-asl-session-token",
                audit_source={
                    "request_path": "/admission/actions/comment",
                    "auth_mechanism": "session_token",
                    "resolved_session_token": "asl.session.v1:developer:developer",
                },
            )
            self.assertEqual(len(commented.comments), 1)
            self.assertEqual(commented.comments[0].body, "存在性能风险，建议转待确认。")

            transitioned = service.transition_admission_case(
                baseline_key="baseline_1",
                actor_id="tester",
                workflow_state="pending_confirmation",
                reason="需要责任人补充放行依据。",
                session_source="header:x-asl-session-token",
                audit_source={
                    "request_path": "/admission/actions/transition",
                    "auth_mechanism": "session_token",
                    "resolved_session_token": "asl.session.v1:tester:tester",
                },
            )
            self.assertEqual(transitioned.workflow_state, "pending_confirmation")
            self.assertEqual(transitioned.final_reviewer_id, "tester")
            self.assertEqual(len(transitioned.events), 3)

            reloaded = service.get_admission_case_record("baseline_1")
            self.assertEqual(reloaded.workflow_state, "pending_confirmation")
            self.assertEqual(reloaded.assignee_id, "developer")
            self.assertEqual(len(reloaded.comments), 1)
            self.assertTrue(str(reloaded.events[-1].audit_source.get("resolved_session_id", "")).startswith("asl.session_id.v1:"))
            self.assertTrue(str(reloaded.events[-1].audit_source.get("audit_event_id", "")).startswith("asl.audit_event.v1:"))
            self.assertTrue(str(reloaded.events[-1].audit_source.get("permission_check_id", "")).startswith("asl.permission_check.v1:"))

    def test_issue_defect_lifecycle_blocks_resolution_until_acceptable_status(self) -> None:
        with TemporaryDirectory() as temp_dir:
            outbox = IntegrationOutboxService(root_dir=Path(temp_dir) / "outbox")
            service = CollaborationService(
                root_dir=Path(temp_dir) / "collaboration",
                outbox_service=outbox,
            )

            created = service.create_issue_defect(
                fingerprint="ifp_2",
                actor_id="tester",
                system_key="jira",
                title="首页冷启动偶发崩溃",
                description="需要外部缺陷系统跟进。",
                team_key="android-client",
                session_source="header:x-asl-session-token",
                audit_source={"request_path": "/issues/actions/create-defect"},
            )
            self.assertEqual(len(created.defect_links), 1)
            self.assertEqual(created.defect_links[0].sync_status, "pending_create")

            with self.assertRaises(ValueError) as ctx:
                service.transition_issue(
                    fingerprint="ifp_2",
                    actor_id="tester",
                    workflow_state="resolved",
                    reason="还没有缺陷状态同步。",
                    session_source="header:x-asl-session-token",
                    audit_source={"request_path": "/issues/actions/transition"},
                )
            self.assertIn("acceptable status", str(ctx.exception))

            synced = service.sync_issue_defect_status(
                fingerprint="ifp_2",
                actor_id="tester",
                link_id=created.defect_links[0].link_id,
                status="accepted",
                acceptable_for_close=True,
                url="https://bugs.example.invalid/browse/ASL-1",
                session_source="header:x-asl-session-token",
                audit_source={"request_path": "/issues/actions/sync-defect"},
            )
            self.assertTrue(synced.defect_links[0].acceptable_for_close)
            self.assertEqual(synced.defect_links[0].status, "accepted")

            resolved = service.transition_issue(
                fingerprint="ifp_2",
                actor_id="tester",
                workflow_state="resolved",
                reason="缺陷已受理，可关闭平台问题。",
                session_source="header:x-asl-session-token",
                audit_source={"request_path": "/issues/actions/transition"},
            )
            self.assertEqual(resolved.workflow_state, "resolved")

            event_types = [item.event_type for item in outbox.list_events(limit=10)]
            self.assertIn("issue.defect_create_requested", event_types)
            self.assertIn("issue.defect_status_synced", event_types)
            self.assertIn("issue.transitioned", event_types)

    def test_sessions_are_issued_expired_and_revocable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CollaborationService(root_dir=Path(temp_dir) / "collaboration")

            session = service.issue_session("tester", issued_by="admin", ttl_seconds=120)
            resolved = service.resolve_session(session.session_token)

            self.assertEqual(resolved.actor_id, "tester")
            self.assertIsNotNone(resolved.expires_at)

            expired = service.issue_session("developer", issued_by="admin", ttl_seconds=60)
            expired_payload = dict(service._load_session_registry()[expired.session_token])
            expired_payload["expires_at"] = (utcnow() - timedelta(seconds=1)).isoformat()
            service._save_session(service._session_from_payload(expired_payload))
            with self.assertRaises(PermissionError):
                service.resolve_session(expired.session_token)

            revoked = service.issue_session("observer", issued_by="admin", ttl_seconds=120)
            service.revoke_session(revoked.session_token, revoked_by="admin", reason="logout")
            with self.assertRaises(PermissionError):
                service.resolve_session(revoked.session_token)

    def test_sso_claims_create_and_bind_external_actor(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CollaborationService(
                root_dir=Path(temp_dir) / "collaboration",
                trusted_organization_ids=("org-android",),
            )

            resolved = service.resolve_sso_actor(
                {
                    "provider": "okta",
                    "external_subject_id": "00u123",
                    "external_email": "qa@example.com",
                    "external_display_name": "QA Owner",
                    "organization_id": "org-android",
                    "team_ids": ["mobile", "qa"],
                    "role_claims": ["tester"],
                    "session_id": "sid-1",
                }
            )

            actor = resolved["actor"]
            identity = resolved["identity"]
            session = resolved["session"]
            self.assertEqual(actor.display_name, "QA Owner")
            self.assertEqual(actor.role_key, "tester")
            self.assertEqual(identity.provider, "okta")
            self.assertEqual(identity.organization_id, "org-android")
            self.assertEqual(session.identity_id, identity.identity_id)
            self.assertEqual(session.auth_mechanism, "sso_header")
            self.assertEqual(service.get_actor(actor.actor_id).actor_id, actor.actor_id)
            self.assertEqual(resolved["user_profile"].profile_id, identity.identity_id)
            self.assertEqual(resolved["user_profile"].last_seen_at, identity.updated_at)

    def test_sso_claims_resolve_same_external_subject_stably(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CollaborationService(
                root_dir=Path(temp_dir) / "collaboration",
                trusted_organization_ids=("org-android",),
            )
            claims = {
                "provider": "okta",
                "external_subject_id": "00u123",
                "external_email": "qa@example.com",
                "external_display_name": "QA Owner",
                "organization_id": "org-android",
                "role_claims": ["tester"],
                "session_id": "sid-1",
            }

            first = service.resolve_sso_actor(claims)
            second = service.resolve_sso_actor({**claims, "external_display_name": "QA Owner Renamed"})

            self.assertEqual(first["actor"].actor_id, second["actor"].actor_id)
            self.assertEqual(first["identity"].identity_id, second["identity"].identity_id)
            self.assertEqual(first["session"].session_id, second["session"].session_id)
            self.assertEqual(service.list_external_identities()[0].external_display_name, "QA Owner Renamed")

    def test_sso_resolution_creates_and_updates_user_directory_profile(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CollaborationService(
                root_dir=Path(temp_dir) / "collaboration",
                trusted_organization_ids=("org-android",),
            )
            claims = {
                "provider": "okta",
                "external_subject_id": "00u123",
                "external_email": "qa@example.com",
                "external_display_name": "QA Owner",
                "organization_id": "org-android",
                "team_ids": ["mobile", "qa"],
                "role_claims": ["tester"],
                "session_id": "sid-1",
            }

            first = service.sync_user_profile_from_sso(claims)
            first_last_seen = first.last_seen_at
            second = service.sync_user_profile_from_sso(
                {
                    **claims,
                    "external_display_name": "QA Owner Renamed",
                    "team_ids": ["mobile", "release"],
                    "role_claims": ["developer"],
                }
            )

            self.assertEqual(first.profile_id, second.profile_id)
            self.assertEqual(first.actor_id, second.actor_id)
            self.assertEqual(second.display_name, "QA Owner Renamed")
            self.assertEqual(second.team_ids, ("mobile", "release"))
            self.assertEqual(second.role_key, "developer")
            self.assertIn("sync_issue_defect", second.permissions)
            self.assertIsNotNone(second.last_seen_at)
            self.assertGreaterEqual(second.last_seen_at, first_last_seen)

    def test_user_directory_lists_local_and_external_profile_details(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CollaborationService(
                root_dir=Path(temp_dir) / "collaboration",
                trusted_organization_ids=("org-android",),
            )
            resolved = service.resolve_sso_actor(
                {
                    "provider": "okta",
                    "external_subject_id": "00u123",
                    "external_email": "qa@example.com",
                    "external_display_name": "QA Owner",
                    "organization_id": "org-android",
                    "team_ids": ["mobile", "qa"],
                    "role_claims": ["tester"],
                    "session_id": "sid-1",
                }
            )

            profiles = service.list_user_profiles()
            local = service.get_user_profile("developer")
            external = service.get_user_profile(resolved["identity"].identity_id)

            self.assertIn("developer", {item.actor_id for item in profiles})
            self.assertEqual(local.profile_id, service.actor_identity_id("developer"))
            self.assertEqual(local.display_name, "Developer")
            self.assertEqual(local.organization_id, "")
            self.assertIn("comment_issue", local.permissions)
            self.assertEqual(external.email, "qa@example.com")
            self.assertEqual(external.organization_id, "org-android")
            self.assertEqual(external.team_ids, ("mobile", "qa"))
            self.assertEqual(external.external_identities[0].provider, "okta")
            self.assertEqual(external.external_identities[0].external_subject_id, "00u123")
            self.assertIn("assign_issue", external.permissions)

    def test_sso_claims_reject_missing_fields_and_wrong_organization(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CollaborationService(
                root_dir=Path(temp_dir) / "collaboration",
                trusted_organization_ids=("org-android",),
            )
            valid_claims = {
                "provider": "okta",
                "external_subject_id": "00u123",
                "external_email": "qa@example.com",
                "organization_id": "org-android",
                "role_claims": ["tester"],
                "session_id": "sid-1",
            }

            with self.assertRaises(ValueError):
                service.resolve_sso_actor({**valid_claims, "external_subject_id": ""})
            with self.assertRaises(PermissionError):
                service.resolve_sso_actor({**valid_claims, "organization_id": ""})
            with self.assertRaises(PermissionError):
                service.resolve_sso_actor({**valid_claims, "organization_id": "org-other"})

    def test_sso_permission_audit_contains_identity_provider_and_organization(self) -> None:
        with TemporaryDirectory() as temp_dir:
            service = CollaborationService(
                root_dir=Path(temp_dir) / "collaboration",
                trusted_organization_ids=("org-android",),
            )
            resolved = service.resolve_sso_actor(
                {
                    "provider": "okta",
                    "external_subject_id": "00u123",
                    "external_email": "qa@example.com",
                    "external_display_name": "QA Owner",
                    "organization_id": "org-android",
                    "role_claims": ["tester"],
                    "session_id": "sid-1",
                }
            )

            record = service.comment_issue(
                fingerprint="ifp_sso",
                actor_id=resolved["actor_id"],
                actor_identity_id=resolved["actor_identity_id"],
                body="SSO user can comment through the existing permission matrix.",
                session_source=resolved["session_source"],
                audit_source=resolved["audit_source"],
            )
            audit_source = record.events[-1].audit_source

            self.assertEqual(audit_source["auth_mechanism"], "sso_header")
            self.assertEqual(audit_source["identity_provider"], "okta")
            self.assertEqual(audit_source["organization_id"], "org-android")
            self.assertEqual(audit_source["external_subject_id"], "00u123")
            self.assertEqual(audit_source["identity_boundary"], "trusted_sso_organization")
            self.assertTrue(str(audit_source.get("permission_check_id", "")).startswith("asl.permission_check.v1:"))


if __name__ == "__main__":
    unittest.main()
