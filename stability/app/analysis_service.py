from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence

from stability.domain import (
    AggregatedIssue,
    AnalysisRuleConfig,
    FingerprintRuleConfig,
    IssueEventReference,
    IssueFingerprint,
    IssueRecord,
    IssueType,
    SeverityLevel,
)


class TaskDefinitionLike(Protocol):
    task_id: str
    task_name: str
    template_type: object
    target_app: object


class TaskRepository(Protocol):
    def get(self, task_id: str) -> Optional[TaskDefinitionLike]:
        ...


class TaskRunLike(Protocol):
    run_id: str
    task_definition_id: str
    task_name: str
    run_status: str
    created_at: datetime | None
    metadata: dict[str, Any]


class RunRepository(Protocol):
    def list(self) -> Sequence[TaskRunLike]:
        ...


class ExecutionInstanceLike(Protocol):
    instance_id: str
    run_id: str
    task_definition_id: str
    device_id: str
    target_app_package: str
    template_type: object
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    metadata: dict[str, Any]
    issues: Sequence[IssueRecord]
    artifacts: Sequence[object]


class InstanceRepository(Protocol):
    def list_by_run(self, run_id: str) -> Sequence[ExecutionInstanceLike]:
        ...


@dataclass(frozen=True)
class TopIssueQuery:
    """Filters shared by aggregated issue queries."""

    task_id: str = ""
    run_status: str = ""
    template_type: str = ""
    version: str = ""
    package_name: str = ""
    device_id: str = ""
    issue_type: str = ""
    created_from: str = ""
    created_to: str = ""
    limit: int = 20


@dataclass
class _AggregateBucket:
    fingerprint: IssueFingerprint
    issue_type: IssueType
    events: List[IssueEventReference] = field(default_factory=list)
    title_counter: Counter[str] = field(default_factory=Counter)
    severity_counter: Counter[SeverityLevel] = field(default_factory=Counter)
    run_ids: set[str] = field(default_factory=set)
    devices: set[str] = field(default_factory=set)
    scenarios: set[str] = field(default_factory=set)
    versions: set[str] = field(default_factory=set)
    packages: set[str] = field(default_factory=set)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class AggregatedIssueNotFound(LookupError):
    """Raised when one requested aggregated issue fingerprint does not exist."""


class AnalysisService:
    """Minimal V2 aggregation service built on top of V1 run and instance results."""

    _NORMALIZE_PATTERN = re.compile(r"[^a-z0-9._:-]+")
    _SEVERITY_WEIGHT = {
        SeverityLevel.CRITICAL: 400.0,
        SeverityLevel.HIGH: 250.0,
        SeverityLevel.MEDIUM: 100.0,
        SeverityLevel.LOW: 25.0,
    }

    def __init__(
        self,
        *,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        instance_repository: InstanceRepository,
        rule_config: AnalysisRuleConfig | None = None,
    ) -> None:
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._instance_repository = instance_repository
        self._rule_config = rule_config or AnalysisRuleConfig(
            fingerprint=FingerprintRuleConfig(
                version="v1",
                ignore_raw_key_issue_types=(
                    IssueType.DEVICE_OFFLINE,
                    IssueType.STARTUP_TIMEOUT,
                    IssueType.STARTUP_FAILURE,
                    IssueType.REBOOT,
                    IssueType.EXECUTION_TIMEOUT,
                ),
            )
        )

    @property
    def fingerprint_rule_version(self) -> str:
        return self._rule_config.fingerprint.version

    def list_top_issues(self, **filters: Any) -> List[AggregatedIssue]:
        query = self._build_query(filters)
        items = self.query_aggregated_issues(
            task_id=query.task_id,
            run_status=query.run_status,
            template_type=query.template_type,
            version=query.version,
            package_name=query.package_name,
            device_id=query.device_id,
            issue_type=query.issue_type,
            created_from=query.created_from,
            created_to=query.created_to,
            include_samples=False,
        )
        return items[: self._normalize_limit(query.limit)]

    def get_issue_group(self, fingerprint: str, **filters: Any) -> AggregatedIssue:
        query = self._build_query(filters)
        grouped = self._collect_groups(query)
        item = grouped.get(fingerprint.strip())
        if item is None:
            raise AggregatedIssueNotFound(f"Aggregated issue '{fingerprint}' was not found.")
        return self._to_aggregated_issue(item, include_samples=True)

    def query_aggregated_issues(self, *, include_samples: bool = False, **filters: Any) -> List[AggregatedIssue]:
        query = self._build_query(filters)
        grouped = self._collect_groups(query)
        items = [self._to_aggregated_issue(bucket, include_samples=include_samples) for bucket in grouped.values()]
        items.sort(key=lambda item: (item.score, item.last_seen_at or datetime.min), reverse=True)
        return items

    def build_fingerprint(
        self,
        *,
        issue: IssueRecord,
        instance: ExecutionInstanceLike,
        run: TaskRunLike,
        task: TaskDefinitionLike | None,
    ) -> IssueFingerprint:
        package_name = self._resolve_package_name(issue, instance, task)
        process_name = self._normalize_text(issue.process_name)
        title_key = self._normalize_text(issue.issue_title)
        raw_key = self._normalize_text(issue.raw_key)
        scenario_name = self._normalize_text(self._scenario_name(instance, task))
        if issue.issue_type in set(self._rule_config.fingerprint.ignore_raw_key_issue_types):
            raw_key = ""
        components = {
            "issue_type": issue.issue_type.value,
            "package_name": package_name,
            "process_name": process_name,
            "scenario_name": scenario_name,
            "title_key": title_key,
            "raw_key": raw_key,
        }
        digest = hashlib.sha1(
            json.dumps(components, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return IssueFingerprint(
            value=f"ifp_{digest[:16]}",
            rule_version=self._rule_config.fingerprint.version,
            components=components,
        )

    def _collect_groups(self, query: TopIssueQuery) -> Dict[str, _AggregateBucket]:
        grouped: Dict[str, _AggregateBucket] = {}
        task_cache: Dict[str, TaskDefinitionLike | None] = {}
        created_from = self._parse_iso_datetime(query.created_from)
        created_to = self._parse_iso_datetime(query.created_to)

        for run in self._run_repository.list():
            if query.task_id and getattr(run, "task_definition_id", "") != query.task_id:
                continue
            if query.run_status and getattr(run, "run_status", "") != query.run_status:
                continue
            created_at = getattr(run, "created_at", None)
            if created_from is not None and (created_at or datetime.min) < created_from:
                continue
            if created_to is not None and (created_at or datetime.min) > created_to:
                continue

            task_id = getattr(run, "task_definition_id", "") or ""
            if task_id not in task_cache:
                task_cache[task_id] = self._task_repository.get(task_id)
            task = task_cache[task_id]

            task_template_type = self._task_template_type(task)
            task_version_key = self._task_version_key(task)
            task_package_name = self._task_package_name(task)
            if query.template_type and task_template_type != query.template_type:
                continue
            if query.version and task_version_key != query.version:
                continue
            if query.package_name and task_package_name != query.package_name:
                continue

            instances = self._instance_repository.list_by_run(getattr(run, "run_id", "") or "")
            for instance in instances:
                if query.device_id and getattr(instance, "device_id", "") != query.device_id:
                    continue
                for issue in getattr(instance, "issues", ()) or ():
                    if query.issue_type and issue.issue_type.value != query.issue_type:
                        continue
                    reference = self._build_issue_event_reference(issue=issue, instance=instance, run=run, task=task)
                    fingerprint = self.build_fingerprint(issue=issue, instance=instance, run=run, task=task)
                    bucket = grouped.setdefault(
                        fingerprint.value,
                        _AggregateBucket(
                            fingerprint=fingerprint,
                            issue_type=issue.issue_type,
                        ),
                    )
                    bucket.events.append(reference)
                    title = issue.issue_title or issue.summary or issue.issue_type.value
                    bucket.title_counter[title] += 1
                    bucket.severity_counter[issue.severity] += 1
                    bucket.run_ids.add(getattr(run, "run_id", "") or "")
                    bucket.devices.add(reference.device_id)
                    bucket.scenarios.add(reference.scenario_name)
                    if reference.package_name:
                        bucket.packages.add(reference.package_name)
                    if task_version_key:
                        bucket.versions.add(task_version_key)
                    detected_at = issue.detected_at
                    if bucket.first_seen_at is None or (detected_at and detected_at < bucket.first_seen_at):
                        bucket.first_seen_at = detected_at
                    if bucket.last_seen_at is None or (detected_at and detected_at > bucket.last_seen_at):
                        bucket.last_seen_at = detected_at
        return grouped

    def _to_aggregated_issue(self, bucket: _AggregateBucket, *, include_samples: bool) -> AggregatedIssue:
        title = bucket.title_counter.most_common(1)[0][0] if bucket.title_counter else bucket.issue_type.value
        severity = self._select_bucket_severity(bucket)
        occurrence_count = len(bucket.events)
        affected_run_count = len(bucket.run_ids)
        affected_device_count = len(bucket.devices)
        affected_scenario_count = len(bucket.scenarios)
        affected_version_count = len(bucket.versions)
        score_breakdown = {
            "severity": self._SEVERITY_WEIGHT[severity],
            "occurrence_count": float(occurrence_count) * 10.0,
            "affected_device_count": float(affected_device_count) * 5.0,
            "affected_scenario_count": float(affected_scenario_count) * 5.0,
        }
        score = sum(score_breakdown.values())
        sample_events = sorted(bucket.events, key=lambda item: item.detected_at or datetime.min, reverse=True)
        return AggregatedIssue(
            fingerprint=bucket.fingerprint,
            issue_type=bucket.issue_type,
            title=title,
            severity=severity,
            first_seen_at=bucket.first_seen_at,
            last_seen_at=bucket.last_seen_at,
            occurrence_count=occurrence_count,
            affected_run_count=affected_run_count,
            affected_device_count=affected_device_count,
            affected_scenario_count=affected_scenario_count,
            affected_version_count=affected_version_count,
            affected_packages=tuple(sorted(bucket.packages)),
            affected_devices=tuple(sorted(bucket.devices)),
            affected_scenarios=tuple(sorted(bucket.scenarios)),
            affected_versions=tuple(sorted(bucket.versions)),
            sample_event_ids=tuple(item.event_id for item in sample_events[:10]),
            sample_events=tuple(sample_events if include_samples else sample_events[:3]),
            score=score,
            score_breakdown=score_breakdown,
        )

    def _build_issue_event_reference(
        self,
        *,
        issue: IssueRecord,
        instance: ExecutionInstanceLike,
        run: TaskRunLike,
        task: TaskDefinitionLike | None,
    ) -> IssueEventReference:
        artifact_paths = tuple(
            str(getattr(artifact, "file_path", "") or "")
            for artifact in getattr(instance, "artifacts", ()) or ()
            if str(getattr(artifact, "issue_id", "") or "") in {"", issue.issue_id}
            and str(getattr(artifact, "file_path", "") or "")
        )
        metadata = {
            "run_status": getattr(run, "run_status", ""),
            "instance_status": getattr(instance, "instance_status", ""),
            "result_level": str(getattr(getattr(instance, "result_level", None), "value", getattr(instance, "result_level", ""))),
            "exit_reason": str(getattr(getattr(instance, "exit_reason", None), "value", getattr(instance, "exit_reason", ""))),
            "issue_title": issue.issue_title or "",
            "process_name": issue.process_name or "",
            "raw_key": issue.raw_key or "",
            "issue_metadata": dict(issue.metadata),
        }
        return IssueEventReference(
            event_id=issue.issue_id,
            run_id=getattr(run, "run_id", "") or "",
            task_id=getattr(task, "task_id", "") if task is not None else getattr(run, "task_definition_id", "") or "",
            task_name=getattr(task, "task_name", "") if task is not None else getattr(run, "task_name", "") or "",
            instance_id=getattr(instance, "instance_id", "") or "",
            device_id=getattr(instance, "device_id", "") or "",
            package_name=self._resolve_package_name(issue, instance, task),
            scenario_name=self._scenario_name(instance, task),
            issue_type=issue.issue_type,
            severity=issue.severity,
            detected_at=issue.detected_at,
            summary=issue.summary or "",
            report_path=str(getattr(instance, "metadata", {}).get("report_path", "") or ""),
            execution_log_path=str(
                getattr(instance, "metadata", {}).get("execution_log_path", "")
                or getattr(instance, "metadata", {}).get("log_path", "")
                or ""
            ),
            artifact_paths=artifact_paths,
            metadata=metadata,
        )

    @staticmethod
    def _build_query(filters: Mapping[str, Any]) -> TopIssueQuery:
        return TopIssueQuery(
            task_id=str(filters.get("task_id", "") or ""),
            run_status=str(filters.get("run_status", "") or ""),
            template_type=str(filters.get("template_type", "") or ""),
            version=str(filters.get("version", "") or ""),
            package_name=str(filters.get("package_name", "") or ""),
            device_id=str(filters.get("device_id", "") or ""),
            issue_type=str(filters.get("issue_type", "") or ""),
            created_from=str(filters.get("created_from", "") or ""),
            created_to=str(filters.get("created_to", "") or ""),
            limit=int(filters.get("limit", 20) or 20),
        )

    @staticmethod
    def _normalize_limit(limit: int) -> int:
        return max(0, int(limit))

    @classmethod
    def _normalize_text(cls, value: str | None) -> str:
        text = (value or "").strip().lower()
        return cls._NORMALIZE_PATTERN.sub("-", text).strip("-")

    @staticmethod
    def _parse_iso_datetime(raw: str | None) -> datetime | None:
        if not raw:
            return None
        return datetime.fromisoformat(raw)

    @staticmethod
    def _task_template_type(task: TaskDefinitionLike | None) -> str:
        if task is None:
            return ""
        template_type = getattr(task, "template_type", "")
        return str(getattr(template_type, "value", template_type) or "")

    @staticmethod
    def _task_package_name(task: TaskDefinitionLike | None) -> str:
        if task is None:
            return ""
        target_app = getattr(task, "target_app", None)
        return str(getattr(target_app, "package_name", "") or "")

    @staticmethod
    def _task_version_key(task: TaskDefinitionLike | None) -> str:
        if task is None:
            return ""
        target_app = getattr(task, "target_app", None)
        version_name = str(getattr(target_app, "version_name", "") or "")
        version_code = str(getattr(target_app, "version_code", "") or "")
        if version_name and version_code:
            return f"{version_name}({version_code})"
        return version_name or version_code

    @classmethod
    def _resolve_package_name(
        cls,
        issue: IssueRecord,
        instance: ExecutionInstanceLike,
        task: TaskDefinitionLike | None,
    ) -> str:
        if issue.package_name:
            return issue.package_name
        if getattr(instance, "target_app_package", ""):
            return str(getattr(instance, "target_app_package", "") or "")
        return cls._task_package_name(task)

    @classmethod
    def _scenario_name(cls, instance: ExecutionInstanceLike, task: TaskDefinitionLike | None) -> str:
        template_type = getattr(instance, "template_type", None)
        if template_type is None and task is not None:
            template_type = getattr(task, "template_type", None)
        return str(getattr(template_type, "value", template_type) or "")

    @classmethod
    def _select_bucket_severity(cls, bucket: _AggregateBucket) -> SeverityLevel:
        ordered = sorted(
            bucket.severity_counter.keys(),
            key=lambda item: cls._SEVERITY_WEIGHT.get(item, 0.0),
            reverse=True,
        )
        return ordered[0] if ordered else SeverityLevel.MEDIUM
