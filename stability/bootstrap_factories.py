from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from stability.app import (
    AdmissionCaseService,
    AnalysisService,
    AttributionService,
    CollaborationService,
    ComparisonService,
    ConfigProvider,
    DeviceService,
    ExecutionService,
    IntegrationOutboxService,
    IssueFingerprintGovernanceService,
    PerformanceTrendService,
    PlatformHealthService,
    QualityGateService,
    RegressionService,
    ReleaseSubmissionService,
    RuleGovernanceService,
    RuleReplayAcceptanceService,
    RuleReplayGoldenDraftService,
    RuleReplayGoldenPromotionService,
    RuleReplayGoldenSuiteService,
    RuleReplayService,
    RuleReviewReportService,
    RuleReviewService,
    RunExecutionService,
    RunHistoryService,
    SnapshotService,
    TaskService,
    UnattendedPatrolRunnerService,
    UnattendedService,
)
from stability.domain import Device, QualityGateRiskItem, TaskTemplateType
from stability.execution import ExecutionStateMachine, LifecycleHookRegistry
from stability.infrastructure import (
    ArtifactPathPlanner,
    FileBackedPerformanceRiskThresholdProvider,
    build_monitoring_adapter,
)
from stability.repositories import DomainExecutionInstanceFactory, DomainTaskRunFactory
from stability.scenario import (
    ColdStartLoopScenarioRunner,
    CustomAutomationScenarioRunner,
    ForegroundBackgroundLoopScenarioRunner,
    InstallUninstallLoopScenarioRunner,
    MonkeyScenarioRunner,
    RebootLoopScenarioRunner,
    ScenarioRunner,
    StandbyWakeLoopScenarioRunner,
    get_supported_template_values,
)

from .bootstrap_types import V1BootstrapBundle


class RepositoryBackedDevicePlanner:
    """Planner that resolves runnable devices from the persistent device repository."""

    def __init__(self, device_repository) -> None:
        self._device_repository = device_repository

    def select_devices(self, task, requested_devices=None):
        """Prefer explicit device ids, otherwise return all schedulable repository devices."""
        selected_ids = list(requested_devices or task.selected_device_ids)
        if selected_ids:
            known_devices = {
                device.device_id for device in self._device_repository.list()
            }
            return tuple(
                device_id for device_id in selected_ids if device_id in known_devices
            )
        return tuple(
            device.device_id
            for device in self._device_repository.list()
            if device.is_schedulable()
        )


class NullDiscoveryAdapter:
    """Discovery adapter for in-memory bootstraps."""

    def list_devices(self, include_unavailable: bool = False):
        return []

    def get_device(self, serial: str):
        return None


class NullMonitoringDataProvider:
    """Monitoring data provider for in-memory bootstraps."""

    def get_monitoring_data(
        self,
        session_id: int,
        start_time=None,
        end_time=None,
        data_types=None,
        package_names=None,
    ):
        return {}


@dataclass
class TaskServices:
    task_service: TaskService
    execution_service: ExecutionService
    run_execution_service: RunExecutionService
    run_history_service: RunHistoryService


@dataclass
class AnalysisServices:
    analysis_service: AnalysisService
    attribution_service: AttributionService
    comparison_service: ComparisonService
    performance_trend_service: PerformanceTrendService
    regression_service: RegressionService
    snapshot_service: SnapshotService
    issue_fingerprint_governance_service: IssueFingerprintGovernanceService
    rule_governance_service: RuleGovernanceService
    rule_replay_acceptance_service: RuleReplayAcceptanceService
    rule_replay_golden_draft_service: RuleReplayGoldenDraftService
    rule_replay_golden_promotion_service: RuleReplayGoldenPromotionService
    rule_replay_golden_suite_service: RuleReplayGoldenSuiteService
    rule_replay_service: RuleReplayService
    rule_review_service: RuleReviewService
    rule_review_report_service: RuleReviewReportService


@dataclass
class IntegrationServices:
    collaboration_service: CollaborationService
    quality_gate_service: QualityGateService
    admission_case_service: AdmissionCaseService
    release_submission_service: ReleaseSubmissionService


@dataclass
class RuntimeServices:
    unattended_service: UnattendedService
    unattended_runner_service: UnattendedPatrolRunnerService
    platform_health_service: PlatformHealthService


def build_default_scenario_runners() -> dict[str, ScenarioRunner]:
    """Return the executable runner map for every supported task template."""
    runners = {
        TaskTemplateType.MONKEY.value: MonkeyScenarioRunner(),
        TaskTemplateType.COLD_START_LOOP.value: ColdStartLoopScenarioRunner(),
        TaskTemplateType.FOREGROUND_BACKGROUND_LOOP.value: ForegroundBackgroundLoopScenarioRunner(),
        TaskTemplateType.INSTALL_UNINSTALL_LOOP.value: InstallUninstallLoopScenarioRunner(),
        TaskTemplateType.REBOOT_LOOP.value: RebootLoopScenarioRunner(),
        TaskTemplateType.STANDBY_WAKE_LOOP.value: StandbyWakeLoopScenarioRunner(),
        TaskTemplateType.CUSTOM.value: CustomAutomationScenarioRunner(),
    }
    return {
        template: runners[template]
        for template in get_supported_template_values()
        if template in runners
    }


def build_persistent_monitoring_adapter(
    *,
    monitoring_backend: str | None = None,
    monitoring_config_path: str | Path | None = None,
    config_provider: ConfigProvider | None = None,
):
    provider = config_provider or ConfigProvider()
    settings = provider.monitoring_settings(
        requested_backend=monitoring_backend,
        config_path=monitoring_config_path,
    )
    return build_monitoring_adapter(
        requested_backend=monitoring_backend,
        settings=settings,
    )


def build_device_service(
    *, repository: object, discovery_adapter: object
) -> DeviceService:
    return DeviceService(repository=repository, discovery_adapter=discovery_adapter)


def build_outbox_service(*, outbox_config: object) -> IntegrationOutboxService:
    return IntegrationOutboxService(
        root_dir=outbox_config.root_dir,
        retry_delay_seconds=outbox_config.retry_delay_seconds,
        delivery_interval_seconds=outbox_config.delivery_interval_seconds,
        max_retry_delay_seconds=outbox_config.max_retry_delay_seconds,
        dead_letter_threshold=outbox_config.dead_letter_threshold,
        retry_alert_threshold=outbox_config.retry_alert_threshold,
    )


def build_task_services(
    *,
    task_repository: object,
    run_repository: object,
    instance_repository: object,
    planner: object,
    hooks: LifecycleHookRegistry,
    state_machine: ExecutionStateMachine,
    paths: object,
    audit_event_sink: object,
    monitoring_adapter: object | None,
    instance_factory_devices: Mapping[str, Device] | None = None,
) -> TaskServices:
    task_service = TaskService(
        repository=task_repository, audit_event_sink=audit_event_sink
    )
    execution_service = ExecutionService(
        planner=planner,
        run_factory=DomainTaskRunFactory(),
        instance_factory=DomainExecutionInstanceFactory(
            devices=dict(instance_factory_devices or {})
        ),
        run_repository=run_repository,
        instance_repository=instance_repository,
        state_machine=state_machine,
        hooks=hooks,
    )
    run_execution_service = RunExecutionService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        execution_service=execution_service,
        monitoring_adapter=monitoring_adapter,
        artifact_path_planner=ArtifactPathPlanner(runtime_root=paths.root),
        scenario_runners=build_default_scenario_runners(),
    )
    run_history_service = RunHistoryService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
    )
    return TaskServices(
        task_service=task_service,
        execution_service=execution_service,
        run_execution_service=run_execution_service,
        run_history_service=run_history_service,
    )


def build_analysis_services(
    *,
    task_repository: object,
    run_repository: object,
    instance_repository: object,
    paths: object,
    rule_config: object,
    monitoring_data_provider: object,
    config_provider: ConfigProvider | None = None,
) -> AnalysisServices:
    issue_fingerprint_governance_service = IssueFingerprintGovernanceService(
        root_dir=paths.root / "issue_fingerprint_governance",
    )
    analysis_service = AnalysisService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        rule_config=rule_config,
        fingerprint_governance_service=issue_fingerprint_governance_service,
    )
    comparison_service = ComparisonService(analysis_service=analysis_service)
    attribution_service = AttributionService(
        analysis_service=analysis_service,
        rule_config=rule_config,
    )
    performance_trend_service = PerformanceTrendService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        monitoring_data_provider=monitoring_data_provider,
        risk_threshold_config=_load_performance_risk_threshold_config(
            config_provider=config_provider
        ),
    )
    regression_service = RegressionService(
        comparison_service=comparison_service,
        performance_trend_service=performance_trend_service,
        configured_rule_set=rule_config.regression,
    )
    rule_replay_service = RuleReplayService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
    )
    rule_governance_service = RuleGovernanceService()
    rule_replay_acceptance_service = RuleReplayAcceptanceService()
    rule_replay_golden_draft_service = RuleReplayGoldenDraftService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
    )
    rule_replay_golden_promotion_service = RuleReplayGoldenPromotionService(
        acceptance_service=rule_replay_acceptance_service,
    )
    rule_replay_golden_suite_service = RuleReplayGoldenSuiteService()
    rule_review_service = RuleReviewService(
        rule_replay_service=rule_replay_service,
        rule_governance_service=rule_governance_service,
        rule_replay_acceptance_service=rule_replay_acceptance_service,
        performance_risk_provider=_build_review_performance_risk_provider(
            performance_trend_service
        ),
    )
    snapshot_service = SnapshotService(
        root_dir=paths.analysis_snapshots,
        analysis_service=analysis_service,
        comparison_service=comparison_service,
        regression_service=regression_service,
        rule_replay_service=rule_replay_service,
        rule_review_service=rule_review_service,
    )
    rule_review_report_service = RuleReviewReportService(
        root_dir=paths.analysis_review_reports,
        snapshot_service=snapshot_service,
    )
    return AnalysisServices(
        analysis_service=analysis_service,
        attribution_service=attribution_service,
        comparison_service=comparison_service,
        performance_trend_service=performance_trend_service,
        regression_service=regression_service,
        snapshot_service=snapshot_service,
        issue_fingerprint_governance_service=issue_fingerprint_governance_service,
        rule_governance_service=rule_governance_service,
        rule_replay_acceptance_service=rule_replay_acceptance_service,
        rule_replay_golden_draft_service=rule_replay_golden_draft_service,
        rule_replay_golden_promotion_service=rule_replay_golden_promotion_service,
        rule_replay_golden_suite_service=rule_replay_golden_suite_service,
        rule_replay_service=rule_replay_service,
        rule_review_service=rule_review_service,
        rule_review_report_service=rule_review_report_service,
    )


def build_integration_services(
    *,
    paths: object,
    outbox_service: IntegrationOutboxService,
    task_services: TaskServices,
    analysis_services: AnalysisServices,
    monitoring_backend: str | None = None,
    config_provider: ConfigProvider | None = None,
) -> IntegrationServices:
    config = config_provider or ConfigProvider()
    collaboration_service = CollaborationService(
        root_dir=paths.collaboration,
        outbox_service=outbox_service,
    )
    quality_gate_service = QualityGateService(
        rule_review_report_service=analysis_services.rule_review_report_service,
        root_dir=paths.quality_gates,
        outbox_service=outbox_service,
        policy=config.quality_gate_policy(),
    )
    admission_case_service = AdmissionCaseService(
        rule_review_report_service=analysis_services.rule_review_report_service,
        quality_gate_service=quality_gate_service,
        run_history_service=task_services.run_history_service,
        analysis_service=analysis_services.analysis_service,
        regression_service=analysis_services.regression_service,
        root_dir=paths.admission_cases,
        outbox_service=outbox_service,
    )
    release_submission_service = ReleaseSubmissionService(
        task_service=task_services.task_service,
        execution_service=task_services.execution_service,
        run_execution_service=task_services.run_execution_service,
        admission_case_service=admission_case_service,
        outbox_service=outbox_service,
        root_dir=paths.release_submissions,
        monitoring_backend=monitoring_backend,
    )
    collaboration_service.attach_admission_case_service(admission_case_service)
    return IntegrationServices(
        collaboration_service=collaboration_service,
        quality_gate_service=quality_gate_service,
        admission_case_service=admission_case_service,
        release_submission_service=release_submission_service,
    )


def build_runtime_services(
    *,
    paths: object,
    device_service: DeviceService,
    task_repository: object,
    run_repository: object,
    instance_repository: object,
    task_services: TaskServices,
    outbox_service: IntegrationOutboxService,
    config_provider: ConfigProvider | None = None,
) -> RuntimeServices:
    config = config_provider or ConfigProvider()
    unattended_service = UnattendedService(
        task_repository=task_repository,
        device_service=device_service,
        execution_service=task_services.execution_service,
        run_execution_service=task_services.run_execution_service,
    )
    unattended_runner_service = UnattendedPatrolRunnerService(
        unattended_service=unattended_service,
        root_dir=paths.unattended_runner,
    )
    platform_health_service = PlatformHealthService(
        root_dir=paths.root / "platform_health",
        device_service=device_service,
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        unattended_runner_service=unattended_runner_service,
        integration_outbox_service=outbox_service,
        thresholds=config.platform_health(),
    )
    return RuntimeServices(
        unattended_service=unattended_service,
        unattended_runner_service=unattended_runner_service,
        platform_health_service=platform_health_service,
    )


def build_web_bundle(
    *,
    task_services: TaskServices,
    analysis_services: AnalysisServices,
    integration_services: IntegrationServices,
    runtime_services: RuntimeServices,
    outbox_service: IntegrationOutboxService,
    task_repository: object,
    run_repository: object,
    instance_repository: object,
    planner: object,
    hooks: LifecycleHookRegistry,
    state_machine: ExecutionStateMachine,
    device_service: DeviceService,
    devices: Mapping[str, Device],
    monitoring_backend: str | None = None,
) -> V1BootstrapBundle:
    return V1BootstrapBundle(
        task_service=task_services.task_service,
        execution_service=task_services.execution_service,
        run_execution_service=task_services.run_execution_service,
        run_history_service=task_services.run_history_service,
        analysis_service=analysis_services.analysis_service,
        attribution_service=analysis_services.attribution_service,
        comparison_service=analysis_services.comparison_service,
        performance_trend_service=analysis_services.performance_trend_service,
        regression_service=analysis_services.regression_service,
        snapshot_service=analysis_services.snapshot_service,
        issue_fingerprint_governance_service=analysis_services.issue_fingerprint_governance_service,
        rule_governance_service=analysis_services.rule_governance_service,
        rule_replay_acceptance_service=analysis_services.rule_replay_acceptance_service,
        rule_replay_golden_draft_service=analysis_services.rule_replay_golden_draft_service,
        rule_replay_golden_promotion_service=analysis_services.rule_replay_golden_promotion_service,
        rule_replay_golden_suite_service=analysis_services.rule_replay_golden_suite_service,
        rule_replay_service=analysis_services.rule_replay_service,
        rule_review_service=analysis_services.rule_review_service,
        rule_review_report_service=analysis_services.rule_review_report_service,
        admission_case_service=integration_services.admission_case_service,
        quality_gate_service=integration_services.quality_gate_service,
        release_submission_service=integration_services.release_submission_service,
        collaboration_service=integration_services.collaboration_service,
        integration_outbox_service=outbox_service,
        platform_health_service=runtime_services.platform_health_service,
        unattended_service=runtime_services.unattended_service,
        unattended_runner_service=runtime_services.unattended_runner_service,
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        planner=planner,
        hooks=hooks,
        state_machine=state_machine,
        device_service=device_service,
        devices=dict(devices),
        monitoring_backend=monitoring_backend,
    )


def _load_performance_risk_threshold_config(
    path: str | Path = "config/performance_risk_thresholds.json",
    config_provider: ConfigProvider | None = None,
):
    if config_provider is not None:
        return config_provider.performance_risk_thresholds(config_path=path)
    return FileBackedPerformanceRiskThresholdProvider(path).load()


def _comparison_scope_payload(scope: object) -> dict[str, object]:
    return {
        "dimension": str(getattr(scope, "dimension", "") or ""),
        "value": str(getattr(scope, "value", "") or ""),
        "label": str(getattr(scope, "label", "") or ""),
        "filters": dict(getattr(scope, "filters", {}) or {}),
    }


def _performance_risk_severity(
    *, baseline_average: float | None, average_delta: float | None
) -> str:
    if baseline_average in (None, 0) or average_delta is None:
        return "medium"
    delta_ratio = abs(float(average_delta)) / abs(float(baseline_average))
    return "high" if delta_ratio >= 0.2 else "medium"


def _build_review_performance_risk_provider(
    performance_trend_service: PerformanceTrendService,
):
    def provider(**filters):
        dimension = str(filters.get("dimension", "") or "").strip()
        left_value = str(filters.get("left_value", "") or "").strip()
        right_value = str(filters.get("right_value", "") or "").strip()
        if not dimension or not left_value or not right_value:
            return {}

        comparison = performance_trend_service.compare_performance_trends(
            dimension=dimension,
            left_value=left_value,
            right_value=right_value,
            task_id=str(filters.get("task_id", "") or ""),
            run_status=str(filters.get("run_status", "") or ""),
            template_type=str(filters.get("template_type", "") or ""),
            version=str(filters.get("version", "") or ""),
            package_name=str(filters.get("package_name", "") or ""),
            created_from=str(filters.get("created_from", "") or ""),
            created_to=str(filters.get("created_to", "") or ""),
        )
        items: list[QualityGateRiskItem] = []
        for metric in getattr(comparison, "metrics", ()) or ():
            if str(getattr(metric, "change_type", "") or "") != "worsened":
                continue
            left_summary = getattr(metric, "left_summary", object())
            right_summary = getattr(metric, "right_summary", object())
            items.append(
                QualityGateRiskItem(
                    risk_key=f"performance_{getattr(metric, 'metric_key', 'metric')}_worsened",
                    category="performance",
                    severity=_performance_risk_severity(
                        baseline_average=getattr(left_summary, "average", None),
                        average_delta=getattr(metric, "average_delta", None),
                    ),
                    summary=(
                        f"{getattr(metric, 'label', getattr(metric, 'metric_key', 'Performance Metric'))} "
                        f"在 {getattr(comparison.right_scope, 'label', right_value)} 相比 "
                        f"{getattr(comparison.left_scope, 'label', left_value)} 出现恶化。"
                    ),
                    details={
                        "metric_key": getattr(metric, "metric_key", ""),
                        "label": getattr(metric, "label", ""),
                        "unit": getattr(metric, "unit", ""),
                        "average_delta": getattr(metric, "average_delta", None),
                        "peak_delta": getattr(metric, "peak_delta", None),
                        "p95_delta": getattr(metric, "p95_delta", None),
                        "latest_delta": getattr(metric, "latest_delta", None),
                        "left_average": getattr(left_summary, "average", None),
                        "right_average": getattr(right_summary, "average", None),
                        "left_sample_count": getattr(left_summary, "sample_count", 0),
                        "right_sample_count": getattr(right_summary, "sample_count", 0),
                    },
                    source="performance_trend_service.compare_performance_trends",
                    blocks_admission=False,
                )
            )
        return {
            "dimension": getattr(comparison, "dimension", dimension),
            "left_scope": _comparison_scope_payload(
                getattr(comparison, "left_scope", object())
            ),
            "right_scope": _comparison_scope_payload(
                getattr(comparison, "right_scope", object())
            ),
            "sample_summary": dict(getattr(comparison, "sample_summary", {}) or {}),
            "metric_result_summary": dict(
                getattr(comparison, "metric_change_summary", {}) or {}
            ),
            "comparability_notes": list(
                getattr(comparison, "comparability_notes", ()) or ()
            ),
            "items": items,
        }

    return provider
