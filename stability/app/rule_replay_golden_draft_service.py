from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Optional, Protocol, Sequence

from stability.domain import (
    DeviceSnapshot,
    ExecutionInstance,
    ExecutionStatus,
    ExitReason,
    IssueRecord,
    IssueType,
    ResultLevel,
    RuleReplayGoldenDraftResult,
    SamplingConfig,
    TaskDefinition,
    TaskRun,
    TaskRunStatus,
    TaskTargetApp,
)
from stability.time_utils import now_beijing_string
from stability.repositories import InMemoryInstanceRepository, InMemoryRunRepository, InMemoryTaskRepository

from .run_execution_service import RunRecordNotFound
from .rule_replay_service import RuleReplayService


class TaskRepository(Protocol):
    def get(self, task_id: str) -> Optional[TaskDefinition]:
        ...


class RunRepository(Protocol):
    def get(self, run_id: str) -> Optional[TaskRun]:
        ...


class InstanceRepository(Protocol):
    def list_by_run(self, run_id: str) -> Sequence[ExecutionInstance]:
        ...


class RuleReplayGoldenDraftService:
    """Export one replay golden-sample draft from persisted run data."""

    _SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
    _DEFAULT_LAYER_BY_ISSUE_TYPE = {
        IssueType.CRASH.value: "merge_semantics",
        IssueType.ANR.value: "merge_semantics",
        IssueType.PROCESS_EXIT.value: "merge_semantics",
        IssueType.STARTUP_TIMEOUT.value: "merge_semantics",
        IssueType.STARTUP_FAILURE.value: "merge_semantics",
        IssueType.DEVICE_OFFLINE.value: "identity_semantics",
        IssueType.REBOOT.value: "identity_semantics",
        IssueType.EXECUTION_TIMEOUT.value: "stability_guard",
    }

    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        instance_repository: InstanceRepository,
        default_rule_path: str = "config/stability_rules.json",
    ) -> None:
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._instance_repository = instance_repository
        self._default_rule_path = default_rule_path

    def create_draft(
        self,
        *,
        run_id: str,
        output_path: str,
        issue_ids: Sequence[str] | None = None,
        issue_type: str = "",
        limit: int = 0,
        case_id: str = "",
        description: str = "",
        layer: str = "",
        expectation: str = "",
        baseline_path: str = "",
        candidate_path: str = "",
        append: bool = False,
    ) -> RuleReplayGoldenDraftResult:
        run = self._run_repository.get(run_id.strip())
        if run is None:
            raise RunRecordNotFound(f"Run '{run_id}' was not found.")

        task = self._task_repository.get(getattr(run, "task_definition_id", "") or "")
        instances = list(self._instance_repository.list_by_run(run.run_id))
        selected = self._select_issues(
            instances=instances,
            issue_ids=tuple(issue_ids or ()),
            issue_type=issue_type.strip(),
            limit=limit,
        )
        selected_issue_type = self._single_issue_type(selected)
        selected_issue_ids = tuple(issue.issue_id for _, issue in selected)
        selected_instance_ids = tuple(dict.fromkeys(instance.instance_id for instance, _ in selected))
        resolved_baseline_path = str(Path(baseline_path.strip() or self._default_rule_path))
        resolved_candidate_path = str(
            Path(candidate_path.strip() or baseline_path.strip() or self._default_rule_path)
        )
        baseline_rules = self._load_rule_file(resolved_baseline_path)
        candidate_rules = self._load_rule_file(resolved_candidate_path)
        selected_instances = self._selected_instances(instances, selected_issue_ids)
        replay_preview = self._build_replay_preview(
            task=task,
            run=run,
            instances=selected_instances,
            baseline_rules=baseline_rules,
            candidate_rules=candidate_rules,
            issue_type=selected_issue_type,
        )

        resolved_case_id = case_id.strip() or self._default_case_id(run.run_id, selected_issue_type)
        resolved_layer = layer.strip() or self._DEFAULT_LAYER_BY_ISSUE_TYPE.get(selected_issue_type, "draft")
        resolved_expectation = expectation.strip() or self._default_expectation(replay_preview)
        resolved_description = description.strip() or self._default_description(
            run_id=run.run_id,
            issue_type=selected_issue_type,
            issue_count=len(selected_issue_ids),
        )

        case_payload = {
            "case_id": resolved_case_id,
            "description": resolved_description,
            "layer": resolved_layer,
            "expectation": resolved_expectation,
            "issue_type": selected_issue_type,
            "baseline_rules": baseline_rules,
            "candidate_rules": candidate_rules,
            "filters": self._filters(task=task, issue_type=selected_issue_type, selected=selected),
            "include_unchanged": self._should_include_unchanged(
                expectation=resolved_expectation,
                replay_preview=replay_preview,
            ),
            "dataset": self._dataset_payload(task=task, run=run, instances=selected_instances),
            "expected": self._expected_payload(replay_preview),
            "draft_metadata": {
                "source_run_id": run.run_id,
                "source_task_id": getattr(run, "task_definition_id", ""),
                "selected_issue_ids": list(selected_issue_ids),
                "selected_instance_ids": list(selected_instance_ids),
                "generated_at": now_beijing_string(),
                "baseline_rule_path": resolved_baseline_path,
                "candidate_rule_path": resolved_candidate_path,
            },
            "replay_preview": self._replay_preview_payload(replay_preview),
        }

        output = Path(output_path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        suite_payload = self._load_or_initialize_suite(output, append=append)
        suite_payload["suite_version"] = str(suite_payload.get("suite_version", "v2") or "v2")
        suite_payload["generated_by"] = "draft-rule-replay-golden-sample"
        suite_payload["generated_at"] = now_beijing_string()
        cases = [
            item
            for item in suite_payload.get("cases", [])
            if isinstance(item, dict) and str(item.get("case_id", "") or "") != resolved_case_id
        ]
        cases.append(case_payload)
        suite_payload["cases"] = cases
        output.write_text(json.dumps(suite_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return RuleReplayGoldenDraftResult(
            output_path=str(output),
            suite_version=str(suite_payload.get("suite_version", "v2") or "v2"),
            appended=append and output.exists(),
            case_id=resolved_case_id,
            issue_type=selected_issue_type,
            layer=resolved_layer,
            expectation=resolved_expectation,
            issue_count=len(selected_issue_ids),
            source_run_id=run.run_id,
            selected_issue_ids=selected_issue_ids,
            selected_instance_ids=selected_instance_ids,
            baseline_path=resolved_baseline_path,
            candidate_path=resolved_candidate_path,
            expected=self._expected_payload(replay_preview),
            replay_preview=replay_preview,
        )

    def _load_or_initialize_suite(self, output: Path, *, append: bool) -> dict[str, Any]:
        if append and output.exists():
            payload = json.loads(output.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"Golden suite output must be a JSON object: {output}")
            payload.setdefault("cases", [])
            if not isinstance(payload["cases"], list):
                raise ValueError(f"Golden suite 'cases' must be a JSON array: {output}")
            return payload
        return {
            "suite_version": "v2",
            "cases": [],
        }

    def _load_rule_file(self, path: str) -> Mapping[str, Any]:
        candidate = Path(path)
        if not candidate.exists():
            raise FileNotFoundError(f"Rule file not found: {candidate}")
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Rule file must contain a JSON object: {candidate}")
        return payload

    def _select_issues(
        self,
        *,
        instances: Sequence[ExecutionInstance],
        issue_ids: Sequence[str],
        issue_type: str,
        limit: int,
    ) -> list[tuple[ExecutionInstance, IssueRecord]]:
        lookup = {
            issue.issue_id: (instance, issue)
            for instance in instances
            for issue in (instance.issues or [])
        }
        requested_ids = [item.strip() for item in issue_ids if str(item).strip()]
        if requested_ids:
            missing = [item for item in requested_ids if item not in lookup]
            if missing:
                raise ValueError(f"Issue ids were not found in the run: {', '.join(missing)}")
            return [lookup[item] for item in requested_ids]

        if not issue_type:
            raise ValueError("Provide at least one --issue-id or one --issue-type filter.")

        selected: list[tuple[ExecutionInstance, IssueRecord]] = []
        for instance in instances:
            for issue in (instance.issues or []):
                if issue.issue_type.value == issue_type:
                    selected.append((instance, issue))
        selected.sort(
            key=lambda item: (
                item[1].detected_at or datetime.min,
                item[1].issue_id,
            )
        )
        if limit > 0:
            selected = selected[:limit]
        if not selected:
            raise ValueError(f"No issues matched issue_type='{issue_type}' in run '{instances[0].run_id if instances else ''}'.")
        return selected

    @staticmethod
    def _single_issue_type(selected: Sequence[tuple[ExecutionInstance, IssueRecord]]) -> str:
        issue_types = {issue.issue_type.value for _, issue in selected}
        if len(issue_types) != 1:
            raise ValueError(
                "Selected issues must share exactly one issue_type. "
                f"Current selection contains: {', '.join(sorted(issue_types))}"
            )
        return next(iter(issue_types))

    @staticmethod
    def _selected_instances(
        instances: Sequence[ExecutionInstance],
        selected_issue_ids: Sequence[str],
    ) -> list[ExecutionInstance]:
        selected_issue_set = set(selected_issue_ids)
        selected_instances: list[ExecutionInstance] = []
        for instance in instances:
            issues = [issue for issue in (instance.issues or []) if issue.issue_id in selected_issue_set]
            if not issues:
                continue
            selected_instances.append(
                ExecutionInstance(
                    instance_id=instance.instance_id,
                    run_id=instance.run_id,
                    task_definition_id=instance.task_definition_id,
                    device_id=instance.device_id,
                    device_snapshot=instance.device_snapshot,
                    template_type=instance.template_type,
                    target_app_package=instance.target_app_package,
                    status=instance.status,
                    queued_at=instance.queued_at,
                    started_at=instance.started_at,
                    finished_at=instance.finished_at,
                    exit_reason=instance.exit_reason,
                    result_level=instance.result_level,
                    monitoring_session_id=instance.monitoring_session_id,
                    summary=instance.summary,
                    issues=[RuleReplayGoldenDraftService._copy_issue(issue) for issue in issues],
                    artifacts=list(instance.artifacts or []),
                    performance_summaries=list(instance.performance_summaries or []),
                    metadata=dict(instance.metadata),
                )
            )
        return selected_instances

    @staticmethod
    def _copy_issue(issue: IssueRecord) -> IssueRecord:
        return IssueRecord(
            issue_id=issue.issue_id,
            instance_id=issue.instance_id,
            task_run_id=issue.task_run_id,
            device_id=issue.device_id,
            issue_type=issue.issue_type,
            issue_title=issue.issue_title,
            severity=issue.severity,
            detected_at=issue.detected_at,
            source=issue.source,
            raw_key=issue.raw_key,
            process_name=issue.process_name,
            package_name=issue.package_name,
            pid=issue.pid,
            summary=issue.summary,
            is_deduplicated=issue.is_deduplicated,
            metadata=dict(issue.metadata),
        )

    def _build_replay_preview(
        self,
        *,
        task: TaskDefinition | None,
        run: TaskRun,
        instances: Sequence[ExecutionInstance],
        baseline_rules: Mapping[str, Any],
        candidate_rules: Mapping[str, Any],
        issue_type: str,
    ):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            baseline_path = root / "baseline.json"
            candidate_path = root / "candidate.json"
            baseline_path.write_text(json.dumps(baseline_rules, ensure_ascii=False, indent=2), encoding="utf-8")
            candidate_path.write_text(json.dumps(candidate_rules, ensure_ascii=False, indent=2), encoding="utf-8")

            task_repository = InMemoryTaskRepository()
            run_repository = InMemoryRunRepository()
            instance_repository = InMemoryInstanceRepository()
            task_repository.add(task or self._draft_task_definition(run=run, instances=instances))
            run_repository.add(run)
            instance_repository.add_many(instances)
            replay_service = RuleReplayService(
                task_repository=task_repository,
                run_repository=run_repository,
                instance_repository=instance_repository,
                default_rule_path=str(baseline_path),
            )
            selected_package = self._resolve_package_name(task=task, instances=instances)
            return replay_service.replay_top_issues(
                baseline_path=str(baseline_path),
                candidate_path=str(candidate_path),
                package_name=selected_package,
                issue_type=issue_type,
                limit=max(20, len(instances) * 5),
                include_unchanged=True,
            )

    @staticmethod
    def _draft_task_definition(run: TaskRun, instances: Sequence[ExecutionInstance]) -> TaskDefinition:
        package_name = ""
        template_type = instances[0].template_type if instances else "custom"
        if instances:
            package_name = instances[0].target_app_package
        return TaskDefinition(
            task_id=getattr(run, "task_definition_id", "") or "task-draft",
            task_name=getattr(run, "task_name", "") or "Draft Task",
            template_type=template_type,
            target_app=TaskTargetApp(package_name=package_name),
            sampling_config=SamplingConfig(),
        )

    @staticmethod
    def _resolve_package_name(task: TaskDefinition | None, instances: Sequence[ExecutionInstance]) -> str:
        if task is not None and getattr(getattr(task, "target_app", None), "package_name", ""):
            return str(task.target_app.package_name)
        for instance in instances:
            if instance.target_app_package:
                return instance.target_app_package
            for issue in instance.issues:
                if issue.package_name:
                    return issue.package_name
        return ""

    def _filters(
        self,
        *,
        task: TaskDefinition | None,
        issue_type: str,
        selected: Sequence[tuple[ExecutionInstance, IssueRecord]],
    ) -> dict[str, str]:
        package_name = self._resolve_package_name(
            task=task,
            instances=[instance for instance, _ in selected],
        )
        return {
            "package_name": package_name,
            "issue_type": issue_type,
        }

    def _dataset_payload(
        self,
        *,
        task: TaskDefinition | None,
        run: TaskRun,
        instances: Sequence[ExecutionInstance],
    ) -> dict[str, Any]:
        return {
            "task": self._task_payload(task, run=run, instances=instances),
            "run": self._run_payload(run),
            "instances": [self._instance_payload(item) for item in instances],
        }

    def _task_payload(
        self,
        task: TaskDefinition | None,
        *,
        run: TaskRun,
        instances: Sequence[ExecutionInstance],
    ) -> dict[str, Any]:
        if task is None:
            task = self._draft_task_definition(run=run, instances=instances)
        return {
            "task_id": task.task_id,
            "task_name": task.task_name,
            "template_type": task.template_type.value,
            "target_app": {
                "package_name": task.target_app.package_name,
                "launch_activity": task.target_app.launch_activity,
                "version_name": task.target_app.version_name,
            },
            "metadata": dict(task.metadata),
        }

    @staticmethod
    def _run_payload(run: TaskRun) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "status": run.run_status,
            "created_at": run.created_at.isoformat() if run.created_at else "",
            "metadata": dict(run.metadata),
        }

    @staticmethod
    def _instance_payload(instance: ExecutionInstance) -> dict[str, Any]:
        return {
            "instance_id": instance.instance_id,
            "device_id": instance.device_id,
            "template_type": instance.template_type.value,
            "target_app_package": instance.target_app_package,
            "status": instance.instance_status,
            "exit_reason": instance.exit_reason.value if isinstance(instance.exit_reason, ExitReason) else str(instance.exit_reason),
            "result_level": instance.result_level.value if isinstance(instance.result_level, ResultLevel) else str(instance.result_level),
            "metadata": dict(instance.metadata),
            "issues": [RuleReplayGoldenDraftService._issue_payload(issue) for issue in (instance.issues or [])],
        }

    @staticmethod
    def _issue_payload(issue: IssueRecord) -> dict[str, Any]:
        return {
            "issue_id": issue.issue_id,
            "issue_type": issue.issue_type.value,
            "issue_title": issue.issue_title,
            "severity": issue.severity.value,
            "detected_at": issue.detected_at.isoformat() if issue.detected_at else "",
            "process_name": issue.process_name,
            "package_name": issue.package_name,
            "raw_key": issue.raw_key,
            "summary": issue.summary,
            "metadata": dict(issue.metadata),
        }

    @staticmethod
    def _expected_payload(replay_preview) -> dict[str, Any]:
        return {
            "family_count": int(getattr(replay_preview, "family_count", 0) or 0),
            "changed_family_count": int(getattr(replay_preview, "changed_family_count", 0) or 0),
            "change_summary": dict(getattr(replay_preview, "change_summary", {}) or {}),
        }

    @staticmethod
    def _replay_preview_payload(replay_preview) -> dict[str, Any]:
        return {
            "family_count": int(getattr(replay_preview, "family_count", 0) or 0),
            "changed_family_count": int(getattr(replay_preview, "changed_family_count", 0) or 0),
            "change_summary": dict(getattr(replay_preview, "change_summary", {}) or {}),
            "families": [
                {
                    "comparison_key": getattr(item, "comparison_key", ""),
                    "issue_type": getattr(item, "issue_type", ""),
                    "change_type": getattr(item, "change_type", ""),
                    "left_group_count": int(getattr(item, "left_group_count", 0) or 0),
                    "right_group_count": int(getattr(item, "right_group_count", 0) or 0),
                    "left_occurrence_count": int(getattr(item, "left_occurrence_count", 0) or 0),
                    "right_occurrence_count": int(getattr(item, "right_occurrence_count", 0) or 0),
                    "left_sample_event_ids": list(getattr(item, "left_sample_event_ids", ()) or ()),
                    "right_sample_event_ids": list(getattr(item, "right_sample_event_ids", ()) or ()),
                }
                for item in (getattr(replay_preview, "families", ()) or ())
            ],
        }

    @staticmethod
    def _default_case_id(run_id: str, issue_type: str) -> str:
        run_suffix = RuleReplayGoldenDraftService._SLUG_PATTERN.sub("-", run_id.lower()).strip("-")[:16]
        issue_slug = RuleReplayGoldenDraftService._SLUG_PATTERN.sub("-", issue_type.lower()).strip("-")
        return f"{issue_slug}_{run_suffix or 'run'}_draft"

    @staticmethod
    def _default_description(*, run_id: str, issue_type: str, issue_count: int) -> str:
        return (
            f"Draft imported from run {run_id} with {issue_count} "
            f"{issue_type} issue event(s)."
        )

    @staticmethod
    def _default_expectation(replay_preview) -> str:
        change_summary = dict(getattr(replay_preview, "change_summary", {}) or {})
        if len(change_summary) == 1:
            return next(iter(change_summary.keys()))
        if not change_summary:
            return "manual_review"
        return "manual_review"

    @staticmethod
    def _should_include_unchanged(*, expectation: str, replay_preview) -> bool:
        if expectation == "unchanged":
            return True
        change_summary = dict(getattr(replay_preview, "change_summary", {}) or {})
        return "unchanged" in change_summary
