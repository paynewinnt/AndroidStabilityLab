from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol

from stability.app import AdmissionCaseService, AnalysisService, AttributionService, CollaborationService, ComparisonService, ConfigProvider, DeviceService, ExecutionService, IntegrationOutboxService, PerformanceTrendService, PlatformHealthService, QualityGateService, RegressionService, ReleaseSubmissionService, RuleGovernanceService, RuleReplayAcceptanceService, RuleReplayGoldenDraftService, RuleReplayGoldenPromotionService, RuleReplayGoldenSuiteService, RuleReplayService, RuleReviewReportService, RuleReviewService, RunExecutionService, RunHistoryService, SnapshotService, TaskService, UnattendedPatrolRunnerService, UnattendedService
from stability.domain import AppError, AppErrorCode, Device, QualityGateRiskItem, TaskTemplateType
from stability.execution import ExecutionStateMachine, LifecycleHookRegistry
from stability.infrastructure import (
    ArtifactPathPlanner,
    FileBackedRuleConfigProvider,
    FileBackedPerformanceRiskThresholdProvider,
    PersistedMonitoringDataProvider,
    build_monitoring_adapter,
    default_analysis_rule_config,
)
from stability.repositories import (
    DomainExecutionInstanceFactory,
    DomainTaskRunFactory,
    InMemoryDeviceRepository,
    InMemoryInstanceRepository,
    InMemoryRunRepository,
    InMemoryTaskRepository,
    StaticDevicePlanner,
)
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


class DeviceSelector(Protocol):
    """Device selection contract shared by the in-memory and persistent bootstraps."""

    def select_devices(self, task, requested_devices=None):
        """Choose device ids that should be used for one task run."""
        ...


class RepositoryBackedDevicePlanner:
    """Planner that resolves runnable devices from the persistent device repository."""

    def __init__(self, device_repository) -> None:
        """Bind the planner to the repository that stores device availability."""
        self._device_repository = device_repository

    def select_devices(self, task, requested_devices=None):
        """Prefer explicit device ids, otherwise return all schedulable repository devices."""
        # 显式指定设备时只保留当前仓储中仍存在的设备，避免为脏配置创建空实例。
        selected_ids = list(requested_devices or task.selected_device_ids)
        if selected_ids:
            known_devices = {device.device_id for device in self._device_repository.list()}
            return tuple(device_id for device_id in selected_ids if device_id in known_devices)
        return tuple(
            device.device_id for device in self._device_repository.list() if device.is_schedulable()
        )


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
    return {template: runners[template] for template in get_supported_template_values() if template in runners}


def _comparison_scope_payload(scope: object) -> dict[str, object]:
    return {
        "dimension": str(getattr(scope, "dimension", "") or ""),
        "value": str(getattr(scope, "value", "") or ""),
        "label": str(getattr(scope, "label", "") or ""),
        "filters": dict(getattr(scope, "filters", {}) or {}),
    }


def _performance_risk_severity(*, baseline_average: float | None, average_delta: float | None) -> str:
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
        for metric in (getattr(comparison, "metrics", ()) or ()):
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
            "left_scope": _comparison_scope_payload(getattr(comparison, "left_scope", object())),
            "right_scope": _comparison_scope_payload(getattr(comparison, "right_scope", object())),
            "sample_summary": dict(getattr(comparison, "sample_summary", {}) or {}),
            "metric_result_summary": dict(getattr(comparison, "metric_change_summary", {}) or {}),
            "comparability_notes": list(getattr(comparison, "comparability_notes", ()) or ()),
            "items": items,
        }

    return provider


@dataclass
class V1BootstrapBundle:
    """Container that exposes the assembled V1 services and repositories to callers."""

    task_service: TaskService
    execution_service: ExecutionService
    run_execution_service: RunExecutionService | None
    run_history_service: RunHistoryService
    analysis_service: AnalysisService
    attribution_service: AttributionService
    comparison_service: ComparisonService
    performance_trend_service: PerformanceTrendService
    regression_service: RegressionService
    snapshot_service: SnapshotService
    rule_governance_service: RuleGovernanceService
    rule_replay_acceptance_service: RuleReplayAcceptanceService
    rule_replay_golden_draft_service: RuleReplayGoldenDraftService
    rule_replay_golden_promotion_service: RuleReplayGoldenPromotionService
    rule_replay_golden_suite_service: RuleReplayGoldenSuiteService
    rule_replay_service: RuleReplayService
    rule_review_service: RuleReviewService
    rule_review_report_service: RuleReviewReportService
    admission_case_service: AdmissionCaseService
    quality_gate_service: QualityGateService
    release_submission_service: ReleaseSubmissionService | None
    collaboration_service: CollaborationService
    integration_outbox_service: IntegrationOutboxService
    platform_health_service: PlatformHealthService
    unattended_service: UnattendedService | None
    unattended_runner_service: UnattendedPatrolRunnerService | None
    task_repository: object
    run_repository: object
    instance_repository: object
    planner: DeviceSelector
    hooks: LifecycleHookRegistry
    state_machine: ExecutionStateMachine
    device_service: DeviceService | None = None
    devices: dict[str, Device] = field(default_factory=dict)
    monitoring_backend: str | None = None


def _build_persistent_monitoring_adapter(
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


def _load_performance_risk_threshold_config(
    path: str | Path = "config/performance_risk_thresholds.json",
    config_provider: ConfigProvider | None = None,
):
    if config_provider is not None:
        return config_provider.performance_risk_thresholds(config_path=path)
    return FileBackedPerformanceRiskThresholdProvider(path).load()


def create_v1_bootstrap(
    devices: Iterable[Device] | None = None,
    *,
    config_provider: ConfigProvider | None = None,
) -> V1BootstrapBundle:
    """Build an in-memory V1 runtime for smoke tests and fast local development."""
    config = config_provider or ConfigProvider()
    paths = config.runtime_paths()
    outbox_config = config.outbox()
    device_map = {device.device_id: device for device in (devices or [])}
    device_repository = InMemoryDeviceRepository()
    for device in device_map.values():
        device_repository.add(device)
    task_repository = InMemoryTaskRepository()
    run_repository = InMemoryRunRepository()
    instance_repository = InMemoryInstanceRepository()
    planner = StaticDevicePlanner(devices=device_map)
    hooks = LifecycleHookRegistry()
    state_machine = ExecutionStateMachine()
    rule_config = default_analysis_rule_config()

    class _NullDiscoveryAdapter:
        def list_devices(self, include_unavailable: bool = False):
            return []

        def get_device(self, serial: str):
            return None

    class _NullMonitoringDataProvider:
        def get_monitoring_data(self, session_id: int, start_time=None, end_time=None, data_types=None, package_names=None):
            return {}

    device_service = DeviceService(
        repository=device_repository,
        discovery_adapter=_NullDiscoveryAdapter(),
    )
    integration_outbox_service = IntegrationOutboxService(
        root_dir=outbox_config.root_dir,
        retry_delay_seconds=outbox_config.retry_delay_seconds,
        delivery_interval_seconds=outbox_config.delivery_interval_seconds,
        max_retry_delay_seconds=outbox_config.max_retry_delay_seconds,
        dead_letter_threshold=outbox_config.dead_letter_threshold,
        retry_alert_threshold=outbox_config.retry_alert_threshold,
    )
    task_service = TaskService(repository=task_repository, audit_event_sink=integration_outbox_service)
    execution_service = ExecutionService(
        planner=planner,
        run_factory=DomainTaskRunFactory(),
        instance_factory=DomainExecutionInstanceFactory(devices=device_map),
        run_repository=run_repository,
        instance_repository=instance_repository,
        state_machine=state_machine,
        hooks=hooks,
    )
    analysis_service = AnalysisService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        rule_config=rule_config,
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
        monitoring_data_provider=_NullMonitoringDataProvider(),
        risk_threshold_config=_load_performance_risk_threshold_config(config_provider=config),
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
        performance_risk_provider=_build_review_performance_risk_provider(performance_trend_service),
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
    collaboration_service = CollaborationService(
        root_dir=paths.collaboration,
        outbox_service=integration_outbox_service,
    )
    quality_gate_service = QualityGateService(
        rule_review_report_service=rule_review_report_service,
        root_dir=paths.quality_gates,
        outbox_service=integration_outbox_service,
    )
    run_history_service = RunHistoryService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
    )
    admission_case_service = AdmissionCaseService(
        rule_review_report_service=rule_review_report_service,
        quality_gate_service=quality_gate_service,
        run_history_service=run_history_service,
        analysis_service=analysis_service,
        regression_service=regression_service,
        root_dir=paths.admission_cases,
        outbox_service=integration_outbox_service,
    )
    run_execution_service = RunExecutionService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        execution_service=execution_service,
        monitoring_adapter=None,
        artifact_path_planner=ArtifactPathPlanner(runtime_root=paths.root),
        scenario_runners=build_default_scenario_runners(),
    )
    release_submission_service = ReleaseSubmissionService(
        task_service=task_service,
        execution_service=execution_service,
        run_execution_service=run_execution_service,
        admission_case_service=admission_case_service,
        outbox_service=integration_outbox_service,
        root_dir=paths.release_submissions,
    )
    collaboration_service.attach_admission_case_service(admission_case_service)
    unattended_service = UnattendedService(
        task_repository=task_repository,
        device_service=device_service,
        execution_service=execution_service,
        run_execution_service=run_execution_service,
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
        integration_outbox_service=integration_outbox_service,
    )
    return V1BootstrapBundle(
        task_service=task_service,
        execution_service=execution_service,
        # 内存版主要服务于骨架开发和冒烟验证，不依赖数据库和旧监控存储。
        run_execution_service=run_execution_service,
        run_history_service=run_history_service,
        analysis_service=analysis_service,
        attribution_service=attribution_service,
        comparison_service=comparison_service,
        performance_trend_service=performance_trend_service,
        regression_service=regression_service,
        snapshot_service=snapshot_service,
        rule_governance_service=rule_governance_service,
        rule_replay_acceptance_service=rule_replay_acceptance_service,
        rule_replay_golden_draft_service=rule_replay_golden_draft_service,
        rule_replay_golden_promotion_service=rule_replay_golden_promotion_service,
        rule_replay_golden_suite_service=rule_replay_golden_suite_service,
        rule_replay_service=rule_replay_service,
        rule_review_service=rule_review_service,
        rule_review_report_service=rule_review_report_service,
        admission_case_service=admission_case_service,
        quality_gate_service=quality_gate_service,
        release_submission_service=release_submission_service,
        collaboration_service=collaboration_service,
        integration_outbox_service=integration_outbox_service,
        platform_health_service=platform_health_service,
        unattended_service=unattended_service,
        unattended_runner_service=unattended_runner_service,
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        planner=planner,
        hooks=hooks,
        state_machine=state_machine,
        device_service=device_service,
        devices=device_map,
    )


def create_v1_persistent_bootstrap(
    *,
    monitoring_backend: str | None = None,
    monitoring_config_path: str | Path | None = None,
    config_provider: ConfigProvider | None = None,
) -> V1BootstrapBundle:
    """Build a database-backed runtime wired to ADB and monitoring adapters."""
    config = config_provider or ConfigProvider()
    paths = config.runtime_paths()
    outbox_config = config.outbox()
    try:
        from stability.infrastructure.persistence import db_manager
        from stability.infrastructure import ADBCollectorDeviceAdapter
        from stability.repositories.sqlalchemy import (
            SQLAlchemyDeviceRepository,
            SQLAlchemyInstanceRepository,
            SQLAlchemyRunRepository,
            SQLAlchemyTaskRepository,
        )
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on runtime environment
        raise AppError(
            AppErrorCode.INTERNAL_ERROR,
            "Persistent V1 bootstrap requires optional database dependencies such as sqlalchemy.",
        ) from exc

    if not db_manager.is_connected() and not db_manager.connect():
        raise AppError(AppErrorCode.INTERNAL_ERROR, "Unable to connect to the configured database.")

    task_repository = SQLAlchemyTaskRepository(db_manager)
    run_repository = SQLAlchemyRunRepository(db_manager)
    instance_repository = SQLAlchemyInstanceRepository(db_manager)
    device_repository = SQLAlchemyDeviceRepository(db_manager)
    rule_config = FileBackedRuleConfigProvider("config/stability_rules.json").load()
    planner = RepositoryBackedDevicePlanner(device_repository)
    hooks = LifecycleHookRegistry()
    state_machine = ExecutionStateMachine()
    monitoring_adapter, resolved_monitoring_backend = _build_persistent_monitoring_adapter(
        monitoring_backend=monitoring_backend,
        monitoring_config_path=monitoring_config_path,
        config_provider=config,
    )
    device_service = DeviceService(
        repository=device_repository,
        discovery_adapter=ADBCollectorDeviceAdapter(),
    )

    integration_outbox_service = IntegrationOutboxService(
        root_dir=outbox_config.root_dir,
        retry_delay_seconds=outbox_config.retry_delay_seconds,
        delivery_interval_seconds=outbox_config.delivery_interval_seconds,
        max_retry_delay_seconds=outbox_config.max_retry_delay_seconds,
        dead_letter_threshold=outbox_config.dead_letter_threshold,
        retry_alert_threshold=outbox_config.retry_alert_threshold,
    )
    task_service = TaskService(repository=task_repository, audit_event_sink=integration_outbox_service)
    execution_service = ExecutionService(
        planner=planner,
        run_factory=DomainTaskRunFactory(),
        instance_factory=DomainExecutionInstanceFactory(),
        run_repository=run_repository,
        instance_repository=instance_repository,
        state_machine=state_machine,
        hooks=hooks,
    )
    # 持久化版把监控适配层和运行目录规划一并接上，供 CLI 和 Web 共用。
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
    analysis_service = AnalysisService(
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        rule_config=rule_config,
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
        monitoring_data_provider=PersistedMonitoringDataProvider(),
        risk_threshold_config=_load_performance_risk_threshold_config(config_provider=config),
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
        performance_risk_provider=_build_review_performance_risk_provider(performance_trend_service),
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
    collaboration_service = CollaborationService(
        root_dir=paths.collaboration,
        outbox_service=integration_outbox_service,
    )
    quality_gate_service = QualityGateService(
        rule_review_report_service=rule_review_report_service,
        root_dir=paths.quality_gates,
        outbox_service=integration_outbox_service,
    )
    admission_case_service = AdmissionCaseService(
        rule_review_report_service=rule_review_report_service,
        quality_gate_service=quality_gate_service,
        run_history_service=run_history_service,
        analysis_service=analysis_service,
        regression_service=regression_service,
        root_dir=paths.admission_cases,
        outbox_service=integration_outbox_service,
    )
    release_submission_service = ReleaseSubmissionService(
        task_service=task_service,
        execution_service=execution_service,
        run_execution_service=run_execution_service,
        admission_case_service=admission_case_service,
        outbox_service=integration_outbox_service,
        root_dir=paths.release_submissions,
        monitoring_backend=resolved_monitoring_backend,
    )
    collaboration_service.attach_admission_case_service(admission_case_service)
    unattended_service = UnattendedService(
        task_repository=task_repository,
        device_service=device_service,
        execution_service=execution_service,
        run_execution_service=run_execution_service,
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
        integration_outbox_service=integration_outbox_service,
    )

    devices = {device.device_id: device for device in device_repository.list()}
    return V1BootstrapBundle(
        task_service=task_service,
        execution_service=execution_service,
        run_execution_service=run_execution_service,
        run_history_service=run_history_service,
        analysis_service=analysis_service,
        attribution_service=attribution_service,
        comparison_service=comparison_service,
        performance_trend_service=performance_trend_service,
        regression_service=regression_service,
        snapshot_service=snapshot_service,
        rule_governance_service=rule_governance_service,
        rule_replay_acceptance_service=rule_replay_acceptance_service,
        rule_replay_golden_draft_service=rule_replay_golden_draft_service,
        rule_replay_golden_promotion_service=rule_replay_golden_promotion_service,
        rule_replay_golden_suite_service=rule_replay_golden_suite_service,
        rule_replay_service=rule_replay_service,
        rule_review_service=rule_review_service,
        rule_review_report_service=rule_review_report_service,
        admission_case_service=admission_case_service,
        quality_gate_service=quality_gate_service,
        release_submission_service=release_submission_service,
        collaboration_service=collaboration_service,
        integration_outbox_service=integration_outbox_service,
        platform_health_service=platform_health_service,
        unattended_service=unattended_service,
        unattended_runner_service=unattended_runner_service,
        task_repository=task_repository,
        run_repository=run_repository,
        instance_repository=instance_repository,
        planner=planner,
        hooks=hooks,
        state_machine=state_machine,
        device_service=device_service,
        devices=devices,
        monitoring_backend=resolved_monitoring_backend,
    )
