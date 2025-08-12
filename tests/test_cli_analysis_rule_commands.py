from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from stability.app import DeviceRecordNotFound
from stability.app.analysis_service import AggregatedIssueNotFound
from stability.app.task_service import TaskRecordNotFound
from stability.cli import task_create
from tests.helpers.cli import run_main_with_bundle


class CLIAnalysisRuleCommandsTest(unittest.TestCase):
    def test_delete_analysis_snapshot_outputs_delete_result(self) -> None:
        bundle = SimpleNamespace(
            snapshot_service=SimpleNamespace(
                delete_snapshot=lambda snapshot_id: {
                    "snapshot_id": snapshot_id,
                    "snapshot_type": "top_issues",
                    "name": "Nightly Snapshot",
                    "deleted": True,
                    "deleted_dir": "runtime/analysis_snapshots/snapshot_1",
                    "integrity_before_delete": {"missing_path_count": 0},
                }
            )
        )

        payload = self._run_main_with_bundle(
            ["delete-analysis-snapshot", "--snapshot-id", "snapshot_1"],
            bundle,
        )

        self.assertTrue(payload["delete_result"]["deleted"])
        self.assertEqual(payload["delete_result"]["snapshot_id"], "snapshot_1")

    def test_show_analysis_rules_outputs_effective_rules(self) -> None:
        bundle = SimpleNamespace(
            rule_governance_service=SimpleNamespace(
                inspect_rules=lambda path=None: SimpleNamespace(
                    path=path or "config/stability_rules.json",
                    source_exists=True,
                    validation=SimpleNamespace(
                        path=path or "config/stability_rules.json",
                        source_exists=True,
                        valid=True,
                        errors=(),
                        warnings=("one warning",),
                    ),
                    source_rules={"fingerprint": {"version": "v1"}},
                    default_rules={"fingerprint": {"version": "v1"}},
                    effective_rules={"fingerprint": {"version": "v2"}},
                )
            )
        )

        payload = self._run_main_with_bundle(
            ["show-analysis-rules", "--path", "custom_rules.json"],
            bundle,
        )

        self.assertEqual(payload["rules"]["path"], "custom_rules.json")
        self.assertTrue(payload["rules"]["validation"]["valid"])
        self.assertEqual(payload["rules"]["effective_rules"]["fingerprint"]["version"], "v2")

    def test_export_analysis_rules_outputs_export_result(self) -> None:
        bundle = SimpleNamespace(
            rule_governance_service=SimpleNamespace(
                export_effective_rules=lambda output_path, path=None, overwrite=False: SimpleNamespace(
                    source_path=path or "config/stability_rules.json",
                    output_path=output_path,
                    bytes_written=256,
                    rule_versions={"fingerprint": "v1", "regression": "v1", "attribution": "v1"},
                )
            )
        )

        payload = self._run_main_with_bundle(
            ["export-analysis-rules", "--output", "/tmp/effective_rules.json", "--overwrite"],
            bundle,
        )

        self.assertEqual(payload["export"]["output_path"], "/tmp/effective_rules.json")
        self.assertEqual(payload["export"]["rule_versions"]["regression"], "v1")

    def test_diff_analysis_rules_outputs_diffs(self) -> None:
        bundle = SimpleNamespace(
            rule_governance_service=SimpleNamespace(
                diff_rules=lambda **kwargs: SimpleNamespace(
                    left_label="effective:left.json",
                    right_label="source:right.json",
                    left_path="left.json",
                    right_path="right.json",
                    left_validation=SimpleNamespace(
                        path="left.json",
                        source_exists=True,
                        valid=True,
                        errors=(),
                        warnings=(),
                    ),
                    right_validation=SimpleNamespace(
                        path="right.json",
                        source_exists=True,
                        valid=True,
                        errors=(),
                        warnings=("warn",),
                    ),
                    diff_count=1,
                    diffs=(
                        SimpleNamespace(
                            path="fingerprint.version",
                            change_type="changed",
                            left_value="v1",
                            right_value="v2",
                        ),
                    ),
                )
            )
        )

        payload = self._run_main_with_bundle(
            ["diff-analysis-rules", "--left-view", "effective", "--right-view", "source"],
            bundle,
        )

        self.assertEqual(payload["diff"]["diff_count"], 1)
        self.assertEqual(payload["diff"]["diffs"][0]["path"], "fingerprint.version")

    def test_save_analysis_rule_candidate_outputs_candidate(self) -> None:
        calls: list[dict[str, object]] = []
        bundle = SimpleNamespace(
            rule_governance_service=SimpleNamespace(
                save_rule_change_candidate=lambda patch, **kwargs: calls.append({"patch": patch, **kwargs})
                or SimpleNamespace(
                    candidate_id="rule_candidate_1",
                    rule_path=kwargs.get("path") or "config/stability_rules.json",
                    status="draft",
                    created_by=kwargs.get("created_by", "cli"),
                    patch=patch,
                    diff_count=1,
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "save-analysis-rule-candidate",
                "--path",
                "custom_rules.json",
                "--created-by",
                "alice",
                "--title",
                "Rule update",
                "--set",
                "fingerprint.version=v2",
            ],
            bundle,
        )

        self.assertEqual(calls[0]["patch"], {"fingerprint": {"version": "v2"}})
        self.assertEqual(calls[0]["created_by"], "alice")
        self.assertEqual(payload["candidate"]["candidate_id"], "rule_candidate_1")
        self.assertEqual(payload["candidate"]["status"], "draft")

    def test_publish_analysis_rule_candidate_outputs_version(self) -> None:
        calls: list[dict[str, object]] = []
        bundle = SimpleNamespace(
            rule_governance_service=SimpleNamespace(
                publish_rule_change_candidate=lambda **kwargs: calls.append(kwargs)
                or SimpleNamespace(
                    version_id="rule_version_1",
                    candidate_id=kwargs["candidate_id"],
                    rule_path=kwargs.get("path") or "config/stability_rules.json",
                    published_by=kwargs.get("published_by", "cli"),
                    checksum="abc",
                )
            )
        )

        payload = self._run_main_with_bundle(
            [
                "publish-analysis-rule-candidate",
                "--candidate-id",
                "rule_candidate_1",
                "--published-by",
                "publisher",
            ],
            bundle,
        )

        self.assertEqual(calls[0]["candidate_id"], "rule_candidate_1")
        self.assertEqual(payload["version"]["version_id"], "rule_version_1")
        self.assertEqual(payload["version"]["published_by"], "publisher")

    def test_prune_analysis_snapshots_preview_outputs_plan(self) -> None:
        bundle = SimpleNamespace(
            snapshot_service=SimpleNamespace(
                plan_retention=lambda **kwargs: {
                    "policy": {"max_count": 2, "max_age_days": 7},
                    "matched_snapshot_count": 3,
                    "delete_count": 1,
                    "keep_count": 2,
                    "candidates": [{"snapshot_id": "snapshot_old", "reasons": ["older_than_max_age_days"]}],
                    "kept": [{"snapshot_id": "snapshot_new"}],
                }
            )
        )

        payload = self._run_main_with_bundle(
            ["prune-analysis-snapshots", "--max-count", "2", "--max-age-days", "7"],
            bundle,
        )

        self.assertEqual(payload["retention"]["mode"], "preview")
        self.assertEqual(payload["retention"]["delete_count"], 1)

    def test_prune_analysis_snapshots_execute_outputs_delete_results(self) -> None:
        bundle = SimpleNamespace(
            snapshot_service=SimpleNamespace(
                apply_retention=lambda **kwargs: {
                    "policy": {"max_count": 1},
                    "matched_snapshot_count": 2,
                    "delete_count": 1,
                    "keep_count": 1,
                    "deleted": [{"snapshot_id": "snapshot_old", "deleted": True}],
                }
            )
        )

        payload = self._run_main_with_bundle(
            ["prune-analysis-snapshots", "--max-count", "1", "--execute"],
            bundle,
        )

        self.assertEqual(payload["retention"]["mode"], "execute")
        self.assertTrue(payload["retention"]["deleted"][0]["deleted"])

    _run_main_with_bundle = staticmethod(run_main_with_bundle)


if __name__ == "__main__":
    unittest.main()
