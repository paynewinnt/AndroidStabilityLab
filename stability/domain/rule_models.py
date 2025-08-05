from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .enums import IssueType
from .regression_models import RegressionRuleSet


@dataclass(frozen=True)
class FingerprintRuleConfig:
    """Versioned fingerprint rule configuration."""

    version: str = "v1"
    ignore_raw_key_issue_types: Sequence[IssueType] = field(default_factory=tuple)


@dataclass(frozen=True)
class AttributionRule:
    """One rule used by the minimal preliminary attribution service."""

    rule_id: str
    name: str = ""
    direction: str = "unknown"
    issue_types: Sequence[IssueType] = field(default_factory=tuple)
    scored_issue_types: Sequence[IssueType] = field(default_factory=tuple)
    issue_type_score: int = 0
    title_keywords: Sequence[str] = field(default_factory=tuple)
    summary_keywords: Sequence[str] = field(default_factory=tuple)
    process_keywords: Sequence[str] = field(default_factory=tuple)
    artifact_keywords: Sequence[str] = field(default_factory=tuple)
    metadata_keywords: Sequence[str] = field(default_factory=tuple)
    evidence_signal_keywords: Sequence[str] = field(default_factory=tuple)
    evidence_source_keywords: Sequence[str] = field(default_factory=tuple)
    matched_fragment_keywords: Sequence[str] = field(default_factory=tuple)
    confirmation_level_scores: Mapping[str, int] = field(default_factory=dict)
    recommended_next_steps: Sequence[str] = field(default_factory=tuple)
    review_notes: Sequence[str] = field(default_factory=tuple)
    package_process_match: bool = False


def _default_attribution_rules() -> Sequence[AttributionRule]:
    return (
        AttributionRule(
            rule_id="app_target_process_crash",
            name="Target app process failure",
            direction="app_logic",
            issue_types=(
                IssueType.CRASH,
                IssueType.ANR,
                IssueType.JAVA_EXCEPTION,
                IssueType.JAVA_CRASH,
                IssueType.STARTUP_FAILURE,
                IssueType.PROCESS_EXIT,
            ),
            summary_keywords=("fatal exception", "process crashed", "not responding", "startup failed"),
            package_process_match=True,
        ),
        AttributionRule(
            rule_id="framework_system_service",
            name="Framework or system service signal",
            direction="framework_system_service",
            issue_types=(
                IssueType.CRASH,
                IssueType.ANR,
                IssueType.JAVA_EXCEPTION,
                IssueType.JAVA_CRASH,
                IssueType.SYSTEM_SERVER_CRASH,
                IssueType.WATCHDOG,
                IssueType.REBOOT,
                IssueType.PROCESS_EXIT,
            ),
            scored_issue_types=(IssueType.SYSTEM_SERVER_CRASH, IssueType.WATCHDOG),
            issue_type_score=3,
            process_keywords=("system_server", "zygote", "systemui"),
            summary_keywords=("watchdog", "system_server", "system ui", "framework"),
            metadata_keywords=("system_server", "watchdog", "framework"),
            evidence_signal_keywords=("system_server", "watchdog", "system process"),
            evidence_source_keywords=("dropbox", "system_server", "text"),
            matched_fragment_keywords=("system_server", "watchdog"),
            confirmation_level_scores={"weak": 1, "medium": 2, "strong": 3, "confirmed": 3, "high": 3},
            recommended_next_steps=(
                "优先查看 dropbox/system_server/tombstone 与 reboot 前后的 logcat。",
                "确认 Watchdog 阻塞线程、system_server 崩溃栈和 Framework 服务调用链。",
            ),
            review_notes=(
                "该结论仅表示 Framework/SystemService 方向的初步归因，不等同于最终根因。",
            ),
        ),
        AttributionRule(
            rule_id="driver_hardware_native",
            name="Driver or hardware signal",
            direction="driver_hardware",
            issue_types=(
                IssueType.NATIVE_CRASH,
                IssueType.REBOOT,
                IssueType.PROCESS_EXIT,
                IssueType.CRASH,
            ),
            process_keywords=("vendor.", "android.hardware", "composer", "gralloc"),
            summary_keywords=("kernel panic", "segmentation fault", "signal 11", "vendor"),
        ),
        AttributionRule(
            rule_id="resource_pressure",
            name="Resource pressure signal",
            direction="resource_pressure",
            issue_types=(
                IssueType.ANR,
                IssueType.STARTUP_TIMEOUT,
                IssueType.EXECUTION_TIMEOUT,
                IssueType.PROCESS_EXIT,
                IssueType.CRASH,
            ),
            summary_keywords=("oom", "outofmemory", "low memory", "memory pressure", "timeout"),
            artifact_keywords=("meminfo", "bugreport"),
        ),
        AttributionRule(
            rule_id="graphics_display",
            name="Graphics or display pipeline signal",
            direction="graphics_display",
            issue_types=(
                IssueType.ANR,
                IssueType.NATIVE_CRASH,
                IssueType.EXECUTION_TIMEOUT,
                IssueType.CRASH,
                IssueType.FREEZE,
                IssueType.BLACK_SCREEN,
            ),
            scored_issue_types=(IssueType.FREEZE, IssueType.BLACK_SCREEN),
            issue_type_score=3,
            process_keywords=("surfaceflinger", "renderthread", "hwui"),
            summary_keywords=("jank", "black screen", "freeze", "render", "surface"),
            artifact_keywords=("surfaceflinger", "perfetto"),
            metadata_keywords=("black screen", "freeze", "surfaceflinger", "frame_refresh", "screenshot"),
            evidence_signal_keywords=("black screen", "freeze", "frozen", "frame", "render", "surface", "display"),
            evidence_source_keywords=("screenshot", "surfaceflinger", "frame_refresh", "input"),
            matched_fragment_keywords=("black screen", "freeze", "surface", "display", "frame"),
            confirmation_level_scores={"weak": 1, "medium": 2, "strong": 3, "confirmed": 3, "high": 3},
            recommended_next_steps=(
                "优先检查截图/录屏、SurfaceFlinger、Perfetto 与输入事件时间线。",
                "确认是否存在无帧刷新、黑屏持续、渲染线程阻塞或显示合成异常。",
            ),
            review_notes=(
                "Freeze/Black Screen 归因依赖多源 evidence 更可靠，单一日志命中应人工复核。",
            ),
        ),
    )


@dataclass(frozen=True)
class AttributionRuleConfig:
    """Versioned rule configuration for rule-based preliminary attribution."""

    version: str = "v1"
    fallback_direction: str = "unknown"
    medium_confidence_score: int = 3
    high_confidence_score: int = 5
    rules: Sequence[AttributionRule] = field(default_factory=_default_attribution_rules)


@dataclass(frozen=True)
class AnalysisRuleConfig:
    """Aggregated local rule configuration used by V2 analysis services."""

    fingerprint: FingerprintRuleConfig = field(default_factory=FingerprintRuleConfig)
    regression: RegressionRuleSet = field(default_factory=RegressionRuleSet)
    attribution: AttributionRuleConfig = field(default_factory=AttributionRuleConfig)
