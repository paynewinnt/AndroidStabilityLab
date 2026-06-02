from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stability.app import EvidenceRetentionPolicy, RuntimeLifecycleService
from stability.app.evidence_retention import EvidenceRetentionRule


def _device_dir(root: Path) -> Path:
    path = (
        root
        / "tasks"
        / "task-a"
        / "runs"
        / "run-1"
        / "executions"
        / "instance-1"
        / "devices"
        / "serial-1"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, payload: str, *, age_days: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    when = (datetime.now() - timedelta(days=age_days)).timestamp()
    os.utime(path, (when, when))
    return path


class EvidenceRetentionPolicyTest(unittest.TestCase):
    def test_classify_by_directory_and_extension(self) -> None:
        base = Path("runtime/tasks/t/runs/r/executions/e/devices/d")
        self.assertEqual(EvidenceRetentionPolicy.classify(base / "logs" / "execution.log"), "logs")
        self.assertEqual(EvidenceRetentionPolicy.classify(base / "report" / "report.md"), "report")
        self.assertEqual(EvidenceRetentionPolicy.classify(base / "monitoring" / "samples.json"), "monitoring")
        self.assertEqual(EvidenceRetentionPolicy.classify(base / "artifacts" / "x" / "shot.png"), "artifacts")
        # trace 按扩展名优先，即便落在 artifacts 目录
        self.assertEqual(
            EvidenceRetentionPolicy.classify(base / "artifacts" / "x" / "capture.perfetto-trace"),
            "trace",
        )
        self.assertEqual(EvidenceRetentionPolicy.classify(base / "stray.json"), "unknown")

    def test_from_mapping_overrides_defaults_and_supports_mb(self) -> None:
        policy = EvidenceRetentionPolicy.from_mapping(
            {
                "trace": {"max_age_days": 3, "max_total_mb": 10},
                "report": {"protected": False, "max_age_days": 5},
                "default": {"max_age_days": 45},
            }
        )
        self.assertEqual(policy.rule_for("trace").max_age_days, 3)
        self.assertEqual(policy.rule_for("trace").max_total_bytes, 10 * 1024 * 1024)
        # 未覆盖的字段保留默认值
        self.assertEqual(policy.rule_for("logs").max_age_days, 14)
        self.assertFalse(policy.rule_for("report").protected)
        self.assertEqual(policy.rule_for("report").max_age_days, 5)
        self.assertEqual(policy.rule_for("does-not-exist").max_age_days, 45)


class EvidenceRetentionEnforcementTest(unittest.TestCase):
    def test_age_rule_flags_old_files_and_protects_reports(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            device = _device_dir(root)
            old_log = _write(device / "logs" / "execution.log", "x", age_days=30)
            fresh_log = _write(device / "logs" / "fresh.log", "x", age_days=1)
            old_report = _write(device / "report" / "report.md", "x", age_days=365)

            result = RuntimeLifecycleService(root).enforce_evidence_retention()

        self.assertTrue(result.dry_run)
        paths = {c.path for c in result.candidates}
        self.assertIn(str(old_log), paths)
        self.assertNotIn(str(fresh_log), paths)
        # report 受保护，永不进入候选
        self.assertNotIn(str(old_report), paths)
        self.assertEqual(result.deleted_paths, ())

    def test_size_cap_evicts_oldest_first(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            device = _device_dir(root)
            # 三个 trace，各 100 bytes，全部在保留天数内（age 规则不触发）
            oldest = _write(device / "artifacts" / "a.perfetto-trace", "y" * 100, age_days=2)
            middle = _write(device / "artifacts" / "b.perfetto-trace", "y" * 100, age_days=1)
            newest = _write(device / "artifacts" / "c.perfetto-trace", "y" * 100, age_days=0)

            policy = EvidenceRetentionPolicy(
                rules={"trace": EvidenceRetentionRule("trace", max_age_days=7, max_total_bytes=250)},
            )
            result = RuntimeLifecycleService(root).enforce_evidence_retention(policy=policy)

        size_candidates = [c for c in result.candidates if c.reason == "size_cap"]
        # 300 bytes 超过 250 上限，应淘汰最旧的 1 个使其降到 200
        self.assertEqual(len(size_candidates), 1)
        self.assertEqual(size_candidates[0].path, str(oldest))
        self.assertNotIn(str(middle), {c.path for c in size_candidates})
        self.assertNotIn(str(newest), {c.path for c in size_candidates})

    def test_apply_deletes_candidates_and_reports_reclaimed_bytes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            device = _device_dir(root)
            old_log = _write(device / "logs" / "old.log", "z" * 50, age_days=30)
            keep_log = _write(device / "logs" / "keep.log", "z" * 10, age_days=1)

            result = RuntimeLifecycleService(root).enforce_evidence_retention(apply=True)

            self.assertFalse(result.dry_run)
            self.assertIn(str(old_log), result.deleted_paths)
            self.assertEqual(result.reclaimed_bytes, 50)
            self.assertFalse(old_log.exists())
            self.assertTrue(keep_log.exists())

    def test_latest_subtree_is_never_a_candidate(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            latest_log = _write(root / "tasks" / "latest" / "logs" / "old.log", "z" * 50, age_days=365)

            result = RuntimeLifecycleService(root).enforce_evidence_retention()

        self.assertNotIn(str(latest_log), {c.path for c in result.candidates})

    def test_unknown_files_are_protected_by_default(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            # run.json 直接挂在 task 目录下，不属于任何证据子目录
            stray = _write(root / "tasks" / "task-a" / "run.json", "{}", age_days=365)

            result = RuntimeLifecycleService(root).enforce_evidence_retention()

        self.assertNotIn(str(stray), {c.path for c in result.candidates})

    def test_apply_deleted_paths_match_candidate_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            device = _device_dir(root)
            _write(device / "logs" / "old.log", "z" * 50, age_days=30)

            service = RuntimeLifecycleService(root)
            dry = service.enforce_evidence_retention()
            applied = service.enforce_evidence_retention(apply=True)

        # 删除输出路径格式必须与候选完全一致（不受 resolve 影响）
        self.assertEqual({c.path for c in dry.candidates}, set(applied.deleted_paths))

    def test_usage_summary_tracks_per_type_totals(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "runtime"
            device = _device_dir(root)
            _write(device / "logs" / "old.log", "z" * 40, age_days=30)
            _write(device / "monitoring" / "samples.json", "{}", age_days=1)

            result = RuntimeLifecycleService(root).enforce_evidence_retention()

        usage = {item.evidence_type: item for item in result.usage}
        self.assertEqual(usage["logs"].file_count, 1)
        self.assertEqual(usage["logs"].candidate_count, 1)
        self.assertEqual(usage["monitoring"].candidate_count, 0)
        self.assertEqual(result.scanned_files, 2)


if __name__ == "__main__":
    unittest.main()
