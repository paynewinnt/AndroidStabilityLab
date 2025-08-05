from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from stability.domain import (
    Device,
    DeviceAvailabilityState,
    DeviceConnectionState,
    ExecutionInstance,
    ExecutionStatus,
    ExitReason,
    IssueRecord,
    IssueType,
    ResultLevel,
    RuleReplayGoldenCaseResult,
    RuleReplayGoldenSuiteResult,
    RuleReplayResult,
    SeverityLevel,
    TaskDefinition,
    TaskRun,
    TaskRunStatus,
    TaskTargetApp,
    TaskTemplateType,
)
from stability.repositories import InMemoryInstanceRepository, InMemoryRunRepository, InMemoryTaskRepository

from .rule_replay_service import RuleReplayService


@dataclass(frozen=True)
class _GoldenReplayCase:
    case_id: str
    description: str
    layer: str
    expectation: str
    issue_type: str
    baseline_rules: Mapping[str, Any]
    candidate_rules: Mapping[str, Any]
    filters: Mapping[str, Any]
    dataset: Mapping[str, Any]
    expected: Mapping[str, Any]
    include_unchanged: bool = False


class RuleReplayAcceptanceService:
    """Run one deterministic replay acceptance suite against golden samples."""

    def __init__(self, *, default_suite_path: str = "config/rule_replay_golden_samples.json") -> None:
        self._default_suite_path = default_suite_path

    def verify_golden_suite(
        self,
        *,
        suite_path: str = "",
        case_ids: Sequence[str] | None = None,
        fail_fast: bool = False,
    ) -> RuleReplayGoldenSuiteResult:
        path = Path(suite_path or self._default_suite_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        suite_version = str(payload.get("suite_version", "v1") or "v1")
        selected_ids = {item.strip() for item in (case_ids or ()) if str(item).strip()}
        case_specs = [
            self._parse_case(item)
            for item in payload.get("cases", [])
            if isinstance(item, dict)
        ]
        if selected_ids:
            case_specs = [item for item in case_specs if item.case_id in selected_ids]

        results: list[RuleReplayGoldenCaseResult] = []
        for case in case_specs:
            result = self._verify_case(case)
            results.append(result)
            if fail_fast and not result.passed:
                break

        passed_count = sum(1 for item in results if item.passed)
        failed_count = sum(1 for item in results if not item.passed)
        return RuleReplayGoldenSuiteResult(
            suite_path=str(path),
            suite_version=suite_version,
            case_count=len(results),
            passed_case_count=passed_count,
            failed_case_count=failed_count,
            layer_summaries=self._layer_summaries(results),
            cases=tuple(results),
        )

    def _verify_case(self, case: _GoldenReplayCase) -> RuleReplayGoldenCaseResult:
        replay = self._run_case(case)
        mismatches = self._validate_result(case.expected, replay)
        return RuleReplayGoldenCaseResult(
            case_id=case.case_id,
            description=case.description,
            layer=case.layer,
            expectation=case.expectation,
            issue_type=case.issue_type,
            passed=not mismatches,
            mismatches=tuple(mismatches),
            replay=replay,
        )

    def _run_case(self, case: _GoldenReplayCase) -> RuleReplayResult:
        with TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            baseline_path = base_dir / f"{case.case_id}_baseline.json"
            candidate_path = base_dir / f"{case.case_id}_candidate.json"
            baseline_path.write_text(
                json.dumps(case.baseline_rules, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            candidate_path.write_text(
                json.dumps(case.candidate_rules, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            service = self._build_replay_service(case.dataset, default_rule_path=str(baseline_path))
            return service.replay_top_issues(
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                include_unchanged=case.include_unchanged,
                **dict(case.filters),
            )

    def _build_replay_service(self, dataset: Mapping[str, Any], *, default_rule_path: str) -> RuleReplayService:
        task_repository = InMemoryTaskRepository()
        run_repository = InMemoryRunRepository()
        instance_repository = InMemoryInstanceRepository()

        task_payload = self._mapping(dataset.get("task"))
        task = TaskDefinition(
            task_id=str(task_payload.get("task_id", "task-golden") or "task-golden"),
            task_name=str(task_payload.get("task_name", "Golden Replay Task") or "Golden Replay Task"),
            template_type=TaskTemplateType(str(task_payload.get("template_type", TaskTemplateType.MONKEY.value) or TaskTemplateType.MONKEY.value)),
            target_app=TaskTargetApp(
                package_name=str(
                    self._mapping(task_payload.get("target_app")).get("package_name", "")
                    or task_payload.get("target_app_package", "")
                    or "com.example.app"
                ),
                version_name=str(
                    self._mapping(task_payload.get("target_app")).get("version_name", "")
                    or task_payload.get("version_name", "")
                ),
            ),
            metadata=dict(self._mapping(task_payload.get("metadata"))),
        )
        task_repository.add(task)

        run_payload = self._mapping(dataset.get("run"))
        run = TaskRun(
            run_id=str(run_payload.get("run_id", "run-golden") or "run-golden"),
            task_definition_id=task.task_id,
            task_name=task.task_name,
            status=TaskRunStatus(str(run_payload.get("status", TaskRunStatus.FAILED.value) or TaskRunStatus.FAILED.value)),
            created_at=self._parse_datetime(run_payload.get("created_at")) or datetime(2026, 4, 21, 9, 0, 0),
            metadata=dict(self._mapping(run_payload.get("metadata"))),
        )
        run_repository.add(run)

        instances: list[ExecutionInstance] = []
        for index, item in enumerate(dataset.get("instances", []) if isinstance(dataset.get("instances"), list) else []):
            payload = self._mapping(item)
            device_id = str(payload.get("device_id", f"device-{index + 1}") or f"device-{index + 1}")
            device = Device(
                device_id=device_id,
                serial=device_id,
                connection_state=DeviceConnectionState.ONLINE,
                availability_state=DeviceAvailabilityState.IDLE,
            )
            issues = [self._build_issue(self._mapping(issue), run_id=run.run_id, instance_id=str(payload.get("instance_id", f"instance-{index + 1}") or f"instance-{index + 1}"), device_id=device_id) for issue in payload.get("issues", []) if isinstance(issue, dict)]
            instances.append(
                ExecutionInstance(
                    instance_id=str(payload.get("instance_id", f"instance-{index + 1}") or f"instance-{index + 1}"),
                    run_id=run.run_id,
                    task_definition_id=task.task_id,
                    device_id=device_id,
                    device_snapshot=device.snapshot(),
                    template_type=TaskTemplateType(str(payload.get("template_type", task.template_type.value) or task.template_type.value)),
                    target_app_package=str(payload.get("target_app_package", task.target_app.package_name) or task.target_app.package_name),
                    status=ExecutionStatus(str(payload.get("status", ExecutionStatus.FAILED.value) or ExecutionStatus.FAILED.value)),
                    exit_reason=ExitReason(str(payload.get("exit_reason", ExitReason.EXECUTION_ERROR.value) or ExitReason.EXECUTION_ERROR.value)),
                    result_level=ResultLevel(str(payload.get("result_level", ResultLevel.FAILED.value) or ResultLevel.FAILED.value)),
                    issues=issues,
                    metadata=dict(self._mapping(payload.get("metadata"))),
                )
            )
        instance_repository.add_many(instances)

        return RuleReplayService(
            task_repository=task_repository,
            run_repository=run_repository,
            instance_repository=instance_repository,
            default_rule_path=default_rule_path,
        )

    def _build_issue(
        self,
        payload: Mapping[str, Any],
        *,
        run_id: str,
        instance_id: str,
        device_id: str,
    ) -> IssueRecord:
        return IssueRecord(
            issue_id=str(payload.get("issue_id", f"{instance_id}-issue") or f"{instance_id}-issue"),
            instance_id=instance_id,
            task_run_id=run_id,
            device_id=device_id,
            issue_type=IssueType(str(payload.get("issue_type", IssueType.CRASH.value) or IssueType.CRASH.value)),
            issue_title=str(payload.get("issue_title", "") or ""),
            severity=SeverityLevel(str(payload.get("severity", SeverityLevel.HIGH.value) or SeverityLevel.HIGH.value)),
            detected_at=self._parse_datetime(payload.get("detected_at")) or datetime(2026, 4, 21, 9, 1, 0),
            process_name=str(payload.get("process_name", "") or ""),
            package_name=str(payload.get("package_name", "") or ""),
            raw_key=str(payload.get("raw_key", "") or ""),
            summary=str(payload.get("summary", "") or ""),
            metadata=dict(self._mapping(payload.get("metadata"))),
        )

    def _validate_result(self, expected: Mapping[str, Any], replay: RuleReplayResult) -> list[str]:
        mismatches: list[str] = []
        if "family_count" in expected and replay.family_count != int(expected.get("family_count", replay.family_count)):
            mismatches.append(
                f"family_count expected {expected.get('family_count')} but got {replay.family_count}."
            )
        if "changed_family_count" in expected and replay.changed_family_count != int(
            expected.get("changed_family_count", replay.changed_family_count)
        ):
            mismatches.append(
                "changed_family_count expected "
                f"{expected.get('changed_family_count')} but got {replay.changed_family_count}."
            )
        if "change_summary" in expected:
            expected_summary = {
                str(key): int(value)
                for key, value in self._mapping(expected.get("change_summary")).items()
            }
            actual_summary = {str(key): int(value) for key, value in replay.change_summary.items()}
            if actual_summary != expected_summary:
                mismatches.append(
                    f"change_summary expected {expected_summary} but got {actual_summary}."
                )
        if "baseline_rule_version" in expected and replay.baseline.fingerprint_rule_version != str(
            expected.get("baseline_rule_version", replay.baseline.fingerprint_rule_version)
        ):
            mismatches.append(
                "baseline_rule_version expected "
                f"{expected.get('baseline_rule_version')} but got {replay.baseline.fingerprint_rule_version}."
            )
        if "candidate_rule_version" in expected and replay.candidate.fingerprint_rule_version != str(
            expected.get("candidate_rule_version", replay.candidate.fingerprint_rule_version)
        ):
            mismatches.append(
                "candidate_rule_version expected "
                f"{expected.get('candidate_rule_version')} but got {replay.candidate.fingerprint_rule_version}."
            )

        expected_families = expected.get("families", [])
        if isinstance(expected_families, list):
            if len(replay.families) < len(expected_families):
                mismatches.append(
                    f"expected at least {len(expected_families)} family rows but got {len(replay.families)}."
                )
            for index, family_expected in enumerate(expected_families):
                if index >= len(replay.families):
                    break
                actual = replay.families[index]
                for key, value in self._mapping(family_expected).items():
                    actual_value = getattr(actual, key, None)
                    if actual_value != value:
                        mismatches.append(
                            f"families[{index}].{key} expected {value!r} but got {actual_value!r}."
                        )
        return mismatches

    @staticmethod
    def _layer_summaries(
        cases: Sequence[RuleReplayGoldenCaseResult],
    ) -> dict[str, dict[str, object]]:
        summaries: dict[str, dict[str, object]] = {}
        for item in cases:
            layer = str(item.layer or "default")
            summary = summaries.setdefault(
                layer,
                {
                    "case_count": 0,
                    "passed_case_count": 0,
                    "failed_case_count": 0,
                    "issue_types": [],
                    "expectations": [],
                    "case_ids": [],
                },
            )
            summary["case_count"] = int(summary["case_count"]) + 1
            if item.passed:
                summary["passed_case_count"] = int(summary["passed_case_count"]) + 1
            else:
                summary["failed_case_count"] = int(summary["failed_case_count"]) + 1
            issue_types = set(summary["issue_types"])
            if item.issue_type:
                issue_types.add(item.issue_type)
            summary["issue_types"] = sorted(issue_types)
            expectations = set(summary["expectations"])
            if item.expectation:
                expectations.add(item.expectation)
            summary["expectations"] = sorted(expectations)
            case_ids = list(summary["case_ids"])
            case_ids.append(item.case_id)
            summary["case_ids"] = case_ids
        return summaries

    @staticmethod
    def _parse_case(payload: Mapping[str, Any]) -> _GoldenReplayCase:
        filters = RuleReplayAcceptanceService._mapping(payload.get("filters"))
        expected = RuleReplayAcceptanceService._mapping(payload.get("expected"))
        expectation = str(payload.get("expectation", "") or "").strip()
        if not expectation:
            change_summary = RuleReplayAcceptanceService._mapping(expected.get("change_summary"))
            expectation = ",".join(
                sorted(str(key) for key in change_summary.keys() if str(key).strip())
            ) or "unchanged"
        return _GoldenReplayCase(
            case_id=str(payload.get("case_id", "") or "").strip(),
            description=str(payload.get("description", "") or "").strip(),
            layer=str(payload.get("layer", "") or "default").strip(),
            expectation=expectation,
            issue_type=str(payload.get("issue_type", "") or filters.get("issue_type", "") or "").strip(),
            baseline_rules=RuleReplayAcceptanceService._mapping(payload.get("baseline_rules")),
            candidate_rules=RuleReplayAcceptanceService._mapping(payload.get("candidate_rules")),
            filters=filters,
            dataset=RuleReplayAcceptanceService._mapping(payload.get("dataset")),
            expected=expected,
            include_unchanged=bool(payload.get("include_unchanged", False)),
        )

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None
