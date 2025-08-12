from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app.rule_governance_service import RuleGovernanceService


class RuleGovernanceServiceTest(unittest.TestCase):
    def test_inspect_rules_returns_source_and_effective_payloads(self) -> None:
        with TemporaryDirectory() as temp_dir:
            rule_path = Path(temp_dir) / "rules.json"
            rule_path.write_text(
                json.dumps(
                    {
                        "fingerprint": {"version": "v2"},
                        "regression": {"version": "v3", "min_side_issue_groups": 2},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            service = RuleGovernanceService(rule_path=rule_path)

            result = service.inspect_rules()

            self.assertTrue(result.source_exists)
            self.assertTrue(result.validation.valid)
            self.assertEqual(result.source_rules["fingerprint"]["version"], "v2")
            self.assertEqual(result.effective_rules["fingerprint"]["version"], "v2")
            self.assertEqual(result.effective_rules["regression"]["version"], "v3")
            self.assertIn("attribution", result.default_rules)

    def test_validate_rules_reports_invalid_issue_type_and_unknown_key(self) -> None:
        with TemporaryDirectory() as temp_dir:
            rule_path = Path(temp_dir) / "rules.json"
            rule_path.write_text(
                json.dumps(
                    {
                        "fingerprint": {"unknown_field": True},
                        "attribution": {
                            "rules": [
                                {
                                    "rule_id": "bad_rule",
                                    "issue_types": ["not_a_real_issue"],
                                }
                            ]
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            service = RuleGovernanceService(rule_path=rule_path)

            result = service.validate_rules()

            self.assertFalse(result.valid)
            self.assertTrue(any("unsupported issue type" in item for item in result.errors))
            self.assertTrue(any("Unknown key 'fingerprint.unknown_field'" in item for item in result.warnings))

    def test_validate_current_attribution_fields_do_not_warn_unknown_keys(self) -> None:
        service = RuleGovernanceService(rule_path=Path("config/stability_rules.json"))

        result = service.validate_rules()

        self.assertTrue(result.valid, result.errors)
        for key in (
            "scored_issue_types",
            "issue_type_score",
            "metadata_keywords",
            "evidence_signal_keywords",
            "evidence_source_keywords",
            "matched_fragment_keywords",
            "confirmation_level_scores",
            "recommended_next_steps",
            "review_notes",
        ):
            self.assertFalse(
                any(f".{key}'" in item for item in result.warnings),
                f"Unexpected unknown-key warning for {key}: {result.warnings}",
            )

    def test_validate_rules_reports_invalid_new_attribution_field_types(self) -> None:
        with TemporaryDirectory() as temp_dir:
            rule_path = Path(temp_dir) / "rules.json"
            rule_path.write_text(
                json.dumps(
                    {
                        "attribution": {
                            "rules": [
                                {
                                    "rule_id": "bad_contract",
                                    "scored_issue_types": "crash",
                                    "issue_type_score": "3",
                                    "evidence_signal_keywords": ["watchdog", 7],
                                    "confirmation_level_scores": {"strong": "3"},
                                    "recommended_next_steps": "inspect dropbox",
                                    "review_notes": ["ok", False],
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            service = RuleGovernanceService(rule_path=rule_path)

            result = service.validate_rules()

            self.assertFalse(result.valid)
            self.assertTrue(any("scored_issue_types must be a JSON array" in item for item in result.errors))
            self.assertTrue(any("issue_type_score must be an integer" in item for item in result.errors))
            self.assertTrue(any("evidence_signal_keywords[1] must be a string" in item for item in result.errors))
            self.assertTrue(any("confirmation_level_scores.strong must be an integer" in item for item in result.errors))
            self.assertTrue(any("recommended_next_steps must be a JSON array" in item for item in result.errors))
            self.assertTrue(any("review_notes[1] must be a string" in item for item in result.errors))

    def test_default_rule_serialization_includes_new_attribution_fields(self) -> None:
        with TemporaryDirectory() as temp_dir:
            rule_path = Path(temp_dir) / "rules.json"
            rule_path.write_text("{}", encoding="utf-8")
            service = RuleGovernanceService(rule_path=rule_path)

            result = service.inspect_rules()
            rules = result.default_rules["attribution"]["rules"]
            framework_rule = next(item for item in rules if item["rule_id"] == "framework_system_service")

            self.assertEqual(framework_rule["scored_issue_types"], ["system_server_crash", "watchdog"])
            self.assertEqual(framework_rule["issue_type_score"], 3)
            self.assertIn("system_server", framework_rule["metadata_keywords"])
            self.assertIn("watchdog", framework_rule["evidence_signal_keywords"])
            self.assertEqual(framework_rule["confirmation_level_scores"]["strong"], 3)
            self.assertTrue(framework_rule["recommended_next_steps"])
            self.assertTrue(framework_rule["review_notes"])

    def test_export_effective_rules_writes_json_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            rule_path = Path(temp_dir) / "rules.json"
            export_path = Path(temp_dir) / "effective.json"
            rule_path.write_text(json.dumps({"fingerprint": {"version": "v9"}}, ensure_ascii=False), encoding="utf-8")
            service = RuleGovernanceService(rule_path=rule_path)

            result = service.export_effective_rules(export_path)

            self.assertEqual(result.rule_versions["fingerprint"], "v9")
            self.assertTrue(export_path.exists())
            exported = json.loads(export_path.read_text(encoding="utf-8"))
            self.assertEqual(exported["fingerprint"]["version"], "v9")

    def test_diff_rules_reports_field_level_changes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            left_path = Path(temp_dir) / "left.json"
            right_path = Path(temp_dir) / "right.json"
            left_path.write_text(
                json.dumps(
                    {
                        "fingerprint": {"version": "v1"},
                        "regression": {"version": "v1", "min_side_issue_groups": 1},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            right_path.write_text(
                json.dumps(
                    {
                        "fingerprint": {"version": "v2"},
                        "regression": {"version": "v1", "min_side_issue_groups": 3},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            service = RuleGovernanceService(rule_path=left_path)

            result = service.diff_rules(left_path=left_path, right_path=right_path, left_view="source", right_view="source")

            self.assertEqual(result.diff_count, 2)
            self.assertTrue(any(item.path == "fingerprint.version" for item in result.diffs))
            self.assertTrue(any(item.path == "regression.min_side_issue_groups" for item in result.diffs))

    def test_describe_rule_entrypoint_returns_consumer_contract(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            rule_path = config_dir / "stability_rules.json"
            (config_dir / "rule_review_policy.json").write_text(
                json.dumps({"version": "review-v2"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (config_dir / "rule_review_baseline_policy.json").write_text(
                json.dumps({"version": "baseline-v3"}, ensure_ascii=False),
                encoding="utf-8",
            )
            rule_path.write_text(
                json.dumps(
                    {
                        "fingerprint": {"version": "fp-v1", "ignore_raw_key_issue_types": ["device_offline"]},
                        "regression": {"version": "reg-v1", "min_side_issue_groups": 2},
                        "attribution": {"version": "attr-v1", "rules": []},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            service = RuleGovernanceService(rule_path=rule_path)

            result = service.describe_rule_entrypoint()

            self.assertEqual(result.rule_path, str(rule_path))
            self.assertTrue(result.validation_summary["valid"])
            self.assertEqual(result.config_versions["fingerprint"], "fp-v1")
            self.assertEqual(result.config_versions["rule_review_policy"], "review-v2")
            self.assertEqual(result.config_versions["rule_review_baseline_policy"], "baseline-v3")
            self.assertEqual(set(result.sections), {"fingerprint", "regression", "attribution"})
            self.assertIn("min_side_issue_groups", result.sections["regression"].editable_fields)
            self.assertIn("rules", result.risky_fields["attribution"])
            self.assertIn("rule_review_policy.json", result.related_policy_paths["rule_review_policy"])
            self.assertTrue(result.suggested_workflow)
            self.assertIn("persists candidates", result.audit_hint)

    def test_build_rule_edit_plan_rejects_invalid_patch_without_writing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            rule_path = Path(temp_dir) / "rules.json"
            original = {"fingerprint": {"version": "v1"}}
            rule_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            service = RuleGovernanceService(rule_path=rule_path)

            result = service.build_rule_edit_plan(patch={"unknown": {"version": "v2"}})

            self.assertFalse(result.valid)
            self.assertTrue(any("Unsupported rule section 'unknown'" in item for item in result.errors))
            self.assertEqual(result.diff_count, 0)
            self.assertEqual(json.loads(rule_path.read_text(encoding="utf-8")), original)
            self.assertTrue(result.requires_manual_save)

    def test_preview_rule_update_returns_valid_diff_without_writing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            rule_path = Path(temp_dir) / "rules.json"
            original = {
                "fingerprint": {"version": "v1", "ignore_raw_key_issue_types": ["device_offline"]},
                "regression": {"version": "v1", "min_side_issue_groups": 1},
            }
            rule_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            service = RuleGovernanceService(rule_path=rule_path)

            result = service.preview_rule_update({"regression": {"min_side_issue_groups": 3}})

            self.assertTrue(result.valid, result.errors)
            self.assertEqual(result.patch, {"regression": {"min_side_issue_groups": 3}})
            self.assertEqual(result.preview_rules["regression"]["min_side_issue_groups"], 3)
            self.assertEqual(result.diff_count, 1)
            self.assertTrue(any(item.path == "regression.min_side_issue_groups" for item in result.diffs))
            self.assertEqual(json.loads(rule_path.read_text(encoding="utf-8")), original)
            self.assertTrue(result.requires_manual_save)

    def test_build_rule_edit_plan_accepts_section_key_value(self) -> None:
        with TemporaryDirectory() as temp_dir:
            rule_path = Path(temp_dir) / "rules.json"
            rule_path.write_text(json.dumps({"fingerprint": {"version": "v1"}}, ensure_ascii=False), encoding="utf-8")
            service = RuleGovernanceService(rule_path=rule_path)

            result = service.build_rule_edit_plan(
                section="fingerprint",
                key="ignore_raw_key_issue_types",
                value=["device_offline"],
            )

            self.assertTrue(result.valid, result.errors)
            self.assertEqual(result.preview_rules["fingerprint"]["ignore_raw_key_issue_types"], ["device_offline"])

    def test_rule_governance_candidate_approval_publish_and_rollback(self) -> None:
        with TemporaryDirectory() as temp_dir:
            rule_path = Path(temp_dir) / "rules.json"
            rule_path.write_text(
                json.dumps({"fingerprint": {"version": "v1"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            service = RuleGovernanceService(rule_path=rule_path)

            admin = service.bind_rule_permission(actor_id="cli", role="admin")
            reviewer = service.bind_rule_permission(actor_id="reviewer-1", role="reviewer")
            candidate = service.save_rule_change_candidate(
                {"fingerprint": {"version": "v2"}},
                created_by="cli",
                title="Bump fingerprint rule version",
            )
            approved = service.approve_rule_change_candidate(
                candidate_id=candidate.candidate_id,
                actor_id="reviewer-1",
                decision="approve",
                comment="Replay looks stable.",
            )
            version = service.publish_rule_change_candidate(candidate_id=candidate.candidate_id, published_by="cli")

            self.assertEqual(admin.permissions, ("propose", "approve", "publish", "rollback", "bind_permission"))
            self.assertEqual(reviewer.permissions, ("approve",))
            self.assertEqual(approved.status, "approved")
            self.assertEqual(json.loads(rule_path.read_text(encoding="utf-8"))["fingerprint"]["version"], "v2")
            self.assertEqual(version.previous_rule_content["fingerprint"]["version"], "v1")
            self.assertEqual(service.get_rule_change_candidate(candidate.candidate_id).status, "published")

            rollback = service.rollback_rule_version(version_id=version.version_id, rolled_back_by="cli")

            self.assertEqual(rollback.restored_from_version_id, version.version_id)
            self.assertEqual(json.loads(rule_path.read_text(encoding="utf-8"))["fingerprint"]["version"], "v1")
            self.assertEqual(len(service.list_rule_versions()), 2)

    def test_rule_governance_rejects_unbound_actor_after_permissions_exist(self) -> None:
        with TemporaryDirectory() as temp_dir:
            rule_path = Path(temp_dir) / "rules.json"
            rule_path.write_text(json.dumps({"fingerprint": {"version": "v1"}}, ensure_ascii=False), encoding="utf-8")
            service = RuleGovernanceService(rule_path=rule_path)
            service.bind_rule_permission(actor_id="cli", role="admin")

            with self.assertRaises(PermissionError):
                service.save_rule_change_candidate(
                    {"fingerprint": {"version": "v2"}},
                    created_by="unknown-user",
                )


if __name__ == "__main__":
    unittest.main()
