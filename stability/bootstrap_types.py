from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from stability.app import (
    AdmissionCaseService,
    AnalysisService,
    AttributionService,
    CollaborationService,
    ComparisonService,
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
from stability.domain import Device
from stability.execution import ExecutionStateMachine, LifecycleHookRegistry


class DeviceSelector(Protocol):
    """Device selection contract shared by bootstrap variants."""

    def select_devices(self, task, requested_devices=None):
        """Choose device ids that should be used for one task run."""
        ...


@dataclass
class V1BootstrapBundle:
    """Container that exposes assembled V1 services and repositories to callers."""

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
    issue_fingerprint_governance_service: IssueFingerprintGovernanceService
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
